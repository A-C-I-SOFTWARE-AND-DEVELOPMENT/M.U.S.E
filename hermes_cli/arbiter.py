"""Arbiter — selects which worker proposal(s) reach the merge engine.

The arbiter is the policy layer between scoring and merging. Scoring gives
a ranked list; the arbiter decides whether to pick a single winner, the
top-k, or to declare a draw that requires human input.
"""

from __future__ import annotations

import dataclasses
from typing import Iterable

from hermes_cli.scoring import ScoreBreakdown, rank
from hermes_cli.workers.base import WorkerResult


@dataclasses.dataclass(frozen=True)
class ArbiterDecision:
    selected: list[WorkerResult]
    rationale: str
    requires_human: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "selected": [s.worker_name for s in self.selected],
            "rationale": self.rationale,
            "requires_human": self.requires_human,
        }


# Tunable thresholds. Documented in docs/orchestration/final-10-10-readiness-report.md.
DRAW_MARGIN = 0.02  # Scores within this absolute distance count as a tie.
MIN_PASS_SCORE = 0.40  # Below this, the arbiter abstains and asks for help.


def decide(results: Iterable[WorkerResult]) -> ArbiterDecision:
    ranked = rank(results)
    if not ranked:
        return ArbiterDecision(
            selected=[],
            rationale="no proposals to arbitrate",
            requires_human=True,
        )
    top, top_score = ranked[0]
    if top_score.total < MIN_PASS_SCORE:
        return ArbiterDecision(
            selected=[],
            rationale=(
                f"top score {top_score.total} below minimum {MIN_PASS_SCORE}; "
                "deferring to operator"
            ),
            requires_human=True,
        )

    ties = [top]
    for other, other_score in ranked[1:]:
        if abs(other_score.total - top_score.total) <= DRAW_MARGIN:
            ties.append(other)
        else:
            break

    if len(ties) > 1:
        names = ", ".join(t.worker_name for t in ties)
        return ArbiterDecision(
            selected=ties,
            rationale=f"draw within {DRAW_MARGIN} between: {names}",
            requires_human=False,
        )
    return ArbiterDecision(
        selected=[top],
        rationale=f"clear winner: {top.worker_name} ({top_score.total})",
        requires_human=False,
    )
