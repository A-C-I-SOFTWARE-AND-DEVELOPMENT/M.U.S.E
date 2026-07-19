"""Local orchestrator controller for the Hermes CLI.

Provides Python-level entry points for the native Hermes orchestration
slash commands:

  * ``/orchestrate <prompt>``
  * ``/orchestrator list``
  * ``/orchestrator status [job-id]``
  * ``/orchestrator open <job-id>``
  * ``/orchestrator resume <job-id>``
  * ``/orchestrator cancel <job-id>``
  * ``/orchestrator approve <job-id> <phase>``
  * ``/orchestrator validate <job-id>``
  * ``/orchestrator publish <job-id>``
  * ``/orchestrator publish-plan <job-id>``
  * ``/model-router explain <prompt>``
  * ``/decision-ledger show [job-id]``
  * ``/ai-radar update``
  * ``/best-coding-tool-mission status``
  * ``/voice-capture status``
  * ``/voice-capture mode <push_to_talk|wake_word|driving_capture|disabled>``
  * ``/remote-worker status``
  * ``/self-improve run <job-id>``
  * ``/profile build-github-history``

The controller is intentionally minimal: it owns local job bookkeeping and
returns formatted strings so the CLI dispatcher and the gateway can render
them without duplicating logic.  It deliberately stops short of executing
agents — every "go" path is gated and surfaces an instructional message
until config + approval are wired.  This mirrors the local-orchestrator
contract documented in ``docs/hermes-local-orchestrator.md``: Hermes
prepares hand-off material; the user is the one who launches anything that
actually moves money, code, or messages.

Publish/remote/secret actions (``publish-plan``, ``approve``, the
``/remote-worker`` family) are explicitly gated: they refuse to advance a
job until an operator approves the phase.  The approval record lives
beside the job in ``$HERMES_HOME/orchestrator/approvals.json``.
"""

from __future__ import annotations

import json
import os
import shlex
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from hermes_cli import orchestrator_ledger as _ledger
from hermes_cli.decision_engine import (
    DecisionTier,
    merge_decision_inputs,
    owner_gate_input,
    policy_input,
)


# ---------------------------------------------------------------------------
# Storage layout
# ---------------------------------------------------------------------------

_ORCHESTRATOR_DIR_NAME = "orchestrator"
_JOBS_FILE = "jobs.json"
_LEDGER_FILE = "decision_ledger.json"
_RADAR_FILE = "ai_radar.json"
_MISSION_FILE = "best_coding_tool_mission.json"
_APPROVALS_FILE = "approvals.json"
_VALIDATION_FILE = "validation.json"
_PLANS_FILE = "publish_plans.json"
_VOICE_CAPTURE_FILE = "voice_capture.json"
_REMOTE_WORKER_FILE = "remote_workers.json"
_SELF_IMPROVE_FILE = "self_improve.json"
_PROFILE_GITHUB_HISTORY_FILE = "profile_github_history.json"

# Sentinel for actions that require explicit operator approval before
# state can transition into a "published" / "remote" / "secret-touching"
# phase.  See ``approve_phase`` and ``publish_plan``.
APPROVAL_PHASES = ("plan", "publish", "remote", "self_improve", "execute")
VOICE_CAPTURE_MODES = (
    "push_to_talk",
    "wake_word",
    "driving_capture",
    "disabled",
)


def _hermes_home() -> Path:
    """Return the active Hermes home directory.

    Imported lazily so tests that point ``HERMES_HOME`` at a tmpdir before
    importing this module still pick up the override.
    """
    try:
        from hermes_constants import get_hermes_home

        return get_hermes_home()
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))


def _orch_dir() -> Path:
    d = _hermes_home() / _ORCHESTRATOR_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Job dataclass + JSON persistence
# ---------------------------------------------------------------------------

JOB_STATUSES = (
    "queued",
    "running",
    "paused",
    "succeeded",
    "failed",
    "published",
    "cancelled",
    "plan_ready",
)


@dataclass
class Job:
    """A single orchestrator job.

    The orchestrator stores a small flat record per job.  Tool calls,
    model decisions, and validator output live in the decision ledger
    (keyed by ``job.id``).
    """

    id: str
    prompt: str
    status: str = "queued"
    created_at: int = 0
    updated_at: int = 0
    notes: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    published_at: Optional[int] = None
    resumed_count: int = 0
    cancelled_at: Optional[int] = None
    approvals: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        # Tolerate unknown keys so future schema additions don't crash
        # older readers (this file may be hand-edited).
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in data.items() if k in known}
        kwargs.setdefault("id", data.get("id") or _new_job_id())
        kwargs.setdefault("prompt", data.get("prompt") or "")
        return cls(**kwargs)


def _new_job_id() -> str:
    return f"orc-{uuid.uuid4().hex[:8]}"


_LAST_NOW = 0  # monotonic increment guard for _now() ties


def _now() -> int:
    """Return a strictly-increasing Unix time stamp (microseconds).

    Microsecond resolution + a monotonic-increment guard guarantees that
    two submissions inside the same loop tick still get distinct
    ``created_at`` values — which is what ``list_jobs`` relies on to
    order results newest-first.  Without the guard, fast scripts and
    tests can submit several jobs inside the same wall-clock tick and
    the listing order becomes implementation-defined.
    """
    global _LAST_NOW
    candidate = time.time_ns() // 1_000  # microseconds
    if candidate <= _LAST_NOW:
        candidate = _LAST_NOW + 1
    _LAST_NOW = candidate
    return candidate


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _load_jobs() -> list[Job]:
    raw = _read_json(_orch_dir() / _JOBS_FILE, default=[])
    if not isinstance(raw, list):
        return []
    jobs: list[Job] = []
    for entry in raw:
        if isinstance(entry, dict):
            try:
                jobs.append(Job.from_dict(entry))
            except Exception:
                continue
    return jobs


def _save_jobs(jobs: Iterable[Job]) -> None:
    _write_json(_orch_dir() / _JOBS_FILE, [j.to_dict() for j in jobs])


def _find_job(jobs: list[Job], job_id: str) -> Optional[Job]:
    job_id = (job_id or "").strip()
    if not job_id:
        return None
    for j in jobs:
        if j.id == job_id:
            return j
    # Allow prefix match so users can type the first few chars of a UUID.
    matches = [j for j in jobs if j.id.startswith(job_id)]
    if len(matches) == 1:
        return matches[0]
    return None


# ---------------------------------------------------------------------------
# Decision ledger
# ---------------------------------------------------------------------------
#
# Canonical store is per-job JSONL at ``~/.hermes/jobs/<job-id>/ledger.jsonl``
# (see :mod:`hermes_cli.orchestrator_ledger` and ``docs/orchestration/README.md``).
# That's the path :mod:`hermes_cli.jarvis_prime.awareness` reads when it
# builds the active-jobs panel.  Before this consolidation, writes went to
# ``~/.hermes/orchestrator/decision_ledger.json`` (a single combined dict)
# and the awareness reader saw nothing.
#
# The legacy combined file is still merged in by ``_load_ledger`` so users
# upgrading don't lose history, but no new writes go to it.


def _load_legacy_ledger() -> dict[str, list[dict[str, Any]]]:
    """Read the deprecated combined-JSON ledger if it still exists on disk.

    Returns ``{}`` when the file is absent or unreadable.  Only dict-shaped
    entries are kept (hand-edits sometimes leave stray scalars behind).
    """
    raw = _read_json(_orch_dir() / _LEDGER_FILE, default={})
    if not isinstance(raw, dict):
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for k, v in raw.items():
        if isinstance(v, list):
            result[str(k)] = [e for e in v if isinstance(e, dict)]
    return result


