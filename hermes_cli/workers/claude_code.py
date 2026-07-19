"""Claude Code worker adapter.

Claude Code is Anthropic's official local CLI (binary name: ``claude``).
This adapter treats it as a *handoff-only* worker by default: Hermes
writes a structured prompt and status file into a workspace, the user
runs the official ``claude`` CLI against that workspace, and Hermes
collects whatever artifacts the run leaves behind.

The adapter is intentionally narrow:

  * It uses ``shutil.which`` and (optionally) ``claude --version`` to
    detect the local CLI. If the binary is absent or the version probe
    fails the adapter degrades to a "not installed" state rather than
    raising.
  * It never scrapes or automates Anthropic's subscription UI, never
    drives any unsupported control surface, and never calls the
    Anthropic API directly. Execution is gated behind an explicit
    ``allow_execute=True`` opt-in and even then only invokes the
    officially supported ``claude`` CLI in non-interactive mode.
  * Prompts emphasise the review axes Claude Code scores well on:
    architecture fit, risk control, maintainability, correctness,
    repo fit. ``SCORING_WEIGHTS`` makes those weights inspectable so
    a downstream judge can plug them into a cross-worker comparison.

The adapter is deliberately side-effect free at import time. Every
filesystem write happens through :func:`prepare_workspace` so tests
can point it at a per-test tempdir.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── public constants ──────────────────────────────────────────────────────

WORKER_NAME = "claude-code"
"""Stable identifier used in workspace paths and status payloads."""

DEFAULT_CLI_BINARY = "claude"
"""Binary name Anthropic ships for the official local CLI."""

EXPECTED_ARTIFACTS: tuple[str, ...] = (
    "output.md",
    "architecture-review.md",
    "risk-review.md",
    "patch.diff",
    "status.json",
)
"""Files Claude Code is asked to write back into the workspace.

``patch.diff`` is conditional — Claude Code only emits it when concrete
code changes are proposed. The other four are always expected.
"""

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "output.md",
    "architecture-review.md",
    "risk-review.md",
    "status.json",
)
"""Subset of :data:`EXPECTED_ARTIFACTS` that must exist for a run to be
considered complete. ``patch.diff`` is optional.
"""

SCORING_WEIGHTS: Mapping[str, float] = {
    "architecture_fit": 0.30,
    "risk_control": 0.25,
    "maintainability": 0.20,
    "correctness": 0.15,
    "repo_fit": 0.10,
}
"""Default axis weights when a judge scores a Claude Code output.

The weights sum to 1.0 and were picked to reward what this worker is
best at (architecture review, risk surfacing, long-horizon
maintainability) without ignoring correctness or repo fit. Downstream
code is free to substitute its own weights — the dict is exported so
the choice is auditable rather than hidden inside a scoring function.
"""

RUN_MODE_HANDOFF = "handoff_required"
RUN_MODE_EXECUTE = "execute"

_VALID_RUN_MODES: frozenset[str] = frozenset({RUN_MODE_HANDOFF, RUN_MODE_EXECUTE})

_VERSION_PROBE_TIMEOUT_SECONDS = 5.0
_EXECUTE_TIMEOUT_SECONDS_DEFAULT = 60.0 * 30  # 30 minutes
_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.\-]+)?)")


# ── data classes ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ClaudeCodeDetection:
    """Result of probing the local environment for the ``claude`` CLI."""

    available: bool
    path: Optional[str] = None
    version: Optional[str] = None
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "worker": WORKER_NAME,
            "available": self.available,
            "path": self.path,
            "version": self.version,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class WorkerTask:
    """Inputs the orchestrator hands to the Claude Code worker.

    ``repo_evidence`` should be short, copy-pastable strings (paths,
    grep hits, short snippets) — the goal is to give Claude Code enough
    grounding to be useful without dumping the whole repo into the
    prompt. ``decision_ledger`` is a path or URL the worker is told to
    consult before making large architectural recommendations.
    """

    mission: str
    repo_evidence: Sequence[str] = ()
    decision_ledger: Optional[str] = None
    architecture_questions: Sequence[str] = ()
    risk_questions: Sequence[str] = ()
    review_checklist: Sequence[str] = ()
    extra_context: Optional[str] = None
    propose_code_changes: bool = True


@dataclass(frozen=True)
class PreparedWorker:
    """Artifacts produced by :func:`prepare_workspace`.

    The orchestrator hands ``prompt_path`` to the user (or to the local
    ``claude`` CLI when ``mode == RUN_MODE_EXECUTE``) and later reads
    the worker's outputs back via :func:`collect_artifacts`.
    """

    workdir: Path
    prompt_path: Path
    status_path: Path
    mode: str
    detection: ClaudeCodeDetection
    expected_artifacts: tuple[str, ...] = EXPECTED_ARTIFACTS
    required_artifacts: tuple[str, ...] = REQUIRED_ARTIFACTS


@dataclass(frozen=True)
class CollectedArtifacts:
    """Result of reading back what Claude Code wrote into the workspace."""

    workdir: Path
    present: dict[str, Path] = field(default_factory=dict)
    missing_required: tuple[str, ...] = ()
    status: Optional[Mapping[str, object]] = None
    complete: bool = False


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of an explicit ``claude`` CLI invocation.

    The adapter only ever returns this when execution was explicitly
    opted into via ``allow_execute=True``. In the default
    handoff-required mode the orchestrator never calls
    :func:`run_claude_cli` at all and this type is unused.
    """

    invoked: bool
    returncode: Optional[int]
    stdout: str
    stderr: str
    timed_out: bool = False
    error: Optional[str] = None


