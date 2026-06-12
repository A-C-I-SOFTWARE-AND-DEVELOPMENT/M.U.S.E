"""Plane 2 — self-play curriculum engine (scaffold).

The AZR/POET engine, software-first: a *Proposer* generates coding tasks at the
agent's frontier difficulty (a learnability filter — not too easy / not too
hard), a *Solver* attempts them, and the Plane-1 verifier scores them 0/1. A
ReST-EM loop keeps verifier-passing traces as self-play training data.

This module defines the *interfaces* only. It is deliberately not wired to live
models yet: per the plan, the safety substrate (Planes 0-1) must be airtight
first, and the algorithms lane (purest verifier) is the first proving ground.
No method here fabricates a benchmark result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class Task:
    """One self-generated coding task with an executable verifier hook."""

    task_id: str
    domain: str
    prompt: str
    # An opaque reference the verifier uses to grade a solution (e.g. a test
    # module path, an op-count target, expected I/O). Never the answer itself.
    verifier_ref: str
    difficulty: float = 0.5  # learnability-filtered: kept only if ~not-too-easy/hard
    metadata: dict[str, Any] = field(default_factory=dict)


class Proposer(Protocol):
    def propose(self, *, frontier_difficulty: float, n: int) -> list[Task]:
        """Generate ``n`` tasks near the current frontier difficulty."""


class Solver(Protocol):
    def solve(self, task: Task) -> str:
        """Return a candidate solution (code/diff) for ``task``."""


class Verifier(Protocol):
    def score(self, task: Task, solution: str) -> float:
        """Return a 0..1 score by EXECUTING the solution against ground truth."""


def learnability_keep(score_estimate: float, *, low: float = 0.2, high: float = 0.8) -> bool:
    """POET-style minimal-criterion filter: keep tasks that are neither trivial
    nor impossible for the current solver (estimated solve-rate in ``[low, high]``)."""

    return low <= score_estimate <= high


__all__ = ["Task", "Proposer", "Solver", "Verifier", "learnability_keep"]