def _load_ledger() -> dict[str, list[dict[str, Any]]]:
    """Return ``{job_id: [entries…]}`` across the canonical + legacy stores.

    Canonical (per-job JSONL) is authoritative for new entries.  Legacy
    entries are prepended within each job so the timeline still reads
    oldest→newest.
    """
    canonical = _ledger.all_ledgers()
    legacy = _load_legacy_ledger()
    if not legacy:
        return canonical
    merged: dict[str, list[dict[str, Any]]] = {k: list(v) for k, v in canonical.items()}
    for job_id, entries in legacy.items():
        if job_id in merged:
            merged[job_id] = list(entries) + merged[job_id]
        else:
            merged[job_id] = list(entries)
    return merged


def _append_ledger(job_id: str, entry: dict[str, Any]) -> None:
    _ledger.append(job_id, entry)


# ---------------------------------------------------------------------------
# Per-job budget hard-stop (Sprint 10 wiring on the single-job path)
# ---------------------------------------------------------------------------
#
# The parallel runner (``orchestrator_parallel.ParallelRunner``) already meters
# each worker's reported ``cost_usd`` and stops launching further workers once
# the accumulated spend reaches a configured hard limit
# (``hermes_cli.budget_policy.evaluate_budget``). The single-job ``dispatch_job``
# path historically never consulted the budget — these helpers close that gap by
# reusing the *same* policy kernel with the *same* cost-extraction guards as
# ``ParallelRunner._note_cost`` / ``ParallelRunner._budget_stop_decision``.
#
# Both limits default to ``None`` everywhere (no budget configured), so the
# default dispatch path stays byte-identical — enforcement only engages when a
# caller passes an explicit limit.


def _worker_reported_cost(run_result: Any) -> float:
    """Best-effort positive ``cost_usd`` a worker reported, else ``0.0``.

    Mirrors ``ParallelRunner._note_cost``: the cost lives in the worker's
    ``WorkerRunResult.details`` mapping, either directly as ``cost_usd`` or
    nested under a ``{usage, cost_usd, ...}`` ``usage`` block (the shape a
    LOCAL_RUN worker's ``usage.json`` sidecar uses). A missing / non-numeric /
    boolean / non-positive value leaves the meter untouched — the additive,
    behavior-preserving default. Never raises.
    """

    try:
        details = getattr(run_result, "details", None)
        if not isinstance(details, dict):
            return 0.0
        cost = details.get("cost_usd")
        if cost is None:
            usage = details.get("usage")
            if isinstance(usage, dict):
                cost = usage.get("cost_usd")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost <= 0:
            return 0.0
        return float(cost)
    except Exception:
        return 0.0


def _budget_stop_for_spend(
    spent: float,
    *,
    soft_limit: Optional[float],
    hard_limit: Optional[float],
) -> Optional[Any]:
    """Return the hard-stop ``BudgetDecision`` when ``spent`` exhausts the budget.

    ``None`` when no budget is configured, the spend is still within the hard
    limit, or the budget subsystem is unavailable / errors — so a missing or
    broken budget policy never blocks (or crashes) the single-job path. Mirrors
    ``ParallelRunner._budget_stop_decision`` (same ``evaluate_budget`` call, same
    ``should_stop`` semantics).
    """

    if soft_limit is None and hard_limit is None:
        return None
    try:
        from hermes_cli.budget_policy import evaluate_budget

        decision = evaluate_budget(
            spent,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
            meter="cost",
        )
    except Exception:
        return None
    return decision if decision.should_stop else None


def _job_recorded_cost(job_id: str) -> float:
    """Sum the ``cost_usd`` recorded across a job's ledger ``worker_result``s.

    This is the single-job analogue of ``ParallelRunner._spent_usd``: each
    completed worker records its ``cost_usd`` into its ``worker_result`` entry,
    so the accrued spend is recoverable from the ledger across ``dispatch_job``
    calls. Malformed / missing values are ignored. Never raises.
    """

    total = 0.0
    try:
        entries = _load_ledger().get(job_id, [])
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("kind") != "worker_result":
                continue
            cost = entry.get("cost_usd")
            if (
                isinstance(cost, bool)
                or not isinstance(cost, (int, float))
                or cost <= 0
            ):
                continue
            total += float(cost)
    except Exception:
        return total
    return total


def _record_budget_stop(
    job_id: str, jobs: list[Job], job: Job, decision: Any
) -> None:
    """Block a job for a budget hard-stop and record it in the ledger, once.

    Sets ``job.status = "blocked"`` (the existing terminal/blocked convention)
    and appends a ``budget_stop`` ledger entry whose ``reason`` is
    ``budget_exhausted`` plus the policy's numbers/detail. Idempotent: a job
    already carrying a ``budget_stop`` entry is not re-recorded. Never raises.
    """

    try:
        existing = _load_ledger().get(job_id, [])
        already = any(
            isinstance(e, dict) and e.get("kind") == "budget_stop" for e in existing
        )
        if not already:
            _append_ledger(
                job_id,
                {
                    "kind": "budget_stop",
                    "reason": "budget_exhausted",
                    "meter": getattr(decision, "meter", "cost"),
                    "spent": getattr(decision, "spent", None),
                    "soft_limit": getattr(decision, "soft_limit", None),
                    "hard_limit": getattr(decision, "hard_limit", None),
                    "detail": getattr(decision, "detail", ""),
                },
            )
        job.status = "blocked"
        job.updated_at = _now()
        _save_jobs(jobs)
    except Exception:
        # Honesty over crashing: if persistence fails, leave the in-memory job
        # marked blocked but never raise into the dispatch caller.
        job.status = "blocked"


# ---------------------------------------------------------------------------
# Public controller API — used by both CLI and gateway dispatchers
# ---------------------------------------------------------------------------


