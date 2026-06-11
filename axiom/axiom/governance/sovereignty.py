"""The three sovereignty (anti-goal) clauses as constitutional checks
with coverage counts (Phase 6.3).

  1. interruption: the system must always be interruptible. (Stub:
     always answers yes; the counter proves the question was asked.)
  2. why_attached: no decision is recorded without its why.
  3. oracle: no answer above the confidence threshold without an
     attestation reference — confidence without evidence is the
     oracle failure mode, and it is forbidden.

Coverage counts make the constitution auditable: a clause that is
never checked is not a protection, it is a decoration.
"""

from __future__ import annotations

ORACLE_CONFIDENCE_THRESHOLD = 0.8


class Sovereignty:
    """Anti-goal counters: checked / violations per clause."""

    def __init__(self):
        self._counts = {
            "interruption": {"checked": 0, "violations": 0},
            "why_attached": {"checked": 0, "violations": 0},
            "oracle": {"checked": 0, "violations": 0},
        }

    def check_interruptible(self, action: dict) -> bool:
        """Interruption-threshold stub: every action is interruptible.
        The counter records that the clause was consulted."""
        self._counts["interruption"]["checked"] += 1
        return True

    def check_decision_has_why(self, decision: dict) -> bool:
        self._counts["why_attached"]["checked"] += 1
        ok = bool(decision.get("why"))
        if not ok:
            self._counts["why_attached"]["violations"] += 1
        return ok

    def check_answer(
        self, confidence: float, attestation_ref: str | None
    ) -> bool:
        """The oracle check: high confidence requires an attestation."""
        self._counts["oracle"]["checked"] += 1
        ok = confidence <= ORACLE_CONFIDENCE_THRESHOLD or bool(attestation_ref)
        if not ok:
            self._counts["oracle"]["violations"] += 1
        return ok

    def coverage(self) -> dict:
        return {k: dict(v) for k, v in self._counts.items()}
