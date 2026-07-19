"""Claude Code Windows worker — remote execution adapter.

This worker is the bridge twin of :mod:`hermes_cli.workers.claude_code`.
The local Claude Code worker assumes the official ``claude`` CLI lives
on the same machine as Hermes. This module targets the common
``Hermes-on-Android-or-Linux`` ↔ ``Claude Code on Jeremiah's Windows
desktop`` topology: prompts are dispatched over a private,
authenticated tunnel to a Windows worker that runs the official
``claude`` CLI inside a real repo / git worktree and writes the
artifacts back into a shared directory.

The adapter does **not** open any sockets, expose any HTTP endpoint,
or hold long-running threads. It is a thin five-step contract over
:class:`hermes_cli.remote_bridge.RemoteBridge`:

  ``detect`` → does the endpoint look reachable?
  ``prepare`` → reuse the local Claude Code prompt builder.
  ``run``     → dispatch the prompt via the bridge.
  ``collect`` → pull artifacts back when the job reports complete.
  ``score``   → reuse :func:`hermes_cli.workers.claude_code.score`.

Default behaviour is conservative: every run requires explicit
``allow_remote_execute=True`` *and* an opted-in
:class:`~hermes_cli.remote_bridge.RemoteEndpoint`. Without both, the
manifest is staged and the worker is parked in
``awaiting_approval`` — visible to the user via the audit log but
never executed.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from hermes_cli import remote_bridge as rb
from hermes_cli.workers import claude_code as cc

# ── public constants ──────────────────────────────────────────────────────

WORKER_NAME = "claude-code-windows"
"""Stable identifier the orchestrator uses to dispatch to this worker."""

DEFAULT_COMMAND = "claude"
"""Binary the Windows worker is expected to drive."""

EXPECTED_ARTIFACTS: tuple[str, ...] = (
    "output.md",
    "patch.diff",
    "changed-files.txt",
    "validation-output.txt",
    "status.json",
)
"""Artifacts the bridge asks the Windows worker to produce.

