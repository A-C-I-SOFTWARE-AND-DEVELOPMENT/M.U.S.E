"""Core job controller for the Hermes local orchestrator.

This is the Python counterpart to the Android local orchestrator
(see ``docs/hermes-local-orchestrator.md``): a *single-device* manager
that organizes work for the AI tools the user is already logged into.
No API calls are made from this module — it owns filesystem state only.

The controller persists every job under
``.hermes-orchestrator/jobs/<job-id>/`` so jobs survive process
restarts, are inspectable with plain ``ls`` / ``cat``, and can be
hand-edited if needed.

Layout per job::

    .hermes-orchestrator/
        jobs/
            <job-id>/
                job.json
                decision_ledger.md
                scorecard.md
                workers/
                    <worker-id>/
                        prompt.md
                        artifacts/<files…>
                github/
                    pr_body.md
                    decision_ledger.md
                    scorecard.md
                    manifest.json

The controller is intentionally storage-only. It does not spawn
subprocesses, does not call external APIs, does not touch the
network, and does not import the agent loop. That makes it trivial
to test and safe to invoke from any context (CLI, gateway, tests).
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from hermes_cli.orchestrator_models import (
    DEFAULT_WORKERS_BY_MODE,
    HistoryEntry,
    Job,
    JobMode,
    JobState,
    WorkerRole,
    WorkerSpec,
)

logger = logging.getLogger(__name__)

ROOT_DIRNAME = ".hermes-orchestrator"
JOBS_DIRNAME = "jobs"
JOB_FILE = "job.json"
DECISION_LEDGER_FILE = "decision_ledger.md"
SCORECARD_FILE = "scorecard.md"
WORKERS_DIRNAME = "workers"
ARTIFACTS_DIRNAME = "artifacts"
PROMPT_FILE = "prompt.md"
GITHUB_DIRNAME = "github"
PR_BODY_FILE = "pr_body.md"
MANIFEST_FILE = "manifest.json"

# Match Android: codex / chatgpt / claude_code / claude / manual.
DEFAULT_TARGET_TOOL_BY_ROLE: dict[str, str] = {
    WorkerRole.BUILDER: "codex",
    WorkerRole.REVIEWER: "claude_code",
    WorkerRole.PLANNER: "chatgpt",
    WorkerRole.ARCHITECT: "claude",
}

# Job IDs are timestamped + short random suffix so they sort
# chronologically on disk and are easy to scan in ``ls``.
_JOB_ID_RE = re.compile(r"^[a-z0-9_\-]+$")

# Modes whose workers write to the repo; they carry an effect surface in
# the blast-radius estimate (write + the tools the workers spawn).
_WRITE_MODES = frozenset({JobMode.BUILD, JobMode.DEBUG, JobMode.REFACTOR})


def estimate_job_risk(
    mode: str,
    trusted_local: bool,
    *,
    prompt: str = "",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Classify a job's blast radius at planning time.

    Defaults are mode-derived: write modes (build/debug/refactor)
    declare ``fs.write`` + ``process.spawn`` effects; a write job in an
    *untrusted* repo additionally counts as changing default behavior,
    which forces HIGH. Callers holding a task graph pass ``overrides``
    (``loc``/``files``/``effects``/``changes_default_behavior``) for a
    sharper estimate. Returns None when the bridge is unavailable —
    classification is advisory, never a crash.
    """
    try:
        from hermes_cli.jarvis_prime.axiom_bridge import get_bridge

        mode_clean = (mode or "").strip().lower()
        writes = mode_clean in _WRITE_MODES
        params: dict[str, Any] = {
            "description": f"orchestrator {mode_clean} job",
            "loc": 0,
            "files": 1,
            "effects": ("fs.write", "process.spawn") if writes else (),
            "changes_default_behavior": writes and not trusted_local,
        }
        params.update(overrides or {})
        classification = get_bridge().classify_change(**params)
        classification["strict_evidence"] = classification["risk"] in ("MED", "HIGH")
        return classification
    except Exception:
        return None