# ── detection ─────────────────────────────────────────────────────────────


def detect(
    *,
    binary: str = DEFAULT_CLI_BINARY,
    probe_version: bool = True,
    runner: Optional[object] = None,
) -> ClaudeCodeDetection:
    """Return whether the official Claude Code CLI is locally installed.

    The probe is best-effort: a missing binary, a non-zero exit, a
    timeout, or stdout that does not parse as a version string all
    degrade to ``available=False`` (or ``available=True`` with
    ``version=None`` if the binary was found but the version probe
    failed). The function never raises.

    ``runner`` is a hook for tests — when omitted we fall back to
    :func:`subprocess.run`.
    """
    notes: list[str] = []
    path = shutil.which(binary)
    if not path:
        notes.append(
            f"binary {binary!r} not on PATH; install the official Claude "
            "Code CLI from https://docs.claude.com/claude-code to enable "
            "this worker."
        )
        return ClaudeCodeDetection(available=False, notes=tuple(notes))

    if not probe_version:
        return ClaudeCodeDetection(available=True, path=path, notes=tuple(notes))

    version = _probe_version(path, runner=runner, notes=notes)
    return ClaudeCodeDetection(
        available=True, path=path, version=version, notes=tuple(notes)
    )


def _probe_version(
    path: str,
    *,
    runner: Optional[object],
    notes: list[str],
) -> Optional[str]:
    """Run ``<path> --version`` defensively and return the parsed version.

    Any failure mode appends a note and returns ``None``. We never let
    the probe abort detection — the CLI being present is the load-
    bearing signal; the version is a nice-to-have.
    """
    call = runner if runner is not None else subprocess.run
    try:
        proc = call(  # ty: ignore[call-non-callable]  # dynamic config/plugin path
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=_VERSION_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        notes.append("version probe timed out after 5s")
        return None
    except (OSError, ValueError) as exc:
        notes.append(f"version probe failed: {exc}")
        return None

    returncode = getattr(proc, "returncode", None)
    stdout = getattr(proc, "stdout", "") or ""
    stderr = getattr(proc, "stderr", "") or ""
    if returncode not in (0, None):
        notes.append(f"version probe exited {returncode!r}")
        return None
    combined = f"{stdout}\n{stderr}".strip()
    match = _VERSION_RE.search(combined)
    if not match:
        notes.append("version probe returned unparseable output")
        return None
    return match.group(1)


# ── prompt preparation ────────────────────────────────────────────────────


def prepare_workspace(
    task: WorkerTask,
    base_dir: Path,
    *,
    mode: str = RUN_MODE_HANDOFF,
    detection: Optional[ClaudeCodeDetection] = None,
) -> PreparedWorker:
    """Materialise ``workers/claude-code/`` under ``base_dir``.

    Writes two files:

      * ``prompt.md`` — the structured handoff prompt the user (or the
        official CLI) drives Claude Code with.
      * ``status.json`` — a machine-readable snapshot describing what
        the orchestrator expects back and which mode the run is in.

    Detection results are embedded in ``status.json`` so the artifact
    collector can correlate a stale workspace with whatever ``claude``
    binary actually produced it. If ``detection`` is omitted the
    function probes the environment itself.
    """
    if mode not in _VALID_RUN_MODES:
        raise ValueError(
            f"invalid run mode {mode!r}; expected one of {sorted(_VALID_RUN_MODES)}"
        )
    if not task.mission.strip():
        raise ValueError("WorkerTask.mission must be non-empty")

    workdir = Path(base_dir) / "workers" / WORKER_NAME
    workdir.mkdir(parents=True, exist_ok=True)

    det = detection or detect()
    prompt = _render_prompt(task, mode=mode, detection=det)
    prompt_path = workdir / "prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    expected = _expected_for_task(task)
    required = tuple(a for a in REQUIRED_ARTIFACTS if a in expected)
    status_payload: dict[str, object] = {
        "worker": WORKER_NAME,
        "mode": mode,
        "mission": task.mission,
        "decision_ledger": task.decision_ledger,
        "expected_artifacts": list(expected),
        "required_artifacts": list(required),
        "scoring_weights": dict(SCORING_WEIGHTS),
        "detection": det.as_dict(),
        "handoff_required": mode == RUN_MODE_HANDOFF,
    }
    status_path = workdir / "status.json"
    status_path.write_text(
        json.dumps(status_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return PreparedWorker(
        workdir=workdir,
        prompt_path=prompt_path,
        status_path=status_path,
        mode=mode,
        detection=det,
        expected_artifacts=expected,
        required_artifacts=required,
    )


def _expected_for_task(task: WorkerTask) -> tuple[str, ...]:
    """Drop ``patch.diff`` when the task explicitly disables code edits."""
    if task.propose_code_changes:
        return EXPECTED_ARTIFACTS
    return tuple(a for a in EXPECTED_ARTIFACTS if a != "patch.diff")


def _render_prompt(
    task: WorkerTask,
    *,
    mode: str,
    detection: ClaudeCodeDetection,
) -> str:
    """Render the structured prompt Markdown.

    The order and section names are part of the worker contract — the
    judge looks for these headings when parsing what came back, and the
    tests assert that the load-bearing sections are present.
    """
    lines: list[str] = []
    lines.append("# Claude Code worker — handoff prompt")
    lines.append("")
    lines.append(
        f"You are running as the **Claude Code worker** ({WORKER_NAME}). "
        "muse has prepared this workspace for you. Read every section "
        "before producing the requested artifacts."
    )
    lines.append("")

    lines.append("## Mission")
    lines.append("")
    lines.append(task.mission.strip())
    lines.append("")

    lines.append("## Repo evidence")
    lines.append("")
    if task.repo_evidence:
        for item in task.repo_evidence:
            lines.append(f"- {item.strip()}")
    else:
        lines.append(
            "- (none supplied; explore the working tree before recommending "
            "non-trivial changes.)"
        )
    lines.append("")

    lines.append("## Decision ledger")
    lines.append("")
    if task.decision_ledger:
        lines.append(
            f"Consult the decision ledger at `{task.decision_ledger}` before "
            "proposing architectural changes. Reference relevant entries by "
            "ID in `architecture-review.md`."
        )
    else:
        lines.append(
            "No decision ledger was supplied. Treat your recommendations as "
            "an initial entry the maintainer may want to record."
        )
    lines.append("")

    lines.append("## Architecture questions")
    lines.append("")
    _render_question_block(lines, task.architecture_questions, kind="architecture")

    lines.append("## Risk questions")
    lines.append("")
    _render_question_block(lines, task.risk_questions, kind="risk")

    lines.append("## Review checklist")
    lines.append("")
    if task.review_checklist:
        for item in task.review_checklist:
            lines.append(f"- [ ] {item.strip()}")
    else:
        lines += [
            "- [ ] Confirm the change is consistent with the existing "
            "module boundaries.",
            "- [ ] Identify any silently broadened invariants.",
            "- [ ] Flag any new external dependency, network call, or "
            "credential surface.",
            "- [ ] Note tests that should exist but don't.",
        ]
    lines.append("")

    if task.extra_context:
        lines.append("## Additional context")
        lines.append("")
        lines.append(task.extra_context.strip())
        lines.append("")

    lines.append("## Expected output")
    lines.append("")
    lines.append(
        "Write every artifact into the same directory as this prompt. "
        "Do not delete existing files you did not create."
    )
    lines.append("")
    lines.append("- `output.md` — narrative summary of findings and recommendations.")
    lines.append(
        "- `architecture-review.md` — answers to the architecture "
        "questions above, with references to repo evidence and decision "
        "ledger entries."
    )
    lines.append(
        "- `risk-review.md` — answers to the risk questions, including "
        "blast radius, reversibility, and an explicit go / no-go."
    )
    if task.propose_code_changes:
        lines.append(
            "- `patch.diff` — unified diff of any proposed code changes. "
            "Omit the file entirely if you are not recommending code edits."
        )
    lines.append(
        "- `status.json` — machine-readable verdict. Required keys: "
        "`worker` (must equal `\"claude-code\"`), `verdict` "
        "(`approve` / `revise` / `block`), `confidence` (0.0–1.0), "
        "`scores` (object keyed by the axes listed below)."
    )
    lines.append("")

    lines.append("### Scoring axes")
    lines.append("")
    lines.append(
        "Score each axis on a 0.0–1.0 scale in the `scores` object of "
        "`status.json`. The orchestrator weights them as follows when "
        "ranking your output against other workers:"
    )
    lines.append("")
    for axis, weight in SCORING_WEIGHTS.items():
        lines.append(f"- `{axis}` — weight {weight:.2f}")
    lines.append("")

    lines.append("## Run mode")
    lines.append("")
    if mode == RUN_MODE_HANDOFF:
        lines.append(
            "This run is **handoff-required**. A human (or the official "
            "`claude` CLI driven by a human) is expected to read this "
            "prompt and produce the artifacts above. muse will not "
            "invoke any Claude Code automation on its own behalf."
        )
    else:
        lines.append(
            "This run is **execute-enabled**. The orchestrator has been "
            "granted explicit permission to invoke the official local "
            "`claude` CLI against this workspace in non-interactive mode. "
            "No other automation surface is used."
        )
    lines.append("")

    lines.append("## Detection snapshot")
    lines.append("")
    if detection.available:
        lines.append(
            f"- Local `claude` CLI detected at `{detection.path}`"
            + (f" (version {detection.version})." if detection.version else ".")
        )
    else:
        lines.append(
            "- Local `claude` CLI was not detected at prompt-preparation "
            "time. The workspace was still materialised so a human can "
            "drive the run manually."
        )
    for note in detection.notes:
        lines.append(f"  - note: {note}")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_question_block(
    lines: list[str], questions: Sequence[str], *, kind: str
) -> None:
    if questions:
        for q in questions:
            lines.append(f"- {q.strip()}")
    else:
        lines.append(
            f"- (no explicit {kind} questions supplied; surface the top "
            f"three {kind} concerns you find while reviewing.)"
        )
    lines.append("")


# ── artifact collection ───────────────────────────────────────────────────


def collect_artifacts(prepared: PreparedWorker) -> CollectedArtifacts:
    """Read back whatever the worker wrote into ``prepared.workdir``.

    The collector is non-destructive: it never deletes or rewrites
    files. ``status.json`` is parsed when present (best-effort —
    malformed JSON yields a ``None`` status and a missing-required
    note so the orchestrator can mark the run as incomplete).
    """
    present: dict[str, Path] = {}
    for name in prepared.expected_artifacts:
        path = prepared.workdir / name
        if path.is_file():
            present[name] = path

    missing_required = tuple(
        name for name in prepared.required_artifacts if name not in present
    )

    status_payload: Optional[Mapping[str, object]] = None
    status_path = present.get("status.json")
    if status_path is not None:
        try:
            status_payload = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            status_payload = None
            if "status.json" not in missing_required:
                missing_required = (*missing_required, "status.json")

    return CollectedArtifacts(
        workdir=prepared.workdir,
        present=present,
        missing_required=missing_required,
        status=status_payload,
        complete=not missing_required,
    )


# ── scoring helper ────────────────────────────────────────────────────────


def score(
    axis_scores: Mapping[str, float],
    *,
    weights: Mapping[str, float] = SCORING_WEIGHTS,
) -> float:
    """Combine per-axis scores into a single 0.0–1.0 weighted score.

    Missing axes are treated as zero so a worker that fails to score
    itself on the heavy axes is penalised. Extra axes are ignored — a
    worker is allowed to volunteer additional self-assessments without
    polluting the canonical weighting.
    """
    total = 0.0
    for axis, weight in weights.items():
        raw = axis_scores.get(axis, 0.0)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = 0.0
        value = max(0.0, min(1.0, value))
        total += value * float(weight)
    return total


# ── optional execute path ─────────────────────────────────────────────────


def run_claude_cli(
    prepared: PreparedWorker,
    *,
    allow_execute: bool = False,
    extra_args: Sequence[str] = (),
    timeout: float = _EXECUTE_TIMEOUT_SECONDS_DEFAULT,
    runner: Optional[object] = None,
    env: Optional[Mapping[str, str]] = None,
) -> ExecutionResult:
    """Invoke the official ``claude`` CLI against the prepared workspace.

    This function is the single supported execution path and it is
    refused by default. ``allow_execute=True`` AND
    ``prepared.mode == RUN_MODE_EXECUTE`` must both hold — otherwise we
    return a no-op result describing the refusal. This double gate
    means an accidentally mis-set flag in one layer cannot silently
    start running an external tool.
    """
    if not allow_execute:
        return ExecutionResult(
            invoked=False,
            returncode=None,
            stdout="",
            stderr="",
            error="execution refused: allow_execute=False (handoff required).",
        )
    if prepared.mode != RUN_MODE_EXECUTE:
        return ExecutionResult(
            invoked=False,
            returncode=None,
            stdout="",
            stderr="",
            error=(
                "execution refused: prepared workspace is in handoff-required "
                "mode. Re-prepare with mode=RUN_MODE_EXECUTE to opt in."
            ),
        )
    if not prepared.detection.available or not prepared.detection.path:
        return ExecutionResult(
            invoked=False,
            returncode=None,
            stdout="",
            stderr="",
            error="execution refused: local claude CLI is not installed.",
        )

    cli = prepared.detection.path
    cmd: list[str] = [cli, "--print", str(prepared.prompt_path), *extra_args]
    call = runner if runner is not None else subprocess.run
    process_env = dict(env) if env is not None else dict(os.environ)
    try:
        proc = call(  # ty: ignore[call-non-callable]  # dynamic config/plugin path
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(prepared.workdir),
            env=process_env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return ExecutionResult(
            invoked=True,
            returncode=None,
            stdout=getattr(exc, "stdout", "") or "",
            stderr=getattr(exc, "stderr", "") or "",
            timed_out=True,
            error=f"claude CLI timed out after {timeout:.0f}s",
        )
    except (OSError, ValueError) as exc:
        return ExecutionResult(
            invoked=True,
            returncode=None,
            stdout="",
            stderr="",
            error=f"claude CLI failed to launch: {exc}",
        )

    return ExecutionResult(
        invoked=True,
        returncode=getattr(proc, "returncode", None),
        stdout=getattr(proc, "stdout", "") or "",
        stderr=getattr(proc, "stderr", "") or "",
    )


# ── small helpers used by callers / tests ────────────────────────────────


def describe(prepared: PreparedWorker) -> dict[str, object]:
    """Return a JSON-safe snapshot of a prepared workspace."""
    return {
        "worker": WORKER_NAME,
        "workdir": str(prepared.workdir),
        "prompt_path": str(prepared.prompt_path),
        "status_path": str(prepared.status_path),
        "mode": prepared.mode,
        "expected_artifacts": list(prepared.expected_artifacts),
        "required_artifacts": list(prepared.required_artifacts),
        "detection": prepared.detection.as_dict(),
    }


def iter_expected_artifact_paths(prepared: PreparedWorker) -> Iterable[Path]:
    """Yield the absolute paths Hermes will look for after the run."""
    for name in prepared.expected_artifacts:
        yield prepared.workdir / name


# Keep ``CollectedArtifacts.as_dict`` available without forcing callers to
# build it themselves — useful when sticking results into an audit log.
def collected_as_dict(collected: CollectedArtifacts) -> dict[str, object]:
    return {
        "workdir": str(collected.workdir),
        "present": {k: str(v) for k, v in collected.present.items()},
        "missing_required": list(collected.missing_required),
        "complete": collected.complete,
        "status": dict(collected.status) if collected.status else None,
    }


__all__ = [
    "ClaudeCodeDetection",
    "CollectedArtifacts",
    "DEFAULT_CLI_BINARY",
    "EXPECTED_ARTIFACTS",
    "ExecutionResult",
    "PreparedWorker",
    "REQUIRED_ARTIFACTS",
    "RUN_MODE_EXECUTE",
    "RUN_MODE_HANDOFF",
    "SCORING_WEIGHTS",
    "WORKER_NAME",
    "WorkerTask",
    "collect_artifacts",
    "collected_as_dict",
    "describe",
    "detect",
    "iter_expected_artifact_paths",
    "prepare_workspace",
    "run_claude_cli",
    "score",
]
