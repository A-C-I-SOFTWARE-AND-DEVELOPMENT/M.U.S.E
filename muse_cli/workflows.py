"""Phase-gated workflow engine for Hermes jobs.

Every job in Hermes moves through eight explicit phases:

    intake → research → planning → approval → implementation →
        validation → publish → retrospective

Each phase carries a status (``pending``, ``running``, ``blocked``,
``needs_approval``, ``approved``, ``rejected``, ``completed``,
``failed``). Some phases can be advanced automatically; others always
require an explicit ``approve_phase`` call. Destructive commands and
secrets operations always require approval, no matter the phase.

This module owns the *logic*. The on-disk *shapes* live in
:mod:`muse_cli.workflow_models`.

The engine is intentionally storage-only:

  * no subprocesses,
  * no network,
  * no agent loop imports.

That makes it trivial to test, safe to embed in any gateway, and
inspectable with ``ls`` / ``cat`` against the job folder.

A short summary of the gate rules, for quick reference (see
``docs/orchestration/phase-gated-workflows.md`` for the full prose):

* **Research** can start automatically.
* **Planning** can start only after the research phase has produced
  evidence (i.e. ``research`` is ``completed`` and has a non-empty
  report).
* **Implementation** requires approval unless ``trusted_local`` is set.
* **Validation** can run automatically after implementation completes.
* **Publish** always requires approval.
* **Destructive** commands and **secrets** operations always require
  approval — they cannot be auto-run even under ``trusted_local``.

Plain English contract:
    Every phase report this module writes contains a "Plain English"
    section that explains in normal language what happened and why.
    That section is non-optional and is enforced by
    :func:`write_phase_report`.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from muse_cli.workflow_models import (
    ALWAYS_APPROVAL_GATED,
    ALWAYS_APPROVED_ACTIONS,
    APPROVAL,
    APPROVED,
    BLOCKED,
    COMPLETED,
    FAILED,
    IMPLEMENTATION,
    INTAKE,
    NEEDS_APPROVAL,
    PENDING,
    PHASE_ORDER,
    PHASE_STATUSES,
    PLANNING,
    PUBLISH,
    REJECTED,
    REPORT_PHASES,
    RESEARCH,
    RUNNING,
    TERMINAL_STATUSES,
    VALIDATION,
    Phase,
    WorkflowState,
)


PHASES_DIRNAME = "phases"
STATUS_FILE = "status.json"
REPORT_EXT = ".md"
PLAIN_ENGLISH_HEADING = "## Plain English"


# ──────────────────────────────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────────────────────────────


class WorkflowError(Exception):
    """Base class for phase-gated workflow errors."""


class UnknownPhaseError(WorkflowError):
    """Raised when an unknown phase name is referenced."""


class InvalidTransitionError(WorkflowError):
    """Raised when a phase transition is not allowed by the gate rules."""


class ApprovalRequiredError(WorkflowError):
    """Raised when an action would require approval but none was supplied."""


# ──────────────────────────────────────────────────────────────────────
# JobLike protocol
# ──────────────────────────────────────────────────────────────────────


@dataclass
class JobHandle:
    """Minimal job descriptor accepted by the engine.

    The engine doesn't need the full :class:`orchestrator_models.Job`;
    it only needs an id and a place on disk to put the phase folder. A
    ``JobHandle`` makes that contract explicit for tests and for
    callers that don't want to pull in the full controller.

    ``trusted_local`` mirrors the same field on the orchestrator's
    ``Job`` and downgrades approval requirements where the gate rules
    allow it.
    """

    job_id: str
    job_dir: Path
    trusted_local: bool = False


def _coerce_job(job: Any) -> JobHandle:
    """Accept either a :class:`JobHandle` or an arbitrary object with
    the right attributes (e.g. a full ``Job`` from
    ``orchestrator_models``)."""

    if isinstance(job, JobHandle):
        return job
    job_id = getattr(job, "job_id", None) or getattr(job, "id", None)
    if not job_id:
        raise WorkflowError("job has no job_id / id")
    job_dir = getattr(job, "job_dir", None) or getattr(job, "dir", None)
    if job_dir is None:
        raise WorkflowError("job has no job_dir")
    return JobHandle(
        job_id=str(job_id),
        job_dir=Path(job_dir),
        trusted_local=bool(getattr(job, "trusted_local", False)),
    )


# ──────────────────────────────────────────────────────────────────────
# Time helper (monotonic, microsecond resolution)
# ──────────────────────────────────────────────────────────────────────

_LAST_NOW = 0


def _now() -> int:
    """Strictly-increasing microsecond timestamp.

    Mirrors the helper in ``muse_cli.orchestrator`` so two transitions
    that happen inside the same wall-clock tick still get distinct
    ``ts`` values in the history list.
    """

    global _LAST_NOW
    candidate = time.time_ns() // 1_000
    if candidate <= _LAST_NOW:
        candidate = _LAST_NOW + 1
    _LAST_NOW = candidate
    return candidate


# ──────────────────────────────────────────────────────────────────────
# Filesystem helpers
# ──────────────────────────────────────────────────────────────────────


def _phases_dir(job: JobHandle) -> Path:
    return job.job_dir / PHASES_DIRNAME


def _status_path(job: JobHandle) -> Path:
    return job.job_dir / STATUS_FILE


def _report_path(job: JobHandle, phase: str) -> Path:
    return _phases_dir(job) / f"{phase}{REPORT_EXT}"


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _load_state(job: JobHandle) -> WorkflowState:
    sp = _status_path(job)
    if not sp.is_file():
        raise WorkflowError(
            f"job {job.job_id!r} has no status.json — call initialize_phases first"
        )
    raw = json.loads(sp.read_text(encoding="utf-8"))
    state = WorkflowState.from_dict(raw)
    # Ensure all canonical phases exist even if the file was written by
    # an older version that didn't know about one of them.
    changed = False
    for name in PHASE_ORDER:
        if name not in state.phases:
            state.phases[name] = Phase(
                name=name,
                requires_approval=_phase_requires_approval(name, state.trusted_local),
                report_path=_default_report_relpath(name),
            )
            changed = True
    if changed:
        _save_state(job, state)
    return state


def _save_state(job: JobHandle, state: WorkflowState) -> None:
    state.updated_at = _now()
    _write_json_atomic(_status_path(job), state.to_dict())


# ──────────────────────────────────────────────────────────────────────
# Gate-rule helpers
# ──────────────────────────────────────────────────────────────────────


def _phase_requires_approval(phase: str, trusted_local: bool) -> bool:
    """Should ``phase`` carry ``requires_approval=True`` at init time?

    Approval-gated phases are: ``approval`` and ``publish`` (always),
    plus ``implementation`` when ``trusted_local`` is false. The
    ``approval`` phase itself is approval-gated by definition — its
    whole purpose is to be approved or rejected.
    """

    if phase in ALWAYS_APPROVAL_GATED:
        return True
    if phase == IMPLEMENTATION and not trusted_local:
        return True
    return False


def _default_report_relpath(phase: str) -> str | None:
    if phase in REPORT_PHASES:
        return f"{PHASES_DIRNAME}/{phase}{REPORT_EXT}"
    return None


def _ensure_known_phase(phase: str) -> None:
    if phase not in PHASE_ORDER:
        raise UnknownPhaseError(
            f"unknown phase {phase!r}; expected one of {', '.join(PHASE_ORDER)}"
        )


def _ensure_known_status(status: str) -> None:
    if status not in PHASE_STATUSES:
        raise WorkflowError(
            f"unknown phase status {status!r}; "
            f"expected one of {', '.join(sorted(PHASE_STATUSES))}"
        )


def _phase_index(phase: str) -> int:
    return PHASE_ORDER.index(phase)


def _previous_phase(phase: str) -> str | None:
    idx = _phase_index(phase)
    return PHASE_ORDER[idx - 1] if idx > 0 else None


def _has_evidence(state: WorkflowState, phase: str, job: JobHandle) -> bool:
    """A phase has evidence iff it is in a terminal status *and* either
    has a non-empty report on disk or doesn't own a report at all
    (e.g. ``intake``)."""

    p = state.phases.get(phase)
    if p is None or p.status not in TERMINAL_STATUSES:
        return False
    if phase not in REPORT_PHASES:
        return True
    report = _report_path(job, phase)
    if not report.is_file():
        return False
    return report.stat().st_size > 0


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────


def initialize_phases(job: Any) -> WorkflowState:
    """Initialize the phase-gated workflow for ``job``.

    Creates ``<job_dir>/phases/`` and a fresh ``status.json``. Idempotent
    — calling it twice on the same job returns the existing state
    unchanged (so a controller can call it on every resume without
    fear). Intake is marked ``completed`` immediately because by the
    time we have a job folder, intake is by definition done.
    """

    handle = _coerce_job(job)
    handle.job_dir.mkdir(parents=True, exist_ok=True)
    _phases_dir(handle).mkdir(parents=True, exist_ok=True)

    sp = _status_path(handle)
    if sp.is_file():
        return _load_state(handle)

    phases: dict[str, Phase] = {}
    now = _now()
    for name in PHASE_ORDER:
        requires = _phase_requires_approval(name, handle.trusted_local)
        phase = Phase(
            name=name,
            status=PENDING,
            requires_approval=requires,
            report_path=_default_report_relpath(name),
        )
        phases[name] = phase

    # Intake is implicitly satisfied: the job exists.
    intake = phases[INTAKE]
    intake.status = COMPLETED
    intake.started_at = now
    intake.completed_at = now
    intake.history.append({
        "from": PENDING,
        "to": COMPLETED,
        "reason": "job submitted",
        "ts": now,
    })

    state = WorkflowState(
        job_id=handle.job_id,
        trusted_local=handle.trusted_local,
        created_at=now,
        updated_at=now,
        current_phase=RESEARCH,
        phases=phases,
    )
    _save_state(handle, state)
    return state


def get_current_phase(job: Any) -> Phase:
    """Return the phase the workflow currently sits at."""

    handle = _coerce_job(job)
    state = _load_state(handle)
    name = state.current_phase
    if name not in state.phases:
        raise WorkflowError(f"current_phase {name!r} missing from state")
    return state.phases[name]


def transition_phase(
    job: Any,
    from_phase: str,
    to_phase: str,
    reason: str,
    *,
    actor: str | None = None,
) -> WorkflowState:
    """Move from ``from_phase`` to ``to_phase``.

    Two transition shapes are recognised:

    * **start** — ``from_phase == to_phase`` and the phase moves from
      ``pending`` to ``running``. Rejected for phases in
      ``ALWAYS_APPROVAL_GATED`` (``approval``, ``publish``) and for
      ``implementation`` when ``trusted_local`` is false.
    * **advance** — ``to_phase`` is the next phase in ``PHASE_ORDER``
      and ``from_phase`` is in a terminal status (``completed`` or
      ``approved``). Approval-gated destination phases land in
      ``needs_approval``; everything else lands in ``running``.

    ``reason`` is required and recorded in the audit trail. Backward
    transitions and arbitrary skips raise
    :class:`InvalidTransitionError`. Use ``reject_phase`` for the
    "approval was denied" case — it has its own semantics.
    """

    handle = _coerce_job(job)
    _ensure_known_phase(from_phase)
    _ensure_known_phase(to_phase)
    if not (reason or "").strip():
        raise WorkflowError("transition_phase requires a non-empty reason")

    state = _load_state(handle)
    src = state.phases[from_phase]
    dst = state.phases[to_phase]
    now = _now()
    reason_clean = reason.strip()

    # ── Start-in-place ──────────────────────────────────────────────
    if from_phase == to_phase:
        if src.status != PENDING:
            raise InvalidTransitionError(
                f"cannot start phase {from_phase!r} from status {src.status!r}"
            )
        if from_phase in ALWAYS_APPROVAL_GATED:
            raise InvalidTransitionError(
                f"phase {from_phase!r} requires approval before it can run; "
                "call approve_phase first"
            )
        if from_phase == IMPLEMENTATION and not state.trusted_local:
            raise InvalidTransitionError(
                "implementation requires approval unless trusted_local is set"
            )
        if from_phase == PLANNING and not _has_evidence(
            state, RESEARCH, handle
        ):
            raise InvalidTransitionError(
                "planning cannot start until research has produced a "
                "non-empty report"
            )
        if from_phase == VALIDATION and state.phases[IMPLEMENTATION].status not in TERMINAL_STATUSES:
            raise InvalidTransitionError(
                "validation cannot start until implementation has completed"
            )
        src.status = RUNNING
        src.started_at = src.started_at or now
        src.history.append({
            "from": PENDING,
            "to": RUNNING,
            "reason": reason_clean,
            "actor": actor,
            "ts": now,
        })
        state.current_phase = from_phase
        _save_state(handle, state)
        return state

    # ── Advance to next phase ───────────────────────────────────────
    src_idx = _phase_index(from_phase)
    dst_idx = _phase_index(to_phase)
    if dst_idx != src_idx + 1:
        raise InvalidTransitionError(
            f"cannot transition {from_phase!r} -> {to_phase!r}: phases must "
            "advance one step at a time in PHASE_ORDER"
        )
    if src.status not in TERMINAL_STATUSES:
        raise InvalidTransitionError(
            f"cannot leave phase {from_phase!r}: status is {src.status!r}, "
            f"expected one of {sorted(TERMINAL_STATUSES)}"
        )

    # Per-destination gate checks.
    if to_phase == PLANNING and not _has_evidence(state, RESEARCH, handle):
        raise InvalidTransitionError(
            "planning cannot start until research has produced a non-empty "
            "report (see write_phase_report)"
        )
    if to_phase == IMPLEMENTATION and not state.trusted_local:
        approval = state.phases[APPROVAL]
        if approval.status != APPROVED:
            raise InvalidTransitionError(
                "implementation requires explicit approval; the approval "
                "phase has not been approved yet"
            )

    # Approval-gated destinations land in needs_approval; everything
    # else lands in running.
    if to_phase in ALWAYS_APPROVAL_GATED:
        new_status = NEEDS_APPROVAL
        dst.requires_approval = True
    else:
        new_status = RUNNING
        dst.started_at = now

    prev_status = dst.status
    dst.status = new_status
    dst.history.append({
        "from": prev_status,
        "to": new_status,
        "reason": reason_clean,
        "actor": actor,
        "ts": now,
    })
    state.current_phase = to_phase
    _save_state(handle, state)
    return state


def complete_phase(
    job: Any,
    phase: str,
    *,
    reason: str = "completed",
) -> WorkflowState:
    """Mark ``phase`` as ``completed`` and stamp ``completed_at``.

    This is the normal "the work for this phase is done" call. It does
    *not* advance to the next phase — callers should follow up with
    ``transition_phase`` (or rely on ``advance`` from a higher layer).

    The ``approval`` phase cannot be completed via this function; it
    must be approved (``approve_phase``) or rejected (``reject_phase``).
    """

    handle = _coerce_job(job)
    _ensure_known_phase(phase)
    if phase == APPROVAL:
        raise InvalidTransitionError(
            "the approval phase is completed by approve_phase / reject_phase, "
            "not complete_phase"
        )
    state = _load_state(handle)
    ph = state.phases[phase]
    if ph.status in TERMINAL_STATUSES:
        return state
    if ph.status not in (RUNNING, BLOCKED):
        raise InvalidTransitionError(
            f"cannot complete phase {phase!r} from status {ph.status!r}"
        )
    now = _now()
    prev = ph.status
    ph.status = COMPLETED
    ph.completed_at = now
    ph.history.append({
        "from": prev,
        "to": COMPLETED,
        "reason": reason,
        "ts": now,
    })
    _save_state(handle, state)
    return state


def fail_phase(
    job: Any,
    phase: str,
    reason: str,
) -> WorkflowState:
    """Mark ``phase`` as ``failed`` with ``reason`` recorded."""

    handle = _coerce_job(job)
    _ensure_known_phase(phase)
    if not (reason or "").strip():
        raise WorkflowError("fail_phase requires a non-empty reason")
    state = _load_state(handle)
    ph = state.phases[phase]
    now = _now()
    prev = ph.status
    ph.status = FAILED
    ph.completed_at = now
    ph.rejection_reason = reason
    ph.history.append({
        "from": prev,
        "to": FAILED,
        "reason": reason,
        "ts": now,
    })
    _save_state(handle, state)
    return state


def require_approval(
    job: Any,
    phase: str,
    action: str,
    *,
    reason: str | None = None,
) -> WorkflowState:
    """Mark ``phase`` as ``needs_approval`` because ``action`` requires it.

    ``action`` is a free-form label (e.g. ``"destructive"``,
    ``"secrets"``, ``"publish pull request"``). The two reserved
    labels ``"destructive"`` and ``"secrets"`` always escalate to
    ``needs_approval`` regardless of ``trusted_local``.
    """

    handle = _coerce_job(job)
    _ensure_known_phase(phase)
    action_key = (action or "").strip()
    if not action_key:
        raise WorkflowError("require_approval requires an action label")
    state = _load_state(handle)
    ph = state.phases[phase]

    # Destructive / secrets always escalate.
    forced = action_key.lower() in ALWAYS_APPROVED_ACTIONS

    if (
        not forced
        and state.trusted_local
        and phase not in ALWAYS_APPROVAL_GATED
    ):
        # Trusted-local downgrades implementation-style gates, but the
        # caller still asked for approval — record it as informational
        # in the history without flipping status.
        ph.history.append({
            "kind": "require_approval",
            "action": action_key,
            "result": "auto-approved by trusted_local",
            "reason": reason or "",
            "ts": _now(),
        })
        _save_state(handle, state)
        return state

    now = _now()
    prev = ph.status
    ph.status = NEEDS_APPROVAL
    ph.requires_approval = True
    ph.history.append({
        "from": prev,
        "to": NEEDS_APPROVAL,
        "kind": "require_approval",
        "action": action_key,
        "forced": forced,
        "reason": reason or "",
        "ts": now,
    })
    _save_state(handle, state)
    return state


def approve_phase(
    job: Any,
    phase: str,
    approver: str,
    note: str = "",
) -> WorkflowState:
    """Approve ``phase`` and record who approved it and why.

    ``approver`` is required (an empty string is rejected). ``note`` is
    optional but encouraged. The phase moves from any of
    {``pending``, ``running``, ``needs_approval``, ``blocked``} to
    ``approved``; calling this on a phase already in a terminal status
    is a no-op.
    """

    handle = _coerce_job(job)
    _ensure_known_phase(phase)
    if not (approver or "").strip():
        raise WorkflowError("approve_phase requires a non-empty approver")
    state = _load_state(handle)
    ph = state.phases[phase]
    if ph.status in TERMINAL_STATUSES:
        return state
    if ph.status not in (PENDING, RUNNING, NEEDS_APPROVAL, BLOCKED):
        raise InvalidTransitionError(
            f"cannot approve phase {phase!r} from status {ph.status!r}"
        )
    now = _now()
    prev = ph.status
    ph.status = APPROVED
    ph.completed_at = now
    ph.approver = approver.strip()
    ph.approval_note = (note or "").strip() or None
    ph.history.append({
        "from": prev,
        "to": APPROVED,
        "approver": ph.approver,
        "note": ph.approval_note or "",
        "ts": now,
    })
    _save_state(handle, state)
    return state


def reject_phase(job: Any, phase: str, reason: str) -> WorkflowState:
    """Reject ``phase``. The job is blocked until a caller resolves it.

    A rejected phase keeps its slot in ``current_phase``; the caller is
    expected to either re-run the upstream work, escalate, or
    explicitly mark the job as failed. The audit trail records the
    rejection reason.
    """

    handle = _coerce_job(job)
    _ensure_known_phase(phase)
    if not (reason or "").strip():
        raise WorkflowError("reject_phase requires a non-empty reason")
    state = _load_state(handle)
    ph = state.phases[phase]
    now = _now()
    prev = ph.status
    ph.status = REJECTED
    ph.rejection_reason = reason.strip()
    ph.history.append({
        "from": prev,
        "to": REJECTED,
        "reason": ph.rejection_reason,
        "ts": now,
    })
    _save_state(handle, state)
    return state


def write_phase_report(
    job: Any,
    phase: str,
    content: str,
) -> Path:
    """Write the phase report file for ``phase``.

    Enforces two invariants:

    * the phase must be one of ``REPORT_PHASES`` (intake is bookkeeping
      only);
    * ``content`` must contain a "Plain English" section
      (``## Plain English`` heading, case-insensitive on the heading).

    Returns the absolute :class:`Path` of the written report.
    """

    handle = _coerce_job(job)
    _ensure_known_phase(phase)
    if phase not in REPORT_PHASES:
        raise WorkflowError(
            f"phase {phase!r} does not own a report file (allowed: "
            f"{', '.join(REPORT_PHASES)})"
        )
    body = content or ""
    if not body.strip():
        raise WorkflowError("phase report must not be empty")
    if PLAIN_ENGLISH_HEADING.lower() not in body.lower():
        raise WorkflowError(
            "phase report is missing the required 'Plain English' section "
            "(expected a '## Plain English' heading)"
        )
    _phases_dir(handle).mkdir(parents=True, exist_ok=True)
    report = _report_path(handle, phase)
    report.write_text(body, encoding="utf-8")
    # Record on the phase as well so the on-disk state stays in sync.
    state = _load_state(handle)
    ph = state.phases[phase]
    ph.report_path = _default_report_relpath(phase)
    ph.history.append({
        "kind": "report_written",
        "bytes": len(body.encode("utf-8")),
        "ts": _now(),
    })
    _save_state(handle, state)
    return report


# ──────────────────────────────────────────────────────────────────────
# Convenience accessors
# ──────────────────────────────────────────────────────────────────────


def load_state(job: Any) -> WorkflowState:
    """Return the on-disk :class:`WorkflowState` for ``job``."""

    return _load_state(_coerce_job(job))


def list_phases(job: Any) -> list[Phase]:
    """Return all phases for ``job`` in canonical order."""

    state = _load_state(_coerce_job(job))
    return [state.phases[name] for name in PHASE_ORDER]


__all__ = [
    # exceptions
    "WorkflowError",
    "UnknownPhaseError",
    "InvalidTransitionError",
    "ApprovalRequiredError",
    # job handle
    "JobHandle",
    # API
    "initialize_phases",
    "get_current_phase",
    "transition_phase",
    "complete_phase",
    "fail_phase",
    "require_approval",
    "approve_phase",
    "reject_phase",
    "write_phase_report",
    "load_state",
    "list_phases",
    # constants
    "PHASES_DIRNAME",
    "STATUS_FILE",
    "PLAIN_ENGLISH_HEADING",
]
