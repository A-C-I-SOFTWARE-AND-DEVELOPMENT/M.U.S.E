"""Goal Boundary Layer — stop runaway autonomous optimization.

The "paperclip" failure mode is an autonomous loop with an objective but no
brakes. This module makes brakes mandatory: every autonomous loop must declare
its objective, allowed/forbidden actions, stop conditions, iteration and cost
ceilings, an owner-approval threshold, and a rollback plan. A loop *without*
stop conditions is refused outright — JARVIS will not run an unbounded loop.

It is stdlib-only and pure: it decides "continue" vs "stop" and explains why,
emitting decision-ledger-compatible records. It does not execute anything and
it does not bypass the existing owner gates — it composes with them, refusing
to continue when a forbidden or owner-gated action is on the table without the
exact authorization phrase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, Optional, Sequence

from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE, OWNER_GATED_ACTIONS


class BoundaryError(ValueError):
    """Raised when a loop is configured without mandatory brakes."""


class StopReason(Enum):
    STOP_CONDITION_MET = "stop_condition_met"
    MAX_ITERATIONS = "max_iterations"
    MAX_COST = "max_cost"
    FORBIDDEN_ACTION = "forbidden_action"
    NEEDS_OWNER_APPROVAL = "needs_owner_approval"
    OBJECTIVE_COMPLETE = "objective_complete"


class Decision(Enum):
    CONTINUE = "continue"
    STOP = "stop"
    NEEDS_OWNER_APPROVAL = "needs_owner_approval"


@dataclass(frozen=True)
class GoalBoundary:
    """The declared brakes for one autonomous loop."""

    objective: str
    allowed_actions: frozenset[str]
    forbidden_actions: frozenset[str] = frozenset()
    stop_conditions: tuple[str, ...] = ()
    max_iterations: int = 0
    max_cost: float = 0.0
    owner_approval_threshold: float = 0.0  # cost above which owner sign-off is required
    rollback_plan: str = ""

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise BoundaryError("goal boundary requires a non-empty objective")
        if not self.stop_conditions and self.max_iterations <= 0 and self.max_cost <= 0:
            raise BoundaryError(
                "refusing autonomous loop: no stop conditions, no max_iterations, no max_cost"
            )
        if not self.rollback_plan.strip():
            raise BoundaryError("goal boundary requires a rollback plan")
        overlap = self.allowed_actions & self.forbidden_actions
        if overlap:
            raise BoundaryError(
                f"actions cannot be both allowed and forbidden: {sorted(overlap)}"
            )

    @classmethod
    def create(
        cls,
        objective: str,
        *,
        allowed_actions: Sequence[str],
        forbidden_actions: Sequence[str] = (),
        stop_conditions: Sequence[str] = (),
        max_iterations: int = 0,
        max_cost: float = 0.0,
        owner_approval_threshold: float = 0.0,
        rollback_plan: str = "",
    ) -> "GoalBoundary":
        return cls(
            objective=objective,
            allowed_actions=frozenset(allowed_actions),
            forbidden_actions=frozenset(forbidden_actions),
            stop_conditions=tuple(stop_conditions),
            max_iterations=max_iterations,
            max_cost=max_cost,
            owner_approval_threshold=owner_approval_threshold,
            rollback_plan=rollback_plan,
        )

    def permits(self, action: str) -> bool:
        if action in self.forbidden_actions:
            return False
        if self.allowed_actions and action not in self.allowed_actions:
            return False
        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "objective": self.objective,
            "allowed_actions": sorted(self.allowed_actions),
            "forbidden_actions": sorted(self.forbidden_actions),
            "stop_conditions": list(self.stop_conditions),
            "max_iterations": self.max_iterations,
            "max_cost": self.max_cost,
            "owner_approval_threshold": self.owner_approval_threshold,
            "rollback_plan": self.rollback_plan,
        }


@dataclass(frozen=True)
class LoopVerdict:
    decision: Decision
    reason: str
    stop_reason: Optional[StopReason] = None
    iteration: int = 0
    cost: float = 0.0

    @property
    def should_continue(self) -> bool:
        return self.decision is Decision.CONTINUE

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "goal_boundary_verdict",
            "decision": self.decision.value,
            "reason": self.reason,
            "stop_reason": self.stop_reason.value if self.stop_reason else None,
            "iteration": self.iteration,
            "cost": round(self.cost, 6),
        }


@dataclass
class LoopController:
    """Tracks an autonomous loop against its :class:`GoalBoundary`.

    Call :meth:`tick` before each iteration with the next planned action and
    its estimated cost; it returns a :class:`LoopVerdict`. Every verdict is
    appended to :attr:`history` so the whole run is auditable.
    """

    boundary: GoalBoundary
    iteration: int = 0
    cost: float = 0.0
    owner_authorization: str = ""
    objective_complete: bool = False
    history: list[LoopVerdict] = field(default_factory=list)

    def authorize(self, phrase: str) -> bool:
        """Record an owner authorization phrase. Only the exact phrase counts."""

        if phrase.strip() == AUTHORIZATION_PHRASE:
            self.owner_authorization = AUTHORIZATION_PHRASE
            return True
        return False

    def mark_complete(self) -> None:
        self.objective_complete = True

    def tick(
        self,
        *,
        next_action: str = "",
        action_cost: float = 0.0,
        signals: Optional[Mapping[str, bool]] = None,
    ) -> LoopVerdict:
        """Decide whether the loop may run one more iteration."""

        signals = signals or {}

        if self.objective_complete:
            return self._record(
                Decision.STOP,
                "objective marked complete",
                StopReason.OBJECTIVE_COMPLETE,
            )

        # Stop conditions are named booleans the caller evaluates each tick.
        for cond in self.boundary.stop_conditions:
            if signals.get(cond):
                return self._record(
                    Decision.STOP,
                    f"stop condition met: {cond}",
                    StopReason.STOP_CONDITION_MET,
                )

        if (
            self.boundary.max_iterations
            and self.iteration >= self.boundary.max_iterations
        ):
            return self._record(
                Decision.STOP,
                f"reached max_iterations={self.boundary.max_iterations}",
                StopReason.MAX_ITERATIONS,
            )

        projected = self.cost + max(0.0, action_cost)
        if self.boundary.max_cost and projected > self.boundary.max_cost:
            return self._record(
                Decision.STOP,
                f"projected cost {projected:.4f} exceeds max_cost {self.boundary.max_cost}",
                StopReason.MAX_COST,
            )

        if next_action and not self.boundary.permits(next_action):
            return self._record(
                Decision.STOP,
                f"action {next_action!r} is forbidden or outside allowed_actions",
                StopReason.FORBIDDEN_ACTION,
            )

        # Owner-gate composition: an owner-gated action, or crossing the cost
        # threshold, requires the exact authorization phrase.
        needs_owner = (next_action in OWNER_GATED_ACTIONS) or (
            self.boundary.owner_approval_threshold
            and projected >= self.boundary.owner_approval_threshold
        )
        if needs_owner and self.owner_authorization != AUTHORIZATION_PHRASE:
            why = (
                f"action {next_action!r} is owner-gated"
                if next_action in OWNER_GATED_ACTIONS
                else f"projected cost {projected:.4f} crosses owner_approval_threshold "
                f"{self.boundary.owner_approval_threshold}"
            )
            return self._record(
                Decision.NEEDS_OWNER_APPROVAL,
                f"{why}; awaiting exact phrase {AUTHORIZATION_PHRASE!r}",
                StopReason.NEEDS_OWNER_APPROVAL,
            )

        # Cleared: advance the loop.
        self.iteration += 1
        self.cost = projected
        return self._record(
            Decision.CONTINUE,
            f"iteration {self.iteration} permitted (cost={self.cost:.4f})",
            None,
        )

    def _record(
        self, decision: Decision, reason: str, stop_reason: Optional[StopReason]
    ) -> LoopVerdict:
        verdict = LoopVerdict(
            decision=decision,
            reason=reason,
            stop_reason=stop_reason,
            iteration=self.iteration,
            cost=self.cost,
        )
        self.history.append(verdict)
        return verdict

    def ledger_records(self, *, job_id: str | None = None) -> list[dict[str, object]]:
        ts = datetime.now(timezone.utc).isoformat()
        out: list[dict[str, object]] = [
            {
                "kind": "goal_boundary_declared",
                "job_id": job_id,
                "created_at": ts,
                "boundary": self.boundary.to_dict(),
            }
        ]
        for v in self.history:
            rec = v.to_dict()
            rec["job_id"] = job_id
            out.append(rec)
        return out