def run_job_gates(
    job: Job,
    packet: dict[str, Any],
    *,
    evidence_bundle: Any | None = None,
) -> Any:
    """Run exactly the job's risk-profiled gates against *packet*.

    MED/HIGH jobs are evidence-strict by default (self-attested packets
    cannot pass); HIGH jobs additionally treat the job itself as an
    owner-gated action. Jobs without a stored classification fall back
    to the full default gate run.
    """
    from hermes_cli.jarvis_prime.gates import gates_for_profile, run_gate_summary

    risk = dict(job.metadata.get("risk") or {})
    profile = risk.get("gates") or ()
    strict = bool(risk.get("strict_evidence"))
    if not profile:
        return run_gate_summary(
            packet, evidence_bundle=evidence_bundle, strict_evidence=strict
        )
    gates = gates_for_profile(
        profile,
        evidence_bundle=evidence_bundle,
        strict_evidence=strict,
        high_risk=risk.get("risk") == "HIGH",
    )
    return run_gate_summary(packet, gates=gates)


class JobControllerError(RuntimeError):
    """Base error for the orchestrator controller."""


class JobNotFoundError(JobControllerError):
    """Raised when a job_id does not exist on disk."""


class InvalidStateError(JobControllerError):
    """Raised when a state value is not recognized."""


def _now() -> float:
    return time.time()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _new_job_id() -> str:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dt%H%M%Sz")
    suffix = secrets.token_hex(3)
    return f"{stamp}-{suffix}"


