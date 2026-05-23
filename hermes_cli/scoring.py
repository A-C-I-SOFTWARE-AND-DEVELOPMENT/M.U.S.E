"""Scoring engine for orchestration proposals.

Inputs: a list of :class:`WorkerResult` objects.
Output: a ranked list of ``(WorkerResult, score)`` tuples with a single
authoritative score per proposal. The score is the weighted sum of
deterministic, locally-computable signals so that ranking does not depend
on an external model call.
"""

from __future__ import annotations

import dataclasses
from typing import Iterable

from hermes_cli.workers.base import WorkerResult


@dataclasses.dataclass(frozen=True)
class ScoreBreakdown:
    success: float
    structure: float
    coverage: float
    hint: float
    total: float

    def to_dict(self) -> dict[str, float]:
        return dataclasses.asdict(self)


# Weights sum to 1.0. Adjusting these is the documented tuning surface.
WEIGHTS: dict[str, float] = {
    "success": 0.30,
    "structure": 0.25,
    "coverage": 0.20,
    "hint": 0.25,
}


def _signal_success(result: WorkerResult) -> float:
    return 1.0 if result.success else 0.0


def _signal_structure(result: WorkerResult) -> float:
    # Reward proposals that follow the documented template
    # (worker header, role, summary).
    proposal = result.proposal or ""
    markers = ("**Worker:**", "**Role:**", "## Summary")
    hits = sum(1 for m in markers if m in proposal)
    return hits / len(markers)


def _signal_coverage(result: WorkerResult) -> float:
    # Tiny coverage proxy: longer proposals (up to a cap) carry more
    # information; we squash with a linear cap at 800 characters.
    length = len(result.proposal or "")
    return max(0.0, min(1.0, length / 800.0))


def _signal_hint(result: WorkerResult) -> float:
    hint = result.score_hint
    if hint < 0.0:
        return 0.0
    if hint > 1.0:
        return 1.0
    return float(hint)


def score_one(result: WorkerResult) -> ScoreBreakdown:
    success = _signal_success(result) * WEIGHTS["success"]
    structure = _signal_structure(result) * WEIGHTS["structure"]
    coverage = _signal_coverage(result) * WEIGHTS["coverage"]
    hint = _signal_hint(result) * WEIGHTS["hint"]
    return ScoreBreakdown(
        success=round(success, 4),
        structure=round(structure, 4),
        coverage=round(coverage, 4),
        hint=round(hint, 4),
        total=round(success + structure + coverage + hint, 4),
    )


def rank(results: Iterable[WorkerResult]) -> list[tuple[WorkerResult, ScoreBreakdown]]:
    """Sort proposals by total score, descending."""
    scored = [(r, score_one(r)) for r in results]
    scored.sort(key=lambda pair: (pair[1].total, pair[0].worker_name), reverse=True)
    return scored


def pick_winner(results: Iterable[WorkerResult]) -> tuple[WorkerResult, ScoreBreakdown] | None:
    ranked = rank(results)
    if not ranked:
        return None
    return ranked[0]
