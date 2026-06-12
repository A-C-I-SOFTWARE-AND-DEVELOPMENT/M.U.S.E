"""Per-job budget evaluation (Sprint 10 core).

Encodes the plan's budget rule: a **soft** budget overrun asks for owner
confirmation; a **hard** budget overrun stops execution. The check is pure
and unit-agnostic — it works for cost in USD or wall-clock minutes, or any
monotonically-increasing meter.

The three outcomes map onto the unified decision tiers (kept as plain
strings here so this module doesn't import the decision engine; the engine's
``DecisionTier`` uses the same ``auto``/``ask``/``refuse`` vocabulary)::

    WITHIN        -> auto
    SOFT_EXCEEDED -> ask     (owner confirmation)
    HARD_EXCEEDED -> refuse  (stop execution)

Wiring this into the orchestrator's per-job cost/time meters and the
decision engine is a deliberate follow-up; this is the policy kernel and its
tests. Reaching a limit is inclusive (``spent >= limit`` triggers), so a job
that hits its hard cap stops rather than being allowed one more step.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional

__all__ = [
    "BudgetOutcome",
    "BudgetDecision",
    "OUTCOME_TIER",
    "evaluate_budget",
]


class BudgetOutcome(str, enum.Enum):
    """Where ``spent`` sits relative to the soft and hard limits."""

    WITHIN = "within"
    SOFT_EXCEEDED = "soft_exceeded"
    HARD_EXCEEDED = "hard_exceeded"


# Outcome -> unified decision tier (same vocabulary as decision_engine).
OUTCOME_TIER: dict[BudgetOutcome, str] = {
    BudgetOutcome.WITHIN: "auto",
    BudgetOutcome.SOFT_EXCEEDED: "ask",
    BudgetOutcome.HARD_EXCEEDED: "refuse",
}


@dataclass(frozen=True)
class BudgetDecision:
    """The evaluated budget outcome plus the numbers that produced it."""

    outcome: BudgetOutcome
    spent: float
    soft_limit: Optional[float]
    hard_limit: Optional[float]
    meter: str = "cost"
    detail: str = ""

    @property
    def tier(self) -> str:
        """The decision tier this outcome maps to (auto/ask/refuse)."""

        return OUTCOME_TIER[self.outcome]

    @property
    def should_stop(self) -> bool:
        """True when the hard limit is reached — execution must stop."""

        return self.outcome is BudgetOutcome.HARD_EXCEEDED

    @property
    def needs_approval(self) -> bool:
        """True when the soft limit is reached — owner confirmation required."""

        return self.outcome is BudgetOutcome.SOFT_EXCEEDED


def evaluate_budget(
    spent: float,
    *,
    soft_limit: Optional[float] = None,
    hard_limit: Optional[float] = None,
    meter: str = "cost",
) -> BudgetDecision:
    """Classify ``spent`` against the soft/hard limits.

    ``None`` for a limit means that tier never triggers. The hard limit takes
    precedence: if ``spent`` is past both, the outcome is ``HARD_EXCEEDED``.

    Raises:
        ValueError: if ``spent`` is negative, or ``soft_limit > hard_limit``.
    """

    if spent < 0:
        raise ValueError("spent must be >= 0")
    if soft_limit is not None and soft_limit < 0:
        raise ValueError("soft_limit must be >= 0")
    if hard_limit is not None and hard_limit < 0:
        raise ValueError("hard_limit must be >= 0")
    if soft_limit is not None and hard_limit is not None and soft_limit > hard_limit:
        raise ValueError("soft_limit must be <= hard_limit")

    if hard_limit is not None and spent >= hard_limit:
        outcome = BudgetOutcome.HARD_EXCEEDED
        detail = f"{meter}={spent:g} reached hard limit {hard_limit:g}; stop"
    elif soft_limit is not None and spent >= soft_limit:
        outcome = BudgetOutcome.SOFT_EXCEEDED
        detail = (
            f"{meter}={spent:g} reached soft limit {soft_limit:g}; "
            "owner approval required"
        )
    else:
        outcome = BudgetOutcome.WITHIN
        detail = f"{meter}={spent:g} within budget"

    return BudgetDecision(
        outcome=outcome,
        spent=float(spent),
        soft_limit=soft_limit,
        hard_limit=hard_limit,
        meter=meter,
        detail=detail,
    )