def submit_job(prompt: str) -> Job:
    """Record a new orchestration job.

    Does **not** spawn any workers — workers require explicit configuration
    + approval (see ``docs/orchestration/orchestrator-command-reference.md``).
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("/orchestrate requires a prompt")
    job = Job(
        id=_new_job_id(),
        prompt=prompt,
        status="queued",
        created_at=_now(),
        updated_at=_now(),
    )
    jobs = _load_jobs()
    jobs.append(job)
    _save_jobs(jobs)
    # Sprint 2 breadth: attach the unified verdict to the submit entry (not a
    # separate entry, mirroring how the execute boundary records its verdict on
    # the worker entry). Submitting a job records intent only — no worker runs,
    # no owner-gated action is taken — so the verdict is `auto`. Recorded, not
    # gating: this does not change that the job is queued.
    submit_verdict = merge_decision_inputs(
        "orchestrator.submit_job",
        [policy_input(DecisionTier.AUTO, "job queued; no action taken")],
    )
    _append_ledger(
        job.id,
        {
            "kind": "submit",
            "prompt": prompt,
            "decision_verdict": submit_verdict.to_redacted_dict(),
        },
    )
    return job


def navigate_job(
    job_id: str,
    *,
    repo_root: Optional[str] = None,
    issue: Optional[str] = None,
    limit: int = 5,
) -> Optional[dict[str, Any]]:
    """Localize a job's objective in the repo **before** dispatching a worker.

    This is the navigator → orchestrator integration point. It builds the
    HyperAgent-style :class:`~hermes_cli.jarvis_prime.navigation.Navigator`,
    ranks likely edit sites for the job's objective, records a
    ``navigation_decision`` entry in the job ledger, and returns the worker
    packet. It is **best-effort and read-only** — it never edits the repo and
    never blocks dispatch: a navigation failure is logged and ``None`` is
    returned so the caller can proceed.
    """

    job = get_job(job_id)
    objective = (issue or (job.prompt if job else "") or "").strip()
    if not objective:
        return None
    try:
        from hermes_cli.jarvis_prime.navigation import Navigator

        nav = Navigator.for_repo(repo_root or Path.cwd())
        result = nav.navigate(objective, limit=limit)
    except Exception as exc:  # best-effort: navigation never blocks dispatch
        _append_ledger(job_id, {"kind": "navigation_error", "error": str(exc)})
        return None
    _append_ledger(job_id, result.to_ledger_record(job_id=job_id))
    return result.worker_packet()


def dispatch_job(
    job_id: str,
    *,
    worker_id: str = "hermes-local-planner",
    repo_root: Optional[str] = None,
    budget_soft_limit: Optional[float] = None,
    budget_hard_limit: Optional[float] = None,
) -> Optional[Job]:
    """Dispatch a job to a worker via the five-step adapter contract.

    Runs ``detect → prepare_prompt → run → collect → score`` and records a
    ``worker_dispatch`` / ``worker_result`` / ``worker_score`` trail in the
    job ledger (visible via ``/orchestrator replay``). The built-in
    ``hermes-local-planner`` is non-destructive (read-only navigation; no edits,
    no shell) and runs ungated; it makes the engine verifiable end-to-end.
    Repo-mutating / external workers implement the same contract but require an
    approved ``execute`` phase first (the owner gate is never bypassed).

    Per-job budget hard-stop: pass ``budget_hard_limit`` (USD) to meter the
    worker's reported ``cost_usd`` and, once the accrued spend reaches the hard
    limit, stop the job with status ``"blocked"`` and a ``budget_stop`` ledger
    entry (reason ``budget_exhausted``) — the same policy kernel and
    ``should_stop`` semantics the parallel runner uses
    (:func:`hermes_cli.budget_policy.evaluate_budget`). Both limits default to
    ``None`` (no budget configured), so the default dispatch path is unchanged.
    The budget check is wrapped defensively and never raises.

    Best-effort: an unknown/unavailable worker or a worker error is recorded
    and the job is left in an honest state — never raised to the caller.
    """
    jobs = _load_jobs()
    job = _find_job(jobs, job_id)
    if not job:
        return None

    # Budget hard-stop, pre-dispatch (mirrors ParallelRunner gating each launch):
    # if a configured hard budget is *already* exhausted by prior workers'
    # recorded cost, refuse to launch the next worker. No-op when no budget is
    # configured (both limits None) — the default path is unaffected. Never raises.
    if budget_soft_limit is not None or budget_hard_limit is not None:
        prior_stop = _budget_stop_for_spend(
            _job_recorded_cost(job_id),
            soft_limit=budget_soft_limit,
            hard_limit=budget_hard_limit,
        )
        if prior_stop is not None:
            _record_budget_stop(job_id, jobs, job, prior_stop)
            return job

    # Ensure the built-in adapters are registered (they self-register on import).
    from hermes_cli.workers import builtin_worker_classes, load_builtins
    from hermes_cli.workers import registry as _wr

    load_builtins()
    # The built-in adapters are repo-aware; bind them to the requested root.
    _repo_aware = {cls.id: cls for cls in builtin_worker_classes()}
    if worker_id in _repo_aware:
        adapter: Any = _repo_aware[worker_id](repo_root)
    else:
        try:
            adapter = _wr.get(worker_id)
        except Exception:
            _append_ledger(
                job_id,
                {
                    "kind": "worker_error",
                    "worker_id": worker_id,
                    "error": "unknown worker",
                },
            )
            return job

    # Owner gate: a worker that mutates the repo / runs external tools declares
    # `requires_approval = True` (the safe default). It may only run once the
    # 'execute' phase is approved. Non-destructive workers (the local planner,
    # handoff workers) opt out via `requires_approval = False`. Never bypass.
    requires_approval = bool(getattr(adapter, "requires_approval", True))
    needs_owner = requires_approval and not has_approval(job, "execute")
    # Unified decision verdict for the execute boundary (Sprint 2 wiring):
    # compose the owner gate into one auto/ask/refuse verdict the cockpit can
    # render. Behavior-preserving — the block below fires on the same condition.
    execute_verdict = merge_decision_inputs(
        "orchestrator.worker_execute",
        [owner_gate_input(needs_owner, action=f"worker {worker_id} execute")],
    )
    if needs_owner:
        _append_ledger(
            job_id,
            {
                "kind": "worker_blocked",
                "worker_id": worker_id,
                "reason": "execute phase requires owner approval",
                "decision_verdict": execute_verdict.to_redacted_dict(),
            },
        )
        job.status = "blocked"
        job.updated_at = _now()
        _save_jobs(jobs)
        return job

    detection = adapter.detect()
    _append_ledger(
        job_id,
        {
            "kind": "worker_dispatch",
            "worker_id": worker_id,
            "available": bool(detection.available),
            "reason": detection.reason,
            "decision_verdict": execute_verdict.to_redacted_dict(),
        },
    )
    if not detection.available:
        job.status = "blocked"
        job.updated_at = _now()
        _save_jobs(jobs)
        return job

    try:
        adapter.prepare_prompt(job)
        run_result = adapter.run(job)
        artifacts = adapter.collect(job)
        score = adapter.score(artifacts)
    except Exception as exc:  # best-effort: a worker error never crashes dispatch
        _append_ledger(
            job_id,
            {
                "kind": "worker_error",
                "worker_id": worker_id,
                "error": str(exc),
            },
        )
        job.status = "failed"
        job.updated_at = _now()
        _save_jobs(jobs)
        return job

    # Meter this worker's reported cost (same extraction guards as the parallel
    # runner). 0.0 when the worker reported no usage — the additive default.
    worker_cost = _worker_reported_cost(run_result)
    _append_ledger(
        job_id,
        {
            "kind": "worker_result",
            "worker_id": worker_id,
            "ok": bool(run_result.ok),
            "summary": (run_result.stdout or "")[:500],
            "error": run_result.error,
            # Recorded so the pre-dispatch budget guard can sum prior spend on a
            # later dispatch. Always present (0.0 when no usage) — purely additive.
            "cost_usd": worker_cost,
        },
    )
    _append_ledger(
        job_id,
        {
            "kind": "worker_score",
            "worker_id": worker_id,
            "value": round(float(score.value), 4),
            "rationale": score.rationale,
            "files": list(artifacts.files),
        },
    )
    for f in artifacts.files:
        if f not in job.artifacts:
            job.artifacts.append(f)
    job.status = "completed" if run_result.ok else "failed"
    job.updated_at = _now()
    _save_jobs(jobs)

    # Budget hard-stop, post-result (mirrors ParallelRunner metering each
    # completed worker's cost then halting before the next launch): if the
    # accrued spend now reaches the configured hard limit, mark the job blocked
    # and record the stop *before* any next worker can be dispatched. No-op when
    # no budget is configured. Never raises — a budget-subsystem error logs via
    # the ledger nowhere and simply leaves the job's honest terminal status.
    if budget_soft_limit is not None or budget_hard_limit is not None:
        stop = _budget_stop_for_spend(
            _job_recorded_cost(job_id),
            soft_limit=budget_soft_limit,
            hard_limit=budget_hard_limit,
        )
        if stop is not None:
            _record_budget_stop(job_id, jobs, job, stop)
    return job


def list_jobs(limit: int = 25) -> list[Job]:
    jobs = _load_jobs()
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return jobs[: max(1, int(limit))]


def get_job(job_id: str) -> Optional[Job]:
    return _find_job(_load_jobs(), job_id)


def resume_job(job_id: str) -> Optional[Job]:
    jobs = _load_jobs()
    job = _find_job(jobs, job_id)
    if not job:
        return None
    job.status = "queued" if job.status in {"paused", "failed"} else job.status
    job.resumed_count += 1
    job.updated_at = _now()
    _save_jobs(jobs)
    _append_ledger(job.id, {"kind": "resume", "status": job.status})
    return job


def publish_job(job_id: str) -> Optional[Job]:
    jobs = _load_jobs()
    job = _find_job(jobs, job_id)
    if not job:
        return None
    job.status = "published"
    job.published_at = _now()
    job.updated_at = _now()
    _save_jobs(jobs)
    _append_ledger(job.id, {"kind": "publish"})
    return job


def get_ledger(job_id: Optional[str] = None) -> dict[str, list[dict[str, Any]]]:
    ledger = _load_ledger()
    if not job_id:
        return ledger
    job = get_job(job_id)
    if not job:
        return {}
    return {job.id: ledger.get(job.id, [])}


# ---------------------------------------------------------------------------
# Cancel / approve / validate / publish-plan
# ---------------------------------------------------------------------------


def cancel_job(job_id: str) -> Optional[Job]:
    """Mark a job as cancelled.

    Cancellation is a one-way state — a cancelled job can still be inspected
    via ``/orchestrator open`` but it will not auto-resume.  Already-published
    jobs are left alone so the publish record stays honest.
    """
    jobs = _load_jobs()
    job = _find_job(jobs, job_id)
    if not job:
        return None
    if job.status == "published":
        # Refuse to retract a publish through ``cancel``.  Publish is an
        # external commitment; the caller should issue a follow-up instead.
        return job
    job.status = "cancelled"
    job.cancelled_at = _now()
    job.updated_at = _now()
    _save_jobs(jobs)
    _append_ledger(job.id, {"kind": "cancel", "status": job.status})
    return job


def approve_phase(job_id: str, phase: str) -> Optional[Job]:
    """Record an operator approval for a publish/remote/secret phase.

    Approval is required before ``publish_plan`` will actually emit a
    publish-plan, before ``self_improve_run`` will accept a job id, and
    before ``/remote-worker`` may dispatch any work.  The approval record
    is kept on the job so the decision ledger reflects who/when.
    """
    phase = (phase or "").strip()
    if phase not in APPROVAL_PHASES:
        raise ValueError(
            f"unknown approval phase {phase!r}; "
            f"expected one of {', '.join(APPROVAL_PHASES)}"
        )
    jobs = _load_jobs()
    job = _find_job(jobs, job_id)
    if not job:
        return None
    job.approvals = dict(job.approvals or {})
    job.approvals[phase] = _now()
    job.updated_at = _now()
    _save_jobs(jobs)
    _append_ledger(job.id, {"kind": "approve", "phase": phase})
    return job


def has_approval(job: Job, phase: str) -> bool:
    return bool((job.approvals or {}).get(phase))


def validate_job(job_id: str) -> Optional[dict[str, Any]]:
    """Run the local validation gate against the workspace for *job_id*.

    Persists a compact summary under
    ``$HERMES_HOME/orchestrator/validation.json`` keyed by job id, and
    appends a ``validate`` entry to the decision ledger.  Returns ``None``
    when *job_id* is unknown.  Falls back to a static skeleton when the
    validation runner module is unavailable so the slash command still
    surfaces useful state in stripped-down environments.
    """
    job = get_job(job_id)
    if not job:
        return None
    summary: dict[str, Any]
    try:
        from hermes_cli.validation import ValidationRunner

        # Route the runner's artefact writes (validation/results.json,
        # validation/summary.md, validation/commands.log) into the
        # orchestrator's own per-job folder rather than the user's cwd
        # so we never leave a stray validation/ directory in the
        # workspace they're currently editing.
        per_job_dir = _orch_dir() / "validation" / job.id
        per_job_dir.mkdir(parents=True, exist_ok=True)
        runner = ValidationRunner(
            workspace=str(Path.cwd()),
            output_dir=str(per_job_dir),
        )
        report = runner.run()
        # ValidationReport.to_dict() is the documented contract.
        report_dict = report.to_dict() if hasattr(report, "to_dict") else {}
        status_counts = (
            report.status_counts() if hasattr(report, "status_counts") else {}
        )
        summary = {
            "job_id": job.id,
            "checked_at": _now(),
            "status_counts": status_counts,
            "checks": report_dict.get("checks") or [],
            "publish_blocked": any(
                c.get("status") == "fail" and c.get("critical")
                for c in (report_dict.get("checks") or [])
            ),
        }
    except Exception as exc:
        # The runner is best-effort: a stripped-down test environment may
        # be missing ``hermes_cli.validation``.  Surface a skeleton record
        # so users still see the dispatch and timestamp.
        summary = {
            "job_id": job.id,
            "checked_at": _now(),
            "status_counts": {},
            "checks": [],
            "publish_blocked": False,
            "note": f"validation runner unavailable: {exc!s}",
        }
    all_validations = _read_json(_orch_dir() / _VALIDATION_FILE, default={})
    if not isinstance(all_validations, dict):
        all_validations = {}
    all_validations[job.id] = summary
    _write_json(_orch_dir() / _VALIDATION_FILE, all_validations)
    _append_ledger(
        job.id,
        {
            "kind": "validate",
            "status_counts": summary.get("status_counts", {}),
            "publish_blocked": summary.get("publish_blocked", False),
        },
    )
    return summary


def publish_plan(job_id: str) -> dict[str, Any]:
    """Emit a publish-plan for the job — *only* after ``approve plan``.

    Publish-plans live under
    ``$HERMES_HOME/orchestrator/publish_plans.json``.  This is the
    last gate before a workflow can hand artefacts off to a downstream
    publisher (PR, kanban, GitHub release, etc.).  Without approval, the
    function returns ``{"ok": False, "reason": "approval required"}``
    and writes nothing.
    """
    job = get_job(job_id)
    if not job:
        return {"ok": False, "reason": f"unknown job id {job_id!r}"}
    if not has_approval(job, "plan"):
        return {
            "ok": False,
            "reason": (
                "publish-plan requires prior approval — "
                f"run /orchestrator approve {job.id} plan first"
            ),
            "job_id": job.id,
        }
    validations = _read_json(_orch_dir() / _VALIDATION_FILE, default={})
    val_summary = validations.get(job.id) if isinstance(validations, dict) else None
    if val_summary and val_summary.get("publish_blocked"):
        return {
            "ok": False,
            "reason": "publish-plan blocked by failing validation checks",
            "job_id": job.id,
        }
    plans = _read_json(_orch_dir() / _PLANS_FILE, default={})
    if not isinstance(plans, dict):
        plans = {}
    plan = {
        "job_id": job.id,
        "prompt": job.prompt,
        "created_at": _now(),
        "approvals": dict(job.approvals or {}),
        "artifacts": list(job.artifacts or []),
        "validation": val_summary,
        # The plan is local-only.  Downstream publishers (kanban, github
        # publisher, hermes-local-orchestrator clipboard handoff) decide
        # what to do with the artifacts list; we never push.
        "next_step": (
            "Hand off this plan to the github_publisher plugin or your "
            "preferred publisher."
        ),
    }
    plans[job.id] = plan
    _write_json(_orch_dir() / _PLANS_FILE, plans)
    _append_ledger(job.id, {"kind": "publish-plan"})
    # Bump status so listings reflect the readiness.
    jobs = _load_jobs()
    real_job = _find_job(jobs, job.id)
    if real_job and real_job.status not in {"published", "cancelled"}:
        real_job.status = "plan_ready"
        real_job.updated_at = _now()
        _save_jobs(jobs)
    return {"ok": True, "plan": plan}


# ---------------------------------------------------------------------------
# Voice capture state
# ---------------------------------------------------------------------------


def _default_voice_capture_state() -> dict[str, Any]:
    return {
        "mode": "disabled",
        "updated_at": 0,
        "history": [],
    }


def voice_capture_status() -> dict[str, Any]:
    raw = _read_json(
        _orch_dir() / _VOICE_CAPTURE_FILE, default=_default_voice_capture_state()
    )
    if not isinstance(raw, dict):
        return _default_voice_capture_state()
    raw.setdefault("mode", "disabled")
    raw.setdefault("updated_at", 0)
    raw.setdefault("history", [])
    return raw


def set_voice_capture_mode(mode: str) -> dict[str, Any]:
    mode = (mode or "").strip().lower()
    if mode not in VOICE_CAPTURE_MODES:
        raise ValueError(
            f"unknown voice-capture mode {mode!r}; "
            f"expected one of {', '.join(VOICE_CAPTURE_MODES)}"
        )
    state = voice_capture_status()
    previous = state.get("mode", "disabled")
    state["mode"] = mode
    state["updated_at"] = _now()
    history = list(state.get("history") or [])
    history.append({"ts": state["updated_at"], "from": previous, "to": mode})
    state["history"] = history[-25:]
    _write_json(_orch_dir() / _VOICE_CAPTURE_FILE, state)
    return state


# ---------------------------------------------------------------------------
# Remote-worker status
# ---------------------------------------------------------------------------


def remote_worker_status() -> dict[str, Any]:
    """Return a snapshot of registered remote workers.

    Reads the local registry under
    ``$HERMES_HOME/orchestrator/remote_workers.json``.  When the registry
    is empty (the common case in a fresh checkout), returns a single
    placeholder entry so users can confirm the file path and update flow.
    """
    raw = _read_json(_orch_dir() / _REMOTE_WORKER_FILE, default=None)
    if not isinstance(raw, dict) or not raw.get("workers"):
        return {
            "workers": [],
            "note": (
                "No remote workers registered.  Drop entries under "
                "orchestrator.remote_workers in config.yaml or hand-edit "
                f"{_orch_dir() / _REMOTE_WORKER_FILE} to populate."
            ),
            "checked_at": _now(),
        }
    workers = raw.get("workers") or []
    return {
        "workers": workers,
        "checked_at": _now(),
    }


# ---------------------------------------------------------------------------
# Self-improve
# ---------------------------------------------------------------------------


def self_improve_run(job_id: str) -> dict[str, Any]:
    """Record a request to run the self-improvement loop against *job_id*.

    Requires ``approve <job-id> self_improve`` first because the loop
    mutates the local skill library — it must not be invoked silently.
    Stores the request under
    ``$HERMES_HOME/orchestrator/self_improve.json``.
    """
    job = get_job(job_id)
    if not job:
        return {"ok": False, "reason": f"unknown job id {job_id!r}"}
    if not has_approval(job, "self_improve"):
        return {
            "ok": False,
            "job_id": job.id,
            "reason": (
                "/self-improve run requires approval — "
                f"run /orchestrator approve {job.id} self_improve first"
            ),
        }
    history = _read_json(_orch_dir() / _SELF_IMPROVE_FILE, default={})
    if not isinstance(history, dict):
        history = {}
    runs = list(history.get(job.id) or [])
    record = {
        "ts": _now(),
        "job_id": job.id,
        # The self-improvement loop is invoked via the
        # ``self-improvement-loop`` skill; this command only stages
        # the request so the loop can pick it up next time it runs.
        "status": "requested",
        "next_step": (
            "Invoke /self-improvement-loop in an interactive session, "
            "or wait for the background curator to pick this request up."
        ),
    }
    runs.append(record)
    history[job.id] = runs[-25:]
    _write_json(_orch_dir() / _SELF_IMPROVE_FILE, history)
    _append_ledger(job.id, {"kind": "self-improve", "status": "requested"})
    return {"ok": True, "record": record}


# ---------------------------------------------------------------------------
# Profile: build GitHub history
# ---------------------------------------------------------------------------


def profile_build_github_history() -> dict[str, Any]:
    """Refresh the local profile's GitHub history snapshot.

    The CLI surface is a placeholder for the heavier history-mining flow
    in the ``github_assistant`` plugin: it stamps a local JSON file under
    ``$HERMES_HOME/orchestrator/profile_github_history.json`` so users
    can verify dispatch + filesystem access.  Wire a real walk by
    setting ``profile.github_history.feed`` in ``config.yaml``.
    """
    try:
        from hermes_cli.profiles import get_active_profile_name

        profile_name = get_active_profile_name()
    except Exception:
        profile_name = "default"
    payload = {
        "profile": profile_name,
        "built_at": _now(),
        "source": "manual /profile build-github-history",
        "note": (
            "Local placeholder.  Wire a real GitHub history walk via the "
            "github_assistant plugin or set "
            "profile.github_history.feed in config.yaml."
        ),
    }
    _write_json(_orch_dir() / _PROFILE_GITHUB_HISTORY_FILE, payload)
    return payload


def profile_github_history_status() -> dict[str, Any]:
    return _read_json(
        _orch_dir() / _PROFILE_GITHUB_HISTORY_FILE, default={"built_at": 0}
    )


# ---------------------------------------------------------------------------
# Model router — explain-only stub
# ---------------------------------------------------------------------------

_ROUTING_RULES: tuple[tuple[str, str, str], ...] = (
    # (keyword, route, rationale)
    ("review", "reviewer-profile", "code review prompts go to the reviewer profile"),
    ("debug", "debug-profile", "debugging prompts go to the debug profile"),
    ("refactor", "builder-profile", "refactor prompts go to the builder profile"),
    ("design", "architect-profile", "architecture prompts go to the architect profile"),
    ("plan", "planner-profile", "planning prompts go to the planner profile"),
    ("test", "tester-profile", "testing prompts go to the tester profile"),
    ("doc", "writer-profile", "documentation prompts go to the writer profile"),
)


def model_router_explain(prompt: str) -> dict[str, Any]:
    """Return the routing decision Hermes would make for *prompt*.

    This is an explain-only surface — the CLI does **not** actually flip
    the live model.  Use ``/model`` for that.
    """
    text = (prompt or "").lower()
    matched: list[tuple[str, str]] = []
    for kw, route, rationale in _ROUTING_RULES:
        if kw in text:
            matched.append((route, rationale))
    if not matched:
        return {
            "route": "default-profile",
            "rationale": "no routing keywords matched; falling back to the active profile",
            "matched_keywords": [],
        }
    return {
        "route": matched[0][0],
        "rationale": matched[0][1],
        "matched_keywords": [route for route, _ in matched],
    }


# ---------------------------------------------------------------------------
# AI radar
# ---------------------------------------------------------------------------


def ai_radar_update() -> dict[str, Any]:
    """Record a manual AI-radar refresh and return the new snapshot.

    The real radar pipeline pulls model/provider news from external feeds.
    The CLI surface here just stamps the local file so users can verify
    the orchestrator can write to its own home and the rest of the
    pipeline is reachable.
    """
    path = _orch_dir() / _RADAR_FILE
    payload = {
        "updated_at": _now(),
        "source": "manual /ai-radar update",
        "note": (
            "Local placeholder.  Wire a real feed by setting "
            "orchestrator.ai_radar.feed_url in config.yaml."
        ),
    }
    _write_json(path, payload)
    return payload


def ai_radar_status() -> dict[str, Any]:
    return _read_json(_orch_dir() / _RADAR_FILE, default={"updated_at": 0})


# ---------------------------------------------------------------------------
# "Best coding tool" mission
# ---------------------------------------------------------------------------


def best_coding_tool_mission_status() -> dict[str, Any]:
    """Return the mission status snapshot.

    Mission state is read-only via this command — the orchestrator
    updates it as part of its evaluation runs.  Users can edit the file
    manually under ``$HERMES_HOME/orchestrator/best_coding_tool_mission.json``.
    """
    default = {
        "mission": "Make muse the best coding tool for the user's day-to-day work.",
        "metrics": {
            "jobs_submitted": 0,
            "jobs_published": 0,
            "jobs_resumed": 0,
        },
        "next_actions": [
            "Submit a real prompt with /orchestrate <prompt>.",
            "Review the decision ledger with /decision-ledger show.",
        ],
    }
    snapshot = _read_json(_orch_dir() / _MISSION_FILE, default=default)
    # Refresh metrics from live job data so the snapshot is honest even
    # if no-one has hand-edited the JSON file.
    jobs = _load_jobs()
    if isinstance(snapshot, dict):
        snapshot.setdefault("metrics", {})
        snapshot["metrics"].update({
            "jobs_submitted": len(jobs),
            "jobs_published": sum(1 for j in jobs if j.status == "published"),
            "jobs_resumed": sum(j.resumed_count for j in jobs),
        })
    return snapshot if isinstance(snapshot, dict) else default


# ---------------------------------------------------------------------------
# Formatting helpers (used by run_slash + cli.py + gateway/run.py)
# ---------------------------------------------------------------------------


def _fmt_ts(ts: Any) -> str:
    """Render a timestamp for display.

    Accepts the historical formats this code base emits:
      * ``None`` / ``0`` / ``""`` — placeholder ``"—"``
      * ``int`` (microseconds since epoch — ``_now()``'s native format)
      * ``str`` (ISO-8601, e.g. ledger entries from ``orchestrator_ledger``)
    """
    if not ts:
        return "—"
    if isinstance(ts, str):
        from datetime import datetime

        try:
            return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return ts
    # ``_now()`` returns microseconds; convert before handing it to
    # ``time.localtime`` which expects seconds.
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts) / 1_000_000.0))


def _fmt_job_line(job: Job) -> str:
    head = job.prompt.splitlines()[0] if job.prompt else ""
    if len(head) > 72:
        head = head[:69] + "..."
    return f"  {job.id}  {job.status:10s}  {_fmt_ts(job.updated_at)}  {head}"


def _fmt_job_detail(job: Job) -> str:
    lines = [
        f"job:        {job.id}",
        f"status:     {job.status}",
        f"created:    {_fmt_ts(job.created_at)}",
        f"updated:    {_fmt_ts(job.updated_at)}",
        f"resumes:    {job.resumed_count}",
        f"published:  {_fmt_ts(job.published_at) if job.published_at else 'no'}",
        "prompt:",
    ]
    lines.extend(f"  {ln}" for ln in (job.prompt or "").splitlines() or [""])
    if job.notes:
        lines.append("notes:")
        lines.extend(f"  • {n}" for n in job.notes)
    if job.artifacts:
        lines.append("artifacts:")
        lines.extend(f"  • {a}" for a in job.artifacts)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Help blocks (mirrors the kanban run_slash pattern)
# ---------------------------------------------------------------------------

_ORCHESTRATE_HELP = (
    "Usage: /orchestrate <prompt>\n"
    "\n"
    "Records a new orchestration job and assigns it an id.\n"
    "The orchestrator does NOT auto-execute workers — see\n"
    "/orchestrator status <id> to inspect, /orchestrator publish <id>\n"
    "to mark the result as published.\n"
)


_ORCHESTRATOR_HELP = (
    "Usage: /orchestrator <subcommand> [args]\n"
    "\n"
    "Subcommands:\n"
    "  status [job-id]               Show status of one job (or every job).\n"
    "  list                          List recent jobs.\n"
    "  open <job-id>                 Print a job's full record.\n"
    "  dispatch <job-id> [worker]    Run a worker on a job (default: local planner).\n"
    "  replay <job-id>               Replay a job's decision ledger (read-only).\n"
    "  resume <job-id>               Re-queue a paused or failed job.\n"
    "  cancel <job-id>               Mark a job as cancelled.\n"
    "  approve <job-id> <phase>      Approve a publish/remote/secret phase.\n"
    "  validate <job-id>             Run local validation gates for a job.\n"
    "  publish <job-id>              Mark a job as published.\n"
    "  publish-plan <job-id>         Emit a publish-plan (requires approval).\n"
)


_MODEL_ROUTER_HELP = (
    "Usage: /model-router explain <prompt>\n"
    "\n"
    "Explains which model/profile muse would route a prompt to.\n"
    "This is an explain-only surface — use /model to actually switch.\n"
)


_DECISION_LEDGER_HELP = (
    "Usage: /decision-ledger show [job-id]\n"
    "\n"
    "Show the decision ledger (submit/resume/publish events, plus any\n"
    "entries written by the orchestrator) for one job or every job.\n"
)


_AI_RADAR_HELP = "Usage: /ai-radar update\n\nRefresh the local AI-radar snapshot.\n"


_MISSION_HELP = (
    "Usage: /best-coding-tool-mission status\n"
    "\n"
    "Show the orchestrator's running mission summary and live metrics.\n"
)


_VOICE_CAPTURE_HELP = (
    "Usage: /voice-capture <subcommand> [args]\n"
    "\n"
    "Subcommands:\n"
    "  status                        Show the current voice-capture state.\n"
    "  mode <mode>                   Set the capture mode.  Modes:\n"
    "                                  push_to_talk, wake_word,\n"
    "                                  driving_capture, disabled.\n"
)


_REMOTE_WORKER_HELP = (
    "Usage: /remote-worker status\n"
    "\n"
    "Show the local snapshot of registered remote workers.  Remote workers\n"
    "must be approved per-job before they can pick up work — see\n"
    "/orchestrator approve <job-id> remote.\n"
)


_SELF_IMPROVE_HELP = (
    "Usage: /self-improve run <job-id>\n"
    "\n"
    "Stage a self-improvement-loop request for *job-id*.  Requires prior\n"
    "/orchestrator approve <job-id> self_improve.  The loop itself is\n"
    "invoked by the self-improvement-loop skill — this command only\n"
    "records the request so the loop knows what job to target.\n"
)


_PROFILE_HELP = (
    "Usage: /profile [subcommand]\n"
    "\n"
    "With no subcommand, /profile shows the active profile name and home.\n"
    "Subcommands:\n"
    "  build-github-history          Refresh the local GitHub-history\n"
    "                                snapshot for the active profile.\n"
)


# ---------------------------------------------------------------------------
# Slash dispatchers
# ---------------------------------------------------------------------------


def run_orchestrate(rest: str) -> str:
    """Handle ``/orchestrate <prompt>``."""
    prompt = (rest or "").strip()
    if not prompt or prompt in {"-h", "--help", "?"}:
        return _ORCHESTRATE_HELP
    try:
        job = submit_job(prompt)
    except ValueError as exc:
        return f"⚠ {exc}\n{_ORCHESTRATE_HELP}"
    # Navigate before dispatch: localize the objective in the repo and record a
    # navigation_decision in the job ledger (HyperAgent-style, deterministic,
    # read-only, best-effort — never blocks the queue).
    nav_line = ""
    packet = navigate_job(job.id, issue=prompt)
    if packet:
        files = packet.get("candidate_files") or []
        if files:
            nav_line = (
                f"\n  navigation:  {len(files)} candidate file(s) — top: {files[0]}"
            )
    return (
        f"✓ Orchestration job queued: {job.id}\n"
        f"  status:  {job.status}\n"
        f"  prompt:  {job.prompt[:120]}{'...' if len(job.prompt) > 120 else ''}"
        f"{nav_line}\n"
        f"\n"
        f"No worker has started.  Use /orchestrator status {job.id} to inspect."
    )


def _run_orchestrator_status(args: list[str]) -> str:
    if args:
        job = get_job(args[0])
        if not job:
            return f"⚠ /orchestrator: unknown job id {args[0]!r}"
        return _fmt_job_detail(job)
    jobs = list_jobs()
    if not jobs:
        return "  (no jobs yet — use /orchestrate <prompt>)"
    lines = [f"  Orchestrator status — {len(jobs)} job(s)"]
    lines.extend(_fmt_job_line(j) for j in jobs)
    return "\n".join(lines)


def _run_orchestrator_list(_args: list[str]) -> str:
    jobs = list_jobs()
    if not jobs:
        return "  (no jobs yet — use /orchestrate <prompt>)"
    lines = [f"  Recent orchestrator jobs ({len(jobs)}):"]
    lines.extend(_fmt_job_line(j) for j in jobs)
    return "\n".join(lines)


def _run_orchestrator_open(args: list[str]) -> str:
    if not args:
        return "⚠ /orchestrator open requires a job id"
    job = get_job(args[0])
    if not job:
        return f"⚠ /orchestrator: unknown job id {args[0]!r}"
    return _fmt_job_detail(job)


def _run_orchestrator_dispatch(args: list[str]) -> str:
    """Dispatch a job to a worker (defaults to the built-in local planner)."""
    if not args:
        return "⚠ /orchestrator dispatch requires a job id"
    job_id = args[0]
    worker_id = args[1] if len(args) > 1 else "hermes-local-planner"
    job = dispatch_job(job_id, worker_id=worker_id)
    if not job:
        return f"⚠ /orchestrator: unknown job id {job_id!r}"
    return _fmt_job_detail(job)


def _run_orchestrator_replay(args: list[str]) -> str:
    """Replay a job's decision ledger, read-only — navigation, dispatches,
    validation gates, repair-loop steps, in order."""
    if not args:
        return "⚠ /orchestrator replay requires a job id"
    job = get_job(args[0])
    if not job:
        return f"⚠ /orchestrator: unknown job id {args[0]!r}"
    from hermes_cli.orchestrator_replay import JobReplay

    replay = JobReplay.load(job.id)
    if replay.is_empty:
        return f"  (no ledger entries for {job.id})"
    return replay.render()


def _run_orchestrator_resume(args: list[str]) -> str:
    if not args:
        return "⚠ /orchestrator resume requires a job id"
    job = resume_job(args[0])
    if not job:
        return f"⚠ /orchestrator: unknown job id {args[0]!r}"
    return (
        f"✓ Job {job.id} re-queued (status={job.status}, resumes={job.resumed_count})."
    )


def _run_orchestrator_publish(args: list[str]) -> str:
    if not args:
        return "⚠ /orchestrator publish requires a job id"
    job = publish_job(args[0])
    if not job:
        return f"⚠ /orchestrator: unknown job id {args[0]!r}"
    return f"✓ Job {job.id} marked published at {_fmt_ts(job.published_at)}."


def _run_orchestrator_cancel(args: list[str]) -> str:
    if not args:
        return "⚠ /orchestrator cancel requires a job id"
    job = cancel_job(args[0])
    if not job:
        return f"⚠ /orchestrator: unknown job id {args[0]!r}"
    if job.status != "cancelled":
        return (
            f"⚠ Job {job.id} is {job.status} and cannot be cancelled "
            f"through /orchestrator cancel."
        )
    return f"✓ Job {job.id} cancelled at {_fmt_ts(job.cancelled_at)}."


def _run_orchestrator_approve(args: list[str]) -> str:
    if len(args) < 2:
        return (
            "⚠ /orchestrator approve requires <job-id> <phase>\n"
            f"  Phases: {', '.join(APPROVAL_PHASES)}"
        )
    job_id, phase = args[0], args[1]
    try:
        job = approve_phase(job_id, phase)
    except ValueError as exc:
        return f"⚠ /orchestrator approve: {exc}"
    if not job:
        return f"⚠ /orchestrator: unknown job id {job_id!r}"
    return (
        f"✓ Job {job.id} approved for phase '{phase}' at "
        f"{_fmt_ts(job.approvals.get(phase))}."
    )


def _run_orchestrator_validate(args: list[str]) -> str:
    if not args:
        return "⚠ /orchestrator validate requires a job id"
    summary = validate_job(args[0])
    if summary is None:
        return f"⚠ /orchestrator: unknown job id {args[0]!r}"
    counts = summary.get("status_counts") or {}
    count_line = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "—"
    blocked = "yes" if summary.get("publish_blocked") else "no"
    lines = [
        f"  job:              {summary.get('job_id')}",
        f"  checked_at:       {_fmt_ts(summary.get('checked_at'))}",
        f"  status_counts:    {count_line}",
        f"  publish_blocked:  {blocked}",
    ]
    if summary.get("note"):
        lines.append(f"  note:             {summary['note']}")
    return "\n".join(lines)


def _run_orchestrator_publish_plan(args: list[str]) -> str:
    if not args:
        return "⚠ /orchestrator publish-plan requires a job id"
    result = publish_plan(args[0])
    if not result.get("ok"):
        return f"⚠ /orchestrator publish-plan: {result.get('reason')}"
    plan = result.get("plan") or {}
    artifacts = plan.get("artifacts") or []
    lines = [
        f"✓ Publish-plan emitted for {plan.get('job_id')}",
        f"  created_at:  {_fmt_ts(plan.get('created_at'))}",
        f"  approvals:   {', '.join(sorted((plan.get('approvals') or {}).keys())) or '—'}",
        f"  artifacts:   {len(artifacts)}",
        f"  next_step:   {plan.get('next_step')}",
    ]
    return "\n".join(lines)


_ORCHESTRATOR_SUBCOMMANDS: dict[str, Any] = {
    "status": _run_orchestrator_status,
    "list": _run_orchestrator_list,
    "open": _run_orchestrator_open,
    "dispatch": _run_orchestrator_dispatch,
    "replay": _run_orchestrator_replay,
    "resume": _run_orchestrator_resume,
    "cancel": _run_orchestrator_cancel,
    "approve": _run_orchestrator_approve,
    "validate": _run_orchestrator_validate,
    "publish": _run_orchestrator_publish,
    "publish-plan": _run_orchestrator_publish_plan,
}


def run_orchestrator(rest: str) -> str:
    """Handle ``/orchestrator <subcommand> [args]``."""
    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _ORCHESTRATOR_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /orchestrator: {exc}\n{_ORCHESTRATOR_HELP}"
    sub, *args = tokens
    handler = _ORCHESTRATOR_SUBCOMMANDS.get(sub)
    if not handler:
        return f"⚠ /orchestrator: unknown subcommand {sub!r}\n{_ORCHESTRATOR_HELP}"
    return handler(args)


def run_model_router(rest: str) -> str:
    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _MODEL_ROUTER_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /model-router: {exc}\n{_MODEL_ROUTER_HELP}"
    sub, *args = tokens
    if sub != "explain":
        return f"⚠ /model-router: unknown subcommand {sub!r}\n{_MODEL_ROUTER_HELP}"
    prompt = " ".join(args).strip()
    if not prompt:
        return _MODEL_ROUTER_HELP
    decision = model_router_explain(prompt)
    matched = decision.get("matched_keywords") or []
    return (
        f"  route:     {decision.get('route')}\n"
        f"  rationale: {decision.get('rationale')}\n"
        f"  matched:   {', '.join(matched) if matched else '—'}"
    )


def run_decision_ledger(rest: str) -> str:
    rest = (rest or "").strip()
    if rest in {"-h", "--help", "?", "help"}:
        return _DECISION_LEDGER_HELP
    if not rest:
        return _DECISION_LEDGER_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /decision-ledger: {exc}\n{_DECISION_LEDGER_HELP}"
    sub, *args = tokens
    if sub != "show":
        return (
            f"⚠ /decision-ledger: unknown subcommand {sub!r}\n{_DECISION_LEDGER_HELP}"
        )
    job_id = args[0] if args else None
    ledger = get_ledger(job_id)
    if not ledger:
        return "  (no ledger entries)"
    lines: list[str] = []
    for jid, entries in sorted(ledger.items()):
        lines.append(f"  {jid}  ({len(entries)} entries)")
        for entry in entries:
            kind = entry.get("kind", "?")
            ts = _fmt_ts(entry.get("ts"))
            extras = {k: v for k, v in entry.items() if k not in {"kind", "ts"}}
            extra_str = ""
            if extras:
                # Keep extras compact and on one line for chat surfaces.
                extra_str = "  " + json.dumps(extras, sort_keys=True)
            lines.append(f"    {ts}  {kind}{extra_str}")
    return "\n".join(lines)


def run_ai_radar(rest: str) -> str:
    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _AI_RADAR_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /ai-radar: {exc}\n{_AI_RADAR_HELP}"
    sub = tokens[0]
    if sub != "update":
        return f"⚠ /ai-radar: unknown subcommand {sub!r}\n{_AI_RADAR_HELP}"
    snapshot = ai_radar_update()
    return (
        "✓ ai-radar snapshot written\n"
        f"  updated_at: {_fmt_ts(snapshot.get('updated_at'))}\n"
        f"  source:     {snapshot.get('source')}\n"
        f"  note:       {snapshot.get('note')}"
    )


def run_best_coding_tool_mission(rest: str) -> str:
    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _MISSION_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /best-coding-tool-mission: {exc}\n{_MISSION_HELP}"
    sub = tokens[0]
    if sub != "status":
        return (
            f"⚠ /best-coding-tool-mission: unknown subcommand {sub!r}\n{_MISSION_HELP}"
        )
    snapshot = best_coding_tool_mission_status()
    metrics = snapshot.get("metrics") or {}
    lines = [
        f"  mission:  {snapshot.get('mission')}",
        "  metrics:",
        f"    jobs_submitted: {metrics.get('jobs_submitted', 0)}",
        f"    jobs_published: {metrics.get('jobs_published', 0)}",
        f"    jobs_resumed:   {metrics.get('jobs_resumed', 0)}",
    ]
    actions = snapshot.get("next_actions") or []
    if actions:
        lines.append("  next actions:")
        lines.extend(f"    • {a}" for a in actions)
    return "\n".join(lines)


def run_voice_capture(rest: str) -> str:
    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _VOICE_CAPTURE_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /voice-capture: {exc}\n{_VOICE_CAPTURE_HELP}"
    sub, *args = tokens
    if sub == "status":
        state = voice_capture_status()
        history = state.get("history") or []
        last = history[-1] if history else None
        last_line = (
            f"{last.get('from')} → {last.get('to')} at {_fmt_ts(last.get('ts'))}"
            if last
            else "—"
        )
        return (
            f"  mode:          {state.get('mode')}\n"
            f"  updated_at:    {_fmt_ts(state.get('updated_at'))}\n"
            f"  last change:   {last_line}\n"
            f"  history depth: {len(history)}"
        )
    if sub == "mode":
        if not args:
            return (
                f"⚠ /voice-capture mode requires a mode argument\n{_VOICE_CAPTURE_HELP}"
            )
        try:
            state = set_voice_capture_mode(args[0])
        except ValueError as exc:
            return f"⚠ /voice-capture: {exc}\n{_VOICE_CAPTURE_HELP}"
        return (
            f"✓ voice-capture mode set to {state.get('mode')} at "
            f"{_fmt_ts(state.get('updated_at'))}"
        )
    return f"⚠ /voice-capture: unknown subcommand {sub!r}\n{_VOICE_CAPTURE_HELP}"


def run_remote_worker(rest: str) -> str:
    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _REMOTE_WORKER_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /remote-worker: {exc}\n{_REMOTE_WORKER_HELP}"
    sub = tokens[0]
    if sub != "status":
        return f"⚠ /remote-worker: unknown subcommand {sub!r}\n{_REMOTE_WORKER_HELP}"
    snapshot = remote_worker_status()
    workers = snapshot.get("workers") or []
    if not workers:
        return (
            f"  workers:    (none)\n"
            f"  checked_at: {_fmt_ts(snapshot.get('checked_at'))}\n"
            f"  note:       {snapshot.get('note', '—')}"
        )
    lines = [f"  workers ({len(workers)}):"]
    for w in workers:
        if not isinstance(w, dict):
            continue
        name = w.get("id") or w.get("name") or "?"
        kind = w.get("kind", "?")
        url = w.get("url", "—")
        status = w.get("status", "unknown")
        lines.append(f"    • {name:<20} kind={kind:<14} status={status:<10} url={url}")
    lines.append(f"  checked_at: {_fmt_ts(snapshot.get('checked_at'))}")
    return "\n".join(lines)


def run_self_improve(rest: str) -> str:
    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _SELF_IMPROVE_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /self-improve: {exc}\n{_SELF_IMPROVE_HELP}"
    sub, *args = tokens
    if sub != "run":
        return f"⚠ /self-improve: unknown subcommand {sub!r}\n{_SELF_IMPROVE_HELP}"
    if not args:
        return "⚠ /self-improve run requires a job id"
    result = self_improve_run(args[0])
    if not result.get("ok"):
        return f"⚠ /self-improve run: {result.get('reason')}"
    record = result.get("record") or {}
    return (
        f"✓ self-improvement-loop request staged for {record.get('job_id')}\n"
        f"  at:        {_fmt_ts(record.get('ts'))}\n"
        f"  next_step: {record.get('next_step')}"
    )


_SWARM_HELP = (
    "/swarm <goal>            — run a Swarm Grainler Parallel job\n"
    "  Decomposes the goal into non-overlapping grains (each owning a disjoint\n"
    "  file-domain), proves them disjoint, runs each as its own specialized LLM\n"
    "  in an isolated git worktree, writes a dated Decision Ledger, and applies\n"
    "  the reversible self-update learnings.\n"
    "  Options: --no-self-update, --no-claim, --decomposer {directory,keyword,\n"
    "           workpacket,llm}. Default executor isolates + materialises specs\n"
    "  (launches no model, pushes nothing)."
)


def run_swarm(rest: str) -> str:
    """Dispatch ``/swarm`` to the Swarm Grainler Parallel coordinator.

    Runs the conservative PROMPT_ONLY pipeline: decompose → prove disjoint →
    isolate per-grain worktrees → Decision Ledger → reversible self-update. It
    launches no model and pushes nothing; a real per-grain agent executor is
    opt-in via the Python API (``AgentExecutor``).
    """

    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _SWARM_HELP
    try:
        from hermes_cli.swarm.coordinator import run_swarm as _run_swarm
        from hermes_cli.swarm.grain import OverlapError
    except Exception as exc:  # pragma: no cover - defensive
        return f"⚠ /swarm: import failed — {exc}"

    try:
        result = _run_swarm(rest, ".")
    except OverlapError as exc:
        return f"⚠ /swarm: decomposition overlaps — no grain ran.\n  {exc}"
    except Exception as exc:  # pragma: no cover - defensive
        return f"⚠ /swarm: {exc}"

    lines = [
        f"✓ swarm job {result.job_id} ({'trivial' if result.trivial else len(result.grains)} grain(s))",
    ]
    for g in result.grains:
        lines.append(f"  • {g.grain_id}: {g.state}" + (f" [{g.branch}]" if g.branch else ""))
    if result.ledger_path:
        lines.append(f"  ledger: {result.ledger_path}")
    if result.applied_updates:
        lines.append(f"  auto-applied (reversible): {len(result.applied_updates)}")
    if result.queued_updates:
        lines.append(f"  queued for owner: {len(result.queued_updates)}")
    conv = result.convergence or {}
    if conv.get("requires_manual_review"):
        lines.append("  ⚠ runtime file overlap — manual review required")
    return "\n".join(lines)


def run_profile(rest: str) -> str:
    """Dispatch for the ``/profile`` subcommands managed by the orchestrator.

    The bare ``/profile`` form is still handled by the historical
    profile handler in :mod:`cli` (it prints the active profile name +
    home directory).  This entry point handles the new
    ``build-github-history`` subcommand and falls through for help text
    when other subcommands are given.
    """
    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _PROFILE_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /profile: {exc}\n{_PROFILE_HELP}"
    sub = tokens[0]
    if sub == "build-github-history":
        payload = profile_build_github_history()
        return (
            "✓ GitHub-history snapshot written\n"
            f"  profile:    {payload.get('profile')}\n"
            f"  built_at:   {_fmt_ts(payload.get('built_at'))}\n"
            f"  source:     {payload.get('source')}\n"
            f"  note:       {payload.get('note')}"
        )
    return f"⚠ /profile: unknown subcommand {sub!r}\n{_PROFILE_HELP}"


__all__ = [
    "Job",
    "JOB_STATUSES",
    "APPROVAL_PHASES",
    "VOICE_CAPTURE_MODES",
    "submit_job",
    "list_jobs",
    "get_job",
    "resume_job",
    "publish_job",
    "cancel_job",
    "approve_phase",
    "has_approval",
    "validate_job",
    "publish_plan",
    "get_ledger",
    "model_router_explain",
    "ai_radar_update",
    "ai_radar_status",
    "best_coding_tool_mission_status",
    "voice_capture_status",
    "set_voice_capture_mode",
    "remote_worker_status",
    "self_improve_run",
    "profile_build_github_history",
    "profile_github_history_status",
    "run_orchestrate",
    "run_orchestrator",
    "run_model_router",
    "run_decision_ledger",
    "run_ai_radar",
    "run_best_coding_tool_mission",
    "run_voice_capture",
    "run_remote_worker",
    "run_self_improve",
    "run_profile",
]
