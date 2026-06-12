"""Seed algorithm tasks + a reference solver for the self-play lane.

These make the self-play loop runnable end-to-end with no external model: the
reference solver returns known-good implementations keyed by task id, so the
verifier accepts them. A real LLM solver implements the same ``solve(task)->code``
signature and drops in unchanged. The held-out cases are never shown to a solver.
"""

from __future__ import annotations

from ..verifier.algorithms import AlgorithmCase, AlgorithmTask

SEED_TASKS: tuple[AlgorithmTask, ...] = (
    AlgorithmTask(
        task_id="sum_list",
        entrypoint="solve",
        prompt="Return the sum of a list of integers.",
        public_cases=(
            AlgorithmCase(args=[[1, 2, 3]], expected=6),
            AlgorithmCase(args=[[]], expected=0),
        ),
        holdout_cases=(
            AlgorithmCase(args=[[10, -5, 5]], expected=10),
            AlgorithmCase(args=[[100]], expected=100),
        ),
    ),
    AlgorithmTask(
        task_id="reverse_str",
        entrypoint="solve",
        prompt="Return the reverse of a string.",
        public_cases=(
            AlgorithmCase(args=["abc"], expected="cba"),
        ),
        holdout_cases=(
            AlgorithmCase(args=["hermes"], expected="semreh"),
            AlgorithmCase(args=[""], expected=""),
        ),
    ),
    AlgorithmTask(
        task_id="sort_ints",
        entrypoint="solve",
        prompt="Return the list sorted ascending.",
        public_cases=(
            AlgorithmCase(args=[[3, 1, 2]], expected=[1, 2, 3]),
        ),
        holdout_cases=(
            AlgorithmCase(args=[[5, 5, 1]], expected=[1, 5, 5]),
            AlgorithmCase(args=[[]], expected=[]),
        ),
    ),
)

_REFERENCE_SOLUTIONS: dict[str, str] = {
    "sum_list": "def solve(xs):\n    return sum(xs)\n",
    "reverse_str": "def solve(s):\n    return s[::-1]\n",
    "sort_ints": "def solve(xs):\n    return sorted(xs)\n",
}


def reference_solver(task: AlgorithmTask) -> str:
    """A deterministic correct solver for the seed tasks (stand-in for an LLM)."""

    return _REFERENCE_SOLUTIONS.get(task.task_id, "def solve(*a):\n    return None\n")


# --- Evolution demo: a correct-but-wasteful baseline the loop can improve. ---

DEMO_EVOLVE_TASK: AlgorithmTask = next(t for t in SEED_TASKS if t.task_id == "sum_list")

# Correct but does O(n) explicit Python-level work (many traced lines).
DEMO_BASELINE_CODE = (
    "def solve(xs):\n"
    "    total = 0\n"
    "    for x in xs:\n"
    "        total = total + x\n"
    "    return total\n"
)

# An optimized, still-correct rewrite (one traced line; the loop runs in C).
_DEMO_OPTIMIZED_CODE = "def solve(xs):\n    return sum(xs)\n"


def demo_variant_proposer(_best_code: str) -> list[str]:
    """Stand-in mutator: proposes the optimized rewrite (an LLM plugs in here)."""

    return [_DEMO_OPTIMIZED_CODE]


__all__ = [
    "SEED_TASKS",
    "reference_solver",
    "DEMO_EVOLVE_TASK",
    "DEMO_BASELINE_CODE",
    "demo_variant_proposer",
]
