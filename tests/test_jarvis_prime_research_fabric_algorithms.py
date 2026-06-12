"""Tests for the executable algorithms-lane verifier (real subprocess execution)."""

from __future__ import annotations

from muse_cli.jarvis_prime.research_fabric.verifier.algorithms import (
    AlgorithmCase,
    AlgorithmTask,
    score_algorithm_candidate,
)


def _sum_task() -> AlgorithmTask:
    return AlgorithmTask(
        task_id="sum_list",
        entrypoint="solve",
        prompt="sum a list",
        public_cases=(AlgorithmCase(args=[[1, 2, 3]], expected=6),),
        holdout_cases=(
            AlgorithmCase(args=[[10, -5, 5]], expected=10),
            AlgorithmCase(args=[[]], expected=0),
        ),
    )


def test_correct_candidate_is_accepted() -> None:
    score = score_algorithm_candidate("def solve(xs):\n    return sum(xs)\n", _sum_task())
    assert score.accepted is True
    assert score.correctness == 1.0
    assert score.ran is True


def test_incorrect_candidate_is_rejected() -> None:
    # Wrong implementation: always returns 0.
    score = score_algorithm_candidate("def solve(xs):\n    return 0\n", _sum_task())
    assert score.accepted is False
    assert score.correctness < 1.0


def test_candidate_that_raises_is_rejected_not_crash() -> None:
    score = score_algorithm_candidate("def solve(xs):\n    raise ValueError('boom')\n", _sum_task())
    assert score.accepted is False
    assert score.correctness == 0.0


def test_missing_entrypoint_is_rejected() -> None:
    score = score_algorithm_candidate("def other(xs):\n    return sum(xs)\n", _sum_task())
    assert score.accepted is False
    assert score.ran is False


def test_partial_correctness_not_accepted() -> None:
    # Passes the empty-list holdout case but not the [10,-5,5] case.
    code = "def solve(xs):\n    return 0 if not xs else 999\n"
    score = score_algorithm_candidate(code, _sum_task())
    assert score.accepted is False
    assert 0.0 < score.correctness < 1.0
