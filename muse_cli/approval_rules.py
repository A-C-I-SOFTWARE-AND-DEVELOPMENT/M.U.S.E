"""Approval decision race rules (Sprint 9 core).

Pure, storage-agnostic resolution of an owner approval decision under the
race conditions the plan calls out:

* an approval can be **decided once** — a duplicate submit returns the
  existing decision (idempotent), it does not re-decide;
* an **expired** approval rejects a late decision;
* a **superseded** approval rejects a late decision;
* a decision from a **revoked** device is blocked;
* an owner-**phrase mismatch** fails and is flagged for audit.

This is the decision kernel only. Wiring it into the cockpit approval
handler / proposal store (so the live ``POST /v1/cockpit/approvals/{id}``
path enforces these rules) is a deliberate follow-up; keeping the rules in
one pure function means they can be exhaustively tested and reused by every
call site instead of being re-implemented per surface.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional

__all__ = [
    "ApprovalState",
    "DecisionResult",
    "ApprovalRecord",
    "ApprovalDecision",
    "resolve_decision",
]


class ApprovalState(str, enum.Enum):
    """Lifecycle state of a single approval request."""

    PENDING = "pending"
    GRANTED = "granted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


# Once an approval reaches one of these it has been decided and is immutable.
_TERMINAL: frozenset[ApprovalState] = frozenset(
    {ApprovalState.GRANTED, ApprovalState.REJECTED}
)


class DecisionResult(str, enum.Enum):
    """Outcome of attempting to decide an approval."""

    GRANTED = "granted"
    REJECTED = "rejected"
    ALREADY_DECIDED = "already_decided"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    PHRASE_MISMATCH = "phrase_mismatch"
    REVOKED = "revoked"


@dataclass(frozen=True)
class ApprovalRecord:
    """The persisted state a decision is evaluated against."""

    approval_id: str
    state: ApprovalState = ApprovalState.PENDING
    required_phrase: Optional[str] = None
    expires_at: Optional[float] = None
    decided_at: Optional[float] = None
    superseded_by: Optional[str] = None


@dataclass(frozen=True)
class ApprovalDecision:
    """The resolved outcome plus the resulting state and an audit flag."""

    result: DecisionResult
    state: ApprovalState
    audit: bool = False
    detail: str = ""

    @property
    def accepted(self) -> bool:
        """True only when this call actually decided the approval now."""

        return self.result in (DecisionResult.GRANTED, DecisionResult.REJECTED)


def resolve_decision(
    record: ApprovalRecord,
    *,
    approve: bool,
    now: float,
    phrase: Optional[str] = None,
    device_revoked: bool = False,
) -> ApprovalDecision:
    """Resolve a decision attempt against ``record``.

    The checks are ordered by precedence:

    1. **revoked device** — blocked outright (audited);
    2. **already decided** — return the existing decision (idempotent);
    3. **superseded** — a newer request replaced this one;
    4. **expired** — past ``expires_at`` (or already marked expired);
    5. **phrase mismatch** — approving without the exact required phrase
       (audited); rejecting never needs the phrase;
    6. otherwise grant or reject as requested.
    """

    if device_revoked:
        return ApprovalDecision(
            DecisionResult.REVOKED, record.state, audit=True, detail="device revoked"
        )

    if record.state in _TERMINAL or record.decided_at is not None:
        return ApprovalDecision(
            DecisionResult.ALREADY_DECIDED,
            record.state,
            detail="approval already decided",
        )

    if record.state is ApprovalState.SUPERSEDED or record.superseded_by:
        return ApprovalDecision(
            DecisionResult.SUPERSEDED,
            ApprovalState.SUPERSEDED,
            detail="superseded by a newer request",
        )

    if record.state is ApprovalState.EXPIRED or (
        record.expires_at is not None and now > record.expires_at
    ):
        return ApprovalDecision(
            DecisionResult.EXPIRED,
            ApprovalState.EXPIRED,
            detail="expired before decision",
        )

    if approve and record.required_phrase is not None and phrase != record.required_phrase:
        return ApprovalDecision(
            DecisionResult.PHRASE_MISMATCH,
            ApprovalState.PENDING,
            audit=True,
            detail="owner authorization phrase mismatch",
        )

    if approve:
        return ApprovalDecision(DecisionResult.GRANTED, ApprovalState.GRANTED)
    return ApprovalDecision(DecisionResult.REJECTED, ApprovalState.REJECTED)