def _atomic_write_text(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically.

    Uses a temp file in the same directory + os.replace so a partial
    write never leaves a half-baked file on disk.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}.{secrets.token_hex(3)}")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _atomic_write_json(path: Path, data: Any) -> None:
    _atomic_write_text(
        path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def _sanitize_id(raw: str, *, field_name: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise JobControllerError(f"{field_name} is required")
    if not _JOB_ID_RE.match(text):
        raise JobControllerError(
            f"{field_name} must match {_JOB_ID_RE.pattern}; got {text!r}"
        )
    return text


class JobController:
    """Filesystem-backed controller for Hermes orchestrator jobs."""

    def __init__(self, root: str | Path | None = None) -> None:
        """Create a controller rooted at ``root`` (defaults to ``$PWD/.hermes-orchestrator``)."""
        if root is None:
            env_root = os.environ.get("HERMES_ORCHESTRATOR_HOME")
            root = Path(env_root) if env_root else Path.cwd() / ROOT_DIRNAME
        self.root = Path(root)
        self.jobs_dir = self.root / JOBS_DIRNAME

    # ── path helpers ──────────────────────────────────────────────────

    def job_dir(self, job_id: str) -> Path:
        return self.jobs_dir / _sanitize_id(job_id, field_name="job_id")

    def _job_file(self, job_id: str) -> Path:
        return self.job_dir(job_id) / JOB_FILE

    def _workers_dir(self, job_id: str) -> Path:
        return self.job_dir(job_id) / WORKERS_DIRNAME

    def _worker_dir(self, job_id: str, worker_id: str) -> Path:
        return self._workers_dir(job_id) / _sanitize_id(
            worker_id, field_name="worker_id"
        )

    def _github_dir(self, job_id: str) -> Path:
        return self.job_dir(job_id) / GITHUB_DIRNAME

    # ── create / load / list ──────────────────────────────────────────

    def create_job(
        self,
        prompt: str,
        mode: str,
        repo_root: str | Path,
        trusted_local: bool,
        *,
        workers: Iterable[WorkerSpec] | None = None,
        job_id: str | None = None,
        risk_overrides: dict[str, Any] | None = None,
    ) -> Job:
        """Create a new job, persist ``job.json``, return the Job.

        Workers default to a sensible fan-out per mode (see
        ``DEFAULT_WORKERS_BY_MODE``) unless ``workers=`` is provided.

        The job is risk-classified at creation (``metadata["risk"]``:
        band, score, gate profile, strict-evidence flag — see
        :func:`estimate_job_risk`); ``risk_overrides`` feeds task-graph
        estimates (loc/files/effects/changes_default_behavior) into the
        classifier. Gate runs should go through :func:`run_job_gates`
        so exactly the classified profile executes.
        """
        if not (prompt or "").strip():
            raise JobControllerError("prompt is required")
        mode_clean = (mode or "").strip().lower()
        if not mode_clean:
            raise JobControllerError("mode is required")
        if mode_clean not in JobMode.ALL:
            raise JobControllerError(
                f"mode must be one of {sorted(JobMode.ALL)}; got {mode!r}"
            )

        repo_root_str = repo_root if isinstance(repo_root, str) else str(repo_root)

        jid = _sanitize_id(job_id, field_name="job_id") if job_id else _new_job_id()
        if (self.jobs_dir / jid).exists():
            raise JobControllerError(f"job already exists: {jid}")

        resolved_workers: list[WorkerSpec]
        if workers is None:
            resolved_workers = [
                WorkerSpec(
                    worker_id=f"w{i + 1}-{role}",
                    role=role,
                    target_tool=DEFAULT_TARGET_TOOL_BY_ROLE.get(role, "manual"),
                )
                for i, role in enumerate(DEFAULT_WORKERS_BY_MODE.get(mode_clean, ()))
            ]
        else:
            resolved_workers = list(workers)
            for spec in resolved_workers:
                if not isinstance(spec, WorkerSpec):
                    raise JobControllerError(
                        "workers must be WorkerSpec instances"
                    )
                _sanitize_id(spec.worker_id, field_name="worker.worker_id")
                if not (spec.role or "").strip():
                    raise JobControllerError("worker.role is required")
            seen: set[str] = set()
            for spec in resolved_workers:
                if spec.worker_id in seen:
                    raise JobControllerError(
                        f"duplicate worker_id: {spec.worker_id}"
                    )
                seen.add(spec.worker_id)

        now = _now()
        metadata: dict[str, Any] = {}
        risk = estimate_job_risk(
            mode_clean,
            bool(trusted_local),
            prompt=prompt,
            overrides=risk_overrides,
        )
        if risk is not None:
            metadata["risk"] = risk

        job = Job(
            job_id=jid,
            prompt=prompt,
            mode=mode_clean,
            repo_root=repo_root_str,
            trusted_local=bool(trusted_local),
            state=JobState.CREATED,
            created_at=now,
            updated_at=now,
            workers=resolved_workers,
            history=[
                HistoryEntry(
                    timestamp=now,
                    from_state=None,
                    to_state=JobState.CREATED,
                    note="job created",
                )
            ],
            metadata=metadata,
        )
        self._persist(job)
        if risk is not None:
            try:
                from hermes_cli.jarvis_prime.axiom_bridge import get_bridge

                get_bridge().record_event(
                    "job.classified",
                    {
                        "job_id": jid,
                        "mode": mode_clean,
                        "risk": risk.get("risk"),
                        "score": risk.get("score"),
                        "gates": risk.get("gates"),
                    },
                )
            except Exception:
                pass
        logger.info(
            "orchestrator: created job %s (mode=%s, risk=%s)",
            jid,
            mode_clean,
            (risk or {}).get("risk", "unclassified"),
        )
        return job

    def load_job(self, job_id: str) -> Job:
        path = self._job_file(job_id)
        if not path.exists():
            raise JobNotFoundError(f"job not found: {job_id}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise JobControllerError(
                f"job.json for {job_id} is corrupt: {exc}"
            ) from exc
        return Job.from_dict(data)

    def list_jobs(self) -> list[Job]:
        """Return every persisted job, sorted oldest-first by created_at."""
        if not self.jobs_dir.exists():
            return []
        out: list[Job] = []
        for entry in sorted(self.jobs_dir.iterdir()):
            if not entry.is_dir():
                continue
            job_file = entry / JOB_FILE
            if not job_file.exists():
                continue
            try:
                out.append(self.load_job(entry.name))
            except JobControllerError as exc:
                logger.warning(
                    "orchestrator: skipping unreadable job %s (%s)", entry.name, exc
                )
        out.sort(key=lambda j: (j.created_at, j.job_id))
        return out

    # ── state ─────────────────────────────────────────────────────────

    def get_status(self, job_id: str) -> str:
        return self.load_job(job_id).state

    def update_status(
        self, job_id: str, state: str, *, note: str | None = None
    ) -> Job:
        if state not in JobState.ALL:
            raise InvalidStateError(
                f"state must be one of {sorted(JobState.ALL)}; got {state!r}"
            )
        job = self.load_job(job_id)
        if job.state == state:
            return job  # no-op; do not append a duplicate history entry
        prev = job.state
        now = _now()
        job.state = state
        job.updated_at = now
        job.history.append(
            HistoryEntry(
                timestamp=now,
                from_state=prev,
                to_state=state,
                note=note,
            )
        )
        self._persist(job)
        logger.info(
            "orchestrator: job %s state %s -> %s", job_id, prev, state
        )
        return job

    # ── decision ledger ───────────────────────────────────────────────

    def write_decision_ledger(self, job_id: str, content: str) -> Path:
        """Persist a free-form markdown decision ledger for the job."""
        # load_job validates the job exists and the id is well-formed
        self.load_job(job_id)
        path = self.job_dir(job_id) / DECISION_LEDGER_FILE
        _atomic_write_text(path, content if content.endswith("\n") else content + "\n")
        return path

    # ── workers ───────────────────────────────────────────────────────

    def create_worker_folders(self, job_id: str) -> list[Path]:
        """Create one folder per worker on the job. Idempotent."""
        job = self.load_job(job_id)
        if not job.workers:
            raise JobControllerError(
                f"job {job_id} has no workers; cannot create worker folders"
            )
        created: list[Path] = []
        for spec in job.workers:
            wdir = self._worker_dir(job_id, spec.worker_id)
            (wdir / ARTIFACTS_DIRNAME).mkdir(parents=True, exist_ok=True)
            created.append(wdir)
        return created

    def write_worker_prompt(self, job_id: str, worker_id: str, prompt: str) -> Path:
        """Write ``prompt.md`` for a specific worker. Creates folders if needed."""
        if not (prompt or "").strip():
            raise JobControllerError("worker prompt must not be empty")
        job = self.load_job(job_id)
        spec = job.worker(worker_id)
        if spec is None:
            raise JobControllerError(
                f"job {job_id} has no worker {worker_id!r}"
            )
        wdir = self._worker_dir(job_id, worker_id)
        (wdir / ARTIFACTS_DIRNAME).mkdir(parents=True, exist_ok=True)
        path = wdir / PROMPT_FILE
        _atomic_write_text(path, prompt if prompt.endswith("\n") else prompt + "\n")
        spec.prompt_written = True
        job.updated_at = _now()
        self._persist(job)
        return path

    def collect_worker_artifacts(self, job_id: str) -> dict[str, list[Path]]:
        """Scan each worker's ``artifacts/`` directory.

        Returns a mapping ``{worker_id: [Path, …]}`` and updates each
        worker's ``artifact_count`` on the persisted job. Workers with
        no artifacts directory yet map to an empty list.
        """
        job = self.load_job(job_id)
        result: dict[str, list[Path]] = {}
        for spec in job.workers:
            adir = self._worker_dir(job_id, spec.worker_id) / ARTIFACTS_DIRNAME
            if adir.exists():
                files = sorted(p for p in adir.rglob("*") if p.is_file())
            else:
                files = []
            result[spec.worker_id] = files
            spec.artifact_count = len(files)
        job.updated_at = _now()
        self._persist(job)
        return result

    # ── scorecard ─────────────────────────────────────────────────────

    def write_scorecard(
        self, job_id: str, payload: dict[str, Any] | None = None
    ) -> Path:
        """Render a scorecard.md summarizing the job + worker artifacts.

        ``payload`` may include free-form ``summary`` text and a
        ``scores`` dict (``{worker_id: {metric: value, …}}``) which is
        rendered as a table. Both are optional.
        """
        job = self.load_job(job_id)
        artifacts = self.collect_worker_artifacts(job_id)
        payload = dict(payload or {})

        lines: list[str] = []
        lines.append(f"# Scorecard — job {job.job_id}")
        lines.append("")
        lines.append(f"- Mode: `{job.mode}`")
        lines.append(f"- State: `{job.state}`")
        lines.append(f"- Repo: `{job.repo_root}`")
        lines.append(f"- Trusted local: `{job.trusted_local}`")
        lines.append(f"- Created: `{_iso(job.created_at)}`")
        lines.append(f"- Updated: `{_iso(job.updated_at)}`")
        lines.append("")

        if payload.get("summary"):
            lines.append("## Summary")
            lines.append("")
            lines.append(str(payload["summary"]).strip())
            lines.append("")

        lines.append("## Workers")
        lines.append("")
        if not job.workers:
            lines.append("_No workers assigned._")
            lines.append("")
        else:
            lines.append("| Worker | Role | Target tool | Prompt | Artifacts |")
            lines.append("| --- | --- | --- | --- | --- |")
            for spec in job.workers:
                lines.append(
                    f"| `{spec.worker_id}` | {spec.role} | "
                    f"{spec.target_tool} | "
                    f"{'yes' if spec.prompt_written else 'no'} | "
                    f"{len(artifacts.get(spec.worker_id, []))} |"
                )
            lines.append("")

        scores = payload.get("scores")
        if isinstance(scores, dict) and scores:
            metrics = sorted({m for v in scores.values() if isinstance(v, dict) for m in v})
            if metrics:
                lines.append("## Scores")
                lines.append("")
                lines.append("| Worker | " + " | ".join(metrics) + " |")
                lines.append("| --- | " + " | ".join("---" for _ in metrics) + " |")
                for wid, row in scores.items():
                    if not isinstance(row, dict):
                        continue
                    cells = [str(row.get(m, "")) for m in metrics]
                    lines.append(f"| `{wid}` | " + " | ".join(cells) + " |")
                lines.append("")

        lines.append("## Artifacts")
        lines.append("")
        any_artifacts = False
        for spec in job.workers:
            files = artifacts.get(spec.worker_id, [])
            if not files:
                continue
            any_artifacts = True
            lines.append(f"### `{spec.worker_id}`")
            lines.append("")
            for p in files:
                rel = p.relative_to(self.job_dir(job_id))
                lines.append(f"- `{rel.as_posix()}`")
            lines.append("")
        if not any_artifacts:
            lines.append("_No artifacts collected yet._")
            lines.append("")

        path = self.job_dir(job_id) / SCORECARD_FILE
        _atomic_write_text(path, "\n".join(lines))
        return path

    # ── github bundle ─────────────────────────────────────────────────

    def prepare_github_artifacts(self, job_id: str) -> Path:
        """Assemble a GitHub-ready bundle in ``<job>/github/``.

        Copies decision_ledger.md and scorecard.md if present, writes a
        ``pr_body.md`` derived from the job prompt + summary, and emits
        a ``manifest.json`` describing the bundle.

        Returns the path to the ``github/`` directory.
        """
        job = self.load_job(job_id)
        gdir = self._github_dir(job_id)
        gdir.mkdir(parents=True, exist_ok=True)

        copied: list[str] = []
        ledger_src = self.job_dir(job_id) / DECISION_LEDGER_FILE
        if ledger_src.exists():
            dst = gdir / DECISION_LEDGER_FILE
            _atomic_write_text(dst, ledger_src.read_text(encoding="utf-8"))
            copied.append(DECISION_LEDGER_FILE)

        scorecard_src = self.job_dir(job_id) / SCORECARD_FILE
        if scorecard_src.exists():
            dst = gdir / SCORECARD_FILE
            _atomic_write_text(dst, scorecard_src.read_text(encoding="utf-8"))
            copied.append(SCORECARD_FILE)

        pr_body = self._render_pr_body(job, included=copied)
        _atomic_write_text(gdir / PR_BODY_FILE, pr_body)

        manifest = {
            "job_id": job.job_id,
            "mode": job.mode,
            "state": job.state,
            "repo_root": job.repo_root,
            "trusted_local": job.trusted_local,
            "created_at": _iso(job.created_at),
            "updated_at": _iso(job.updated_at),
            "workers": [w.to_dict() for w in job.workers],
            "files": [PR_BODY_FILE, *copied, MANIFEST_FILE],
        }
        _atomic_write_json(gdir / MANIFEST_FILE, manifest)

        return gdir

    # ── internals ─────────────────────────────────────────────────────

    def _persist(self, job: Job) -> None:
        self.job_dir(job.job_id).mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self._job_file(job.job_id), job.to_dict())

    @staticmethod
    def _render_pr_body(job: Job, *, included: list[str]) -> str:
        first_line = (job.prompt.splitlines() or [""])[0].strip()
        title = first_line[:80] or f"job {job.job_id}"
        lines: list[str] = []
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"muse orchestrator job `{job.job_id}` (mode `{job.mode}`).")
        lines.append("")
        lines.append("## Prompt")
        lines.append("")
        lines.append("```")
        lines.append(job.prompt.rstrip())
        lines.append("```")
        lines.append("")
        if job.workers:
            lines.append("## Workers")
            lines.append("")
            for spec in job.workers:
                lines.append(
                    f"- `{spec.worker_id}` — {spec.role} → {spec.target_tool}"
                    f" (artifacts: {spec.artifact_count})"
                )
            lines.append("")
        if included:
            lines.append("## Attached artifacts")
            lines.append("")
            for name in included:
                lines.append(f"- `{name}`")
            lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(
            "_Generated by the muse local orchestrator. Every handoff to an"
            " AI tool is user-driven; this PR body summarizes work prepared"
            " locally and does not include any provider API credentials._"
        )
        lines.append("")
        return "\n".join(lines)
