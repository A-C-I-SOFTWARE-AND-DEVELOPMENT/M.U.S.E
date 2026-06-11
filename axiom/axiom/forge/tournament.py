"""Tournaments with a hard symbolic gate and a kill-switch (defends I2
against reward hacking).

The only unbeatable judge is a theorem: a candidate that fails the
verifier gate gets rating 0 by law and never duels — no panel of soft
judges can resurrect it. A rating jump above KILL_SWITCH_DELTA in a
single update halts the tournament and raises a ledger alarm; a true
champion earns its rating one duel at a time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..core.ledger import Ledger
from . import ratings
from .ratings import Rating

GATE_FAILED_RATING = 0.0
KILL_SWITCH_DELTA = 400.0


class KillSwitch(RuntimeError):
    """A rating moved too far too fast; the tournament is halted."""


@dataclass
class Candidate:
    cid: str
    payload: dict = field(default_factory=dict)
    rating: Rating = field(default_factory=Rating)
    gate_passed: bool | None = None


class Tournament:
    """Hard-gated duel tournament over a candidate pool."""

    def __init__(self, ledger: Ledger):
        self.ledger = ledger
        self.candidates: dict[str, Candidate] = {}
        self.halted = False

    def add(self, candidate: Candidate) -> None:
        self.candidates[candidate.cid] = candidate

    # ------------------------------------------------------------- hard gate
    def gate(self, verify: Callable[[Candidate], bool]) -> list[str]:
        """Run the symbolic gate. Failures get rating 0 — by law, not
        by judgment. Returns the cids that failed."""
        failed: list[str] = []
        for cand in self.candidates.values():
            cand.gate_passed = bool(verify(cand))
            if not cand.gate_passed:
                cand.rating = Rating(
                    rating=GATE_FAILED_RATING, rd=ratings.DEFAULT_RD,
                    vol=ratings.DEFAULT_VOL,
                )
                failed.append(cand.cid)
                self.ledger.append(
                    "forge_gate_fail",
                    {"cid": cand.cid, "reason": "verifier gate failed"},
                )
        return failed

    # ----------------------------------------------------------------- duels
    def duel(self, a: str, b: str, winner: str) -> None:
        """Record one duel and update both ratings (one-game period)."""
        if self.halted:
            raise KillSwitch("tournament is halted")
        ca, cb = self.candidates[a], self.candidates[b]
        if not (ca.gate_passed and cb.gate_passed):
            raise ValueError("gate-failed candidates never duel")
        score_a = ratings.WIN if winner == a else ratings.LOSS
        new_a = ratings.update(
            ca.rating, [(cb.rating.rating, cb.rating.rd, score_a)]
        )
        new_b = ratings.update(
            cb.rating, [(ca.rating.rating, ca.rating.rd, 1.0 - score_a)]
        )
        self._guard(ca, new_a)
        self._guard(cb, new_b)
        ca.rating, cb.rating = new_a, new_b
        self.ledger.append(
            "forge_duel",
            {"a": a, "b": b, "winner": winner,
             "rating_a": new_a.rating, "rating_b": new_b.rating},
        )

    def _guard(self, cand: Candidate, new: Rating) -> None:
        delta = abs(new.rating - cand.rating.rating)
        if delta > KILL_SWITCH_DELTA:
            self.halted = True
            self.ledger.append(
                "forge_kill_switch",
                {"cid": cand.cid, "reason": f"rating jump {delta:.1f} > "
                                            f"{KILL_SWITCH_DELTA}"},
            )
            raise KillSwitch(
                f"candidate {cand.cid} rating jumped {delta:.1f} points"
            )

    # -------------------------------------------------------------- champion
    def champion(self) -> Candidate:
        """Highest-rated gate-passed candidate. Gate failures can never
        win regardless of judges — their rating is 0 by law."""
        passed = [c for c in self.candidates.values() if c.gate_passed]
        if not passed:
            raise ValueError("no gate-passed candidates")
        return max(passed, key=lambda c: c.rating.rating)