``patch.diff`` is conditional (only emitted when code edits are
proposed); everything else is expected on every run.
"""

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "output.md",
    "changed-files.txt",
    "validation-output.txt",
    "status.json",
)
"""Subset of :data:`EXPECTED_ARTIFACTS` that must be present for the
run to count as complete.
"""

SCORING_WEIGHTS: Mapping[str, float] = cc.SCORING_WEIGHTS
"""Scoring weights are inherited from the local Claude Code worker so
local and remote runs are directly comparable."""


# ── data classes ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RemoteWorkerTask:
    """Inputs the orchestrator hands to the remote worker.

    Mirrors :class:`hermes_cli.workers.claude_code.WorkerTask` but
    carries the remote-specific knobs (repo identity on the Windows
    side, whether the worker should run validation after the patch
    lands, what command the worker should drive).
    """

    mission: str
    repo_evidence: Sequence[str] = ()
    decision_ledger: Optional[str] = None
    architecture_questions: Sequence[str] = ()
    risk_questions: Sequence[str] = ()
    review_checklist: Sequence[str] = ()
    extra_context: Optional[str] = None
    propose_code_changes: bool = True
    remote_repo_path: Optional[str] = None
    validation_command: Optional[str] = None
    extra_manifest: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RemoteWorkerDetection:
    """Result of probing whether the remote endpoint is usable."""

    available: bool
    endpoint: str
    transport: str
    workspace_root: str
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "worker": WORKER_NAME,
            "available": self.available,
            "endpoint": self.endpoint,
            "transport": self.transport,
            "workspace_root": self.workspace_root,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class PreparedRemoteWorker:
    """Local staging output produced before the bridge is engaged.

    ``prompt`` is the rendered Markdown body. ``manifest_payload``
    feeds straight into the manifest under the ``extra`` key so the
    Windows worker has the same structured task description Hermes
    used locally.
    """

    workdir: Path
    prompt_path: Path
    prompt: str
    expected_artifacts: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    manifest_payload: Mapping[str, Any]


@dataclass(frozen=True)
class DispatchResult:
    """Outcome of dispatching a prepared worker through the bridge."""

    job: rb.RemoteJob
    refused: bool = False
    error: Optional[str] = None


@dataclass(frozen=True)
class CollectedRemoteArtifacts:
    """Files copied out of the shared workspace back into Hermes-local."""

    job_id: str
    local_dir: Path
    present: dict[str, Path] = field(default_factory=dict)
    missing_required: tuple[str, ...] = ()
    status: Optional[Mapping[str, Any]] = None
    complete: bool = False


# ── detection ─────────────────────────────────────────────────────────────


def detect(bridge: rb.RemoteBridge) -> RemoteWorkerDetection:
    """Best-effort reachability probe for the configured remote endpoint."""
    notes: list[str] = []
    endpoint = bridge.endpoint
    root = Path(endpoint.workspace_root)

    if endpoint.transport != rb.TRANSPORT_FILE_DROP:
        notes.append(
            f"transport {endpoint.transport!r} is documented but not yet "
            "implemented; see docs/remote/secure-tunnel-options.md"
        )
        return RemoteWorkerDetection(
            available=False,
            endpoint=endpoint.name,
            transport=endpoint.transport,
            workspace_root=str(root),
            notes=tuple(notes),
        )

    if not root.exists():
        notes.append(
            f"workspace_root {str(root)!r} does not exist — bring up the "
            "tunnel / mount the shared folder before dispatching."
        )
        return RemoteWorkerDetection(
            available=False,
            endpoint=endpoint.name,
            transport=endpoint.transport,
            workspace_root=str(root),
            notes=tuple(notes),
        )

    if not endpoint.allowed_device_ids:
        notes.append(
            "endpoint has no allowed_device_ids — status replies will be "
            "trusted by token only. Configure allowed_device_ids for "
            "defence in depth."
        )

    if not endpoint.allow_remote_execute:
        notes.append(
            "endpoint.allow_remote_execute=False — dispatches will park in "
            "awaiting_approval until explicitly unlocked."
        )

    return RemoteWorkerDetection(
        available=True,
        endpoint=endpoint.name,
        transport=endpoint.transport,
        workspace_root=str(root),
        notes=tuple(notes),
    )


# ── prompt preparation ────────────────────────────────────────────────────


def prepare_workspace(
    task: RemoteWorkerTask,
    base_dir: Path,
) -> PreparedRemoteWorker:
    """Render the prompt and stage it under ``base_dir/workers/claude-code-windows/``.

    The prompt body is built by reusing the local Claude Code prompt
    renderer with a Windows-specific epilogue describing the
    artifacts the bridge contract requires.
    """
    if not task.mission.strip():
        raise ValueError("RemoteWorkerTask.mission must be non-empty")

    workdir = Path(base_dir) / "workers" / WORKER_NAME
    workdir.mkdir(parents=True, exist_ok=True)

    local_task = cc.WorkerTask(
        mission=task.mission,
        repo_evidence=task.repo_evidence,
        decision_ledger=task.decision_ledger,
        architecture_questions=task.architecture_questions,
        risk_questions=task.risk_questions,
        review_checklist=task.review_checklist,
        extra_context=task.extra_context,
        propose_code_changes=task.propose_code_changes,
    )
    base_prompt = cc._render_prompt(
        local_task,
        mode=cc.RUN_MODE_EXECUTE,
        detection=cc.ClaudeCodeDetection(available=True, path="claude"),
    )
    prompt = base_prompt + _render_remote_epilogue(task)

    expected = _expected_for_task(task)
    required = tuple(a for a in REQUIRED_ARTIFACTS if a in expected)
    prompt_path = workdir / "prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    manifest_payload = {
        "task_kind": "claude-code-windows",
        "remote_repo_path": task.remote_repo_path,
        "validation_command": task.validation_command,
        "propose_code_changes": task.propose_code_changes,
        **dict(task.extra_manifest),
    }

    return PreparedRemoteWorker(
        workdir=workdir,
        prompt_path=prompt_path,
        prompt=prompt,
        expected_artifacts=expected,
        required_artifacts=required,
        manifest_payload=manifest_payload,
    )


def _expected_for_task(task: RemoteWorkerTask) -> tuple[str, ...]:
    if task.propose_code_changes:
        return EXPECTED_ARTIFACTS
    return tuple(a for a in EXPECTED_ARTIFACTS if a != "patch.diff")


def _render_remote_epilogue(task: RemoteWorkerTask) -> str:
    lines: list[str] = []
    lines.append("")
    lines.append("## Remote worker contract")
    lines.append("")
    lines.append(
        "You are running on Jeremiah's Windows desktop, driven by the "
        "muse remote bridge. Read the manifest at `manifest.json` "
        "before you start — it tells you which command muse authorised "
        "and where to write artifacts."
    )
    lines.append("")
    if task.remote_repo_path:
        lines.append(
            f"- Work inside the repo / worktree at `{task.remote_repo_path}`."
        )
    else:
        lines.append(
            "- The manifest's `extra.remote_repo_path` is empty — confirm "
            "with the user before touching any working tree."
        )
    lines.append(
        "- Do not exfiltrate secrets. Never read `.env`, credential "
        "stores, or keychains unless the manifest explicitly lists "
        "them as inputs."
    )
    lines.append(
        "- Honour `cancel.json`: if muse writes one into the workspace, "
        "abort and update `status.json` with `state: canceled`."
    )
    lines.append("")
    lines.append("### Required artifacts")
    lines.append("")
    for name in EXPECTED_ARTIFACTS:
        if name == "patch.diff" and not task.propose_code_changes:
            continue
        lines.append(f"- `{name}`")
    lines.append("")
    if task.validation_command:
        lines.append("### Validation")
        lines.append("")
        lines.append(
            f"Run `{task.validation_command}` after the patch is applied "
            "and capture stdout+stderr into `validation-output.txt`. "
            "Record the exit code in `status.json.validation_exit_code`."
        )
        lines.append("")
    lines.append("### Status protocol")
    lines.append("")
    lines.append(
        "Write `status.json` with at least: `state` "
        "(`queued`/`running`/`completed`/`failed`), `detail`, "
        "`auth_token` (echoed verbatim from `manifest.json`), "
        "`device_id`, `last_seen` (unix seconds), and `artifacts` "
        "(filename → short description)."
    )
    lines.append("")
    return "\n".join(lines)


# ── dispatch / run ────────────────────────────────────────────────────────


def dispatch(
    prepared: PreparedRemoteWorker,
    bridge: rb.RemoteBridge,
    *,
    allow_remote_execute: bool = False,
    command: str = DEFAULT_COMMAND,
    env_files: Sequence[Path] = (),
) -> DispatchResult:
    """Send the prepared workspace through the bridge.

    The bridge enforces the safety gates (command allowlist, device
    allowlist, env-file refusal, transport-stub refusal). We surface
    its refusals as a :class:`DispatchResult` with ``refused=True``
    instead of raising so the orchestrator can keep going and route to
    a fallback worker.
    """
    try:
        job = bridge.dispatch(
            prompt=prepared.prompt,
            expected_artifacts=prepared.expected_artifacts,
            required_artifacts=prepared.required_artifacts,
            command=command,
            allow_remote_execute=allow_remote_execute,
            extra_manifest=prepared.manifest_payload,
            env_files=env_files,
        )
    except rb.BridgeError as exc:
        return DispatchResult(
            job=_placeholder_job(prepared, bridge, error=str(exc)),
            refused=True,
            error=str(exc),
        )
    return DispatchResult(job=job, refused=False)


def _placeholder_job(
    prepared: PreparedRemoteWorker,
    bridge: rb.RemoteBridge,
    *,
    error: str,
) -> rb.RemoteJob:
    """Build a synthetic RemoteJob describing a refusal without dispatching."""
    return rb.RemoteJob(
        job_id="(refused)",
        endpoint=bridge.endpoint.name,
        state=rb.JobState.AWAITING_APPROVAL,
        workdir=prepared.workdir,
        manifest_path=prepared.workdir / "manifest.json",
        prompt_path=prepared.prompt_path,
        auth_token="",
        created_at=0.0,
        detail=f"refused: {error}",
    )


def poll_status(bridge: rb.RemoteBridge, job_id: str) -> rb.RemoteStatus:
    """Wrapper around :meth:`RemoteBridge.get_status` for symmetry."""
    return bridge.get_status(job_id)


# ── artifact collection ───────────────────────────────────────────────────


def collect_artifacts(
    bridge: rb.RemoteBridge,
    job_id: str,
    prepared: PreparedRemoteWorker,
) -> CollectedRemoteArtifacts:
    """Copy artifacts back into the Hermes-local workspace.

    The bridge refuses to collect from a non-completed job; we catch
    the refusal and surface it as an incomplete result so the
    orchestrator can decide whether to retry or fail the run.
    """
    try:
        files = bridge.collect_artifacts(job_id, prepared.workdir)
    except rb.BridgeError as exc:
        return CollectedRemoteArtifacts(
            job_id=job_id,
            local_dir=prepared.workdir,
            present={},
            missing_required=tuple(prepared.required_artifacts),
            status={"error": str(exc)},
            complete=False,
        )

    present: dict[str, Path] = {}
    for path in files:
        present[path.name] = path

    missing_required = tuple(
        name for name in prepared.required_artifacts if name not in present
    )

    status_payload: Optional[Mapping[str, Any]] = None
    status_path = present.get("status.json")
    if status_path is not None:
        try:
            status_payload = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            status_payload = None
            if "status.json" not in missing_required:
                missing_required = (*missing_required, "status.json")

    return CollectedRemoteArtifacts(
        job_id=job_id,
        local_dir=prepared.workdir,
        present=present,
        missing_required=missing_required,
        status=status_payload,
        complete=not missing_required,
    )


# ── scoring ───────────────────────────────────────────────────────────────


def score(
    axis_scores: Mapping[str, float],
    *,
    weights: Mapping[str, float] = SCORING_WEIGHTS,
) -> float:
    """Combine axis scores using the local Claude Code weighting."""
    return cc.score(axis_scores, weights=weights)


# ── small helpers ─────────────────────────────────────────────────────────


def describe(prepared: PreparedRemoteWorker, bridge: rb.RemoteBridge) -> dict[str, Any]:
    """JSON-safe snapshot of a prepared remote worker."""
    return {
        "worker": WORKER_NAME,
        "workdir": str(prepared.workdir),
        "prompt_path": str(prepared.prompt_path),
        "expected_artifacts": list(prepared.expected_artifacts),
        "required_artifacts": list(prepared.required_artifacts),
        "endpoint": bridge.endpoint.name,
        "transport": bridge.endpoint.transport,
    }


def cleanup_workspace(prepared: PreparedRemoteWorker) -> None:
    """Remove the local staging directory.

    Useful in tests; production code keeps the workspace so the audit
    trail outlives the run.
    """
    if prepared.workdir.is_dir():
        shutil.rmtree(prepared.workdir)


__all__ = [
    "CollectedRemoteArtifacts",
    "DEFAULT_COMMAND",
    "DispatchResult",
    "EXPECTED_ARTIFACTS",
    "PreparedRemoteWorker",
    "REQUIRED_ARTIFACTS",
    "RemoteWorkerDetection",
    "RemoteWorkerTask",
    "SCORING_WEIGHTS",
    "WORKER_NAME",
    "cleanup_workspace",
    "collect_artifacts",
    "describe",
    "detect",
    "dispatch",
    "poll_status",
    "prepare_workspace",
    "score",
]
