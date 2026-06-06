"""A runnable ReST-EM self-play loop for the algorithms lane.

Engine: a Proposer yields tasks at the frontier difficulty, a Solver produces
candidate code, the executable verifier (:mod:`research_fabric.verifier.algorithms`)
scores it 0/1, and verifier-accepted solutions are kept as training traces
(generate -> filter-by-verifier -> keep; arXiv:2312.06585 / 2505.03335). The
learnability filter keeps only tasks that are neither trivial nor impossible.

This is fully runnable without external models: inject any ``solver`` callable
(``solve(task) -> code``). A real LLM solver plugs in unchanged. Every accepted
trace is optionally appended to the hash-chained ledger for provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

from ..verifier.algorithms import AlgorithmScore, AlgorithmTask, score_algorithm_candidate
from . import learnability_keep

Solver = Callable[[AlgorithmTask], str]


@dataclass(frozen=True)
class AcceptedTrace:
    task_id: str
    code: str
    score: AlgorithmScore

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "code": self.code,
            "score": self.score.to_dict(),
        }


@dataclass
class SelfPlayResult:
    proposed: int
    attempted: int
    accepted: list[AcceptedTrace] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    skipped_unlearnable: int = 0

    @property
    def acceptance_rate(self) -> float:
        return round(len(self.accepted) / self.attempted, 4) if self.attempted else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposed": self.proposed,
            "attempted": self.attempted,
            "accepted_count": len(self.accepted),
            "acceptance_rate": self.acceptance_rate,
            "skipped_unlearnable": self.skipped_unlearnable,
            "accepted": [t.to_dict() for t in self.accepted],
            "rejected": self.rejected,
        }


def run_selfplay(
    tasks: Sequence[AlgorithmTask],
    solver: Solver,
    *,
    difficulty_estimator: Optional[Callable[[AlgorithmTask], float]] = None,
    ledger: Optional[GuardrailLedger] = None,
    apply_learnability_filter: bool = True,
) -> SelfPlayResult:
    """Run one self-play pass over ``tasks`` with ``solver`` and the verifier."""

    result = SelfPlayResult(proposed=len(tasks), attempted=0)
    for task in tasks:
        if apply_learnability_filter and difficulty_estimator is not None:
            est = difficulty_estimator(task)
            if not learnability_keep(est):
                result.skipped_unlearnable += 1
                continue
        result.attempted += 1
        try:
            code = solver(task)
        except Exception as exc:  # noqa: BLE001 - a solver failure is just a rejection
            result.rejected.append({"task_id": task.task_id, "reason": f"solver error: {exc}"})
            continue
        score = score_algorithm_candidate(code, task)
        if score.accepted:
            trace = AcceptedTrace(task_id=task.task_id, code=code, score=score)
            result.accepted.append(trace)
            if ledger is not None:
                ledger.append(
                    "selfplay_accept",
                    task.task_id,
                    {"score": score.to_dict(), "code_sha_len": len(code)},
                )
        else:
            result.rejected.append(
                {"task_id": task.task_id, "reason": score.detail, "score": score.to_dict()}
            )
            if ledger is not None:
                ledger.append(
                    "selfplay_reject",
                    task.task_id,
                    {"detail": score.detail, "correctness": score.correctness},
                )
    return result


__all__ = ["Solver", "AcceptedTrace", "SelfPlayResult", "run_selfplay"]
