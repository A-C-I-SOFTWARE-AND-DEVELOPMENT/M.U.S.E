"""Data models for the phase-gated workflow engine.

This module owns the *shape* of a phase-gated workflow:

  * the canonical phase ordering,
  * the canonical phase statuses,
  * the rules that say which phases can start automatically and which
    require explicit human approval,
  * the dataclasses (:class:`Phase` and :class:`WorkflowState`) that
    persist to disk inside a job folder.

All logic that *mutates* this state lives in
:mod:`muse_cli.workflows`. Keeping the two concerns separated mirrors
the split between ``orchestrator_models`` and ``job_controller``.

The on-disk layout owned by a phase-gated workflow looks like::

    <job_dir>/
        phases/
            research.md
            planning.md
            approval.md
            implementation.md
            validation.md
            publish.md
            retrospective.md
        status.json

The ``status.json`` file is the serialized :class:`WorkflowState`. Each
``phases/<name>.md`` is a free-form report written by
``write_phase_report``; every report is expected to include a
"Plain English" section, but we do not parse the file beyond that.

Strings (not Enum) are used for phase names and statuses so the JSON
round-trips cleanly and is hand-editable when something goes wrong in
the field.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# ──────────────────────────────────────────────────────────────────────
# Phase names — canonical order matters
# ──────────────────────────────────────────────────────────────────────

INTAKE = "intake"
RESEARCH = "research"
PLANNING = "planning"
APPROVAL = "approval"
IMPLEMENTATION = "implementation"
VALIDATION = "validation"
PUBLISH = "publish"
RETROSPECTIVE = "retrospective"

#: Canonical ordering of the eight phases every job moves through.
PHASE_ORDER: tuple[str, ...] = (
    INTAKE,
    RESEARCH,
    PLANNING,
    APPROVAL,
    IMPLEMENTATION,
    VALIDATION,
    PUBLISH,
    RETROSPECTIVE,
)

#: Phases that own a ``phases/<name>.md`` report file.
#: Intake is bookkeeping only — its evidence lives in ``status.json``.
REPORT_PHASES: tuple[str, ...] = (
    RESEARCH,
    PLANNING,
    APPROVAL,
    IMPLEMENTATION,
    VALIDATION,
    PUBLISH,
    RETROSPECTIVE,
)


# ──────────────────────────────────────────────────────────────────────
# Statuses
# ──────────────────────────────────────────────────────────────────────

PENDING = "pending"
RUNNING = "running"
BLOCKED = "blocked"
NEEDS_APPROVAL = "needs_approval"
APPROVED = "approved"
REJECTED = "rejected"
COMPLETED = "completed"
FAILED = "failed"

PHASE_STATUSES: frozenset[str] = frozenset({
    PENDING,
    RUNNING,
    BLOCKED,
    NEEDS_APPROVAL,
    APPROVED,
    REJECTED,
    COMPLETED,
    FAILED,
})

#: Statuses that mean "this phase is finished; the next one is free to
#: be considered". ``APPROVED`` counts because the approval phase itself
#: completes by being approved.
TERMINAL_STATUSES: frozenset[str] = frozenset({COMPLETED, APPROVED})


# ──────────────────────────────────────────────────────────────────────
# Gate rules
# ──────────────────────────────────────────────────────────────────────

#: Phases that may be started without explicit human approval when
#: ``trusted_local`` is false. ``approve_phase`` is still the way an
#: approval-gated phase becomes ``approved``; this set just answers
#: "can the engine flip this phase to running on its own?".
AUTO_STARTABLE: frozenset[str] = frozenset({
    INTAKE,
    RESEARCH,
    VALIDATION,
    RETROSPECTIVE,
})

#: Phases that always require an explicit ``approve_phase`` call before
#: they can move out of ``needs_approval``. ``trusted_local`` can downgrade
#: ``IMPLEMENTATION`` (see ``workflows.require_approval``) but never
#: ``APPROVAL`` or ``PUBLISH``.
ALWAYS_APPROVAL_GATED: frozenset[str] = frozenset({
    APPROVAL,
    PUBLISH,
})

#: Kinds of actions that *always* trigger an approval gate, regardless
#: of ``trusted_local``. These are checked by ``require_approval``.
ALWAYS_APPROVED_ACTIONS: frozenset[str] = frozenset({
    "destructive",
    "secrets",
})


# ──────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────


@dataclass
class Phase:
    """One phase within a phase-gated workflow.

    ``history`` is an append-only audit trail of status transitions for
    this phase. Every transition recorded by :mod:`muse_cli.workflows`
    appends one entry shaped roughly like::

        {"from": "pending", "to": "running", "reason": "…", "ts": 1234}

    The reason / approver fields are free-form on purpose — the gate
    cares about *that* a transition happened with a reason, not about
    forcing a controlled vocabulary on humans writing the reason.
    """

    name: str
    status: str = PENDING
    started_at: int | None = None
    completed_at: int | None = None
    approver: str | None = None
    approval_note: str | None = None
    rejection_reason: str | None = None
    requires_approval: bool = False
    report_path: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Phase":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        kwargs: dict[str, Any] = {k: v for k, v in data.items() if k in known}
        kwargs.setdefault("name", data.get("name") or "")
        if not kwargs["name"]:
            raise ValueError("Phase requires a name")
        return cls(**kwargs)


@dataclass
class WorkflowState:
    """Serialized state for a phase-gated workflow.

    Persisted as ``<job_dir>/status.json``. The orchestrator owns the
    rest of the on-disk layout; this dataclass is concerned only with
    "which phase are we in, what does each phase look like, and what is
    the audit trail?".
    """

    job_id: str
    trusted_local: bool = False
    created_at: int = 0
    updated_at: int = 0
    current_phase: str = INTAKE
    phases: dict[str, Phase] = field(default_factory=dict)

    # ── serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "trusted_local": self.trusted_local,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_phase": self.current_phase,
            "phases": {name: phase.to_dict() for name, phase in self.phases.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowState":
        phases_raw = data.get("phases") or {}
        phases: dict[str, Phase] = {}
        if isinstance(phases_raw, dict):
            for name, payload in phases_raw.items():
                if not isinstance(payload, dict):
                    continue
                payload.setdefault("name", name)
                try:
                    phases[name] = Phase.from_dict(payload)
                except Exception:
                    continue
        return cls(
            job_id=str(data.get("job_id") or ""),
            trusted_local=bool(data.get("trusted_local", False)),
            created_at=int(data.get("created_at") or 0),
            updated_at=int(data.get("updated_at") or 0),
            current_phase=str(data.get("current_phase") or INTAKE),
            phases=phases,
        )


__all__ = [
    # phase names
    "INTAKE",
    "RESEARCH",
    "PLANNING",
    "APPROVAL",
    "IMPLEMENTATION",
    "VALIDATION",
    "PUBLISH",
    "RETROSPECTIVE",
    "PHASE_ORDER",
    "REPORT_PHASES",
    # statuses
    "PENDING",
    "RUNNING",
    "BLOCKED",
    "NEEDS_APPROVAL",
    "APPROVED",
    "REJECTED",
    "COMPLETED",
    "FAILED",
    "PHASE_STATUSES",
    "TERMINAL_STATUSES",
    # gate rules
    "AUTO_STARTABLE",
    "ALWAYS_APPROVAL_GATED",
    "ALWAYS_APPROVED_ACTIONS",
    # dataclasses
    "Phase",
    "WorkflowState",
]
