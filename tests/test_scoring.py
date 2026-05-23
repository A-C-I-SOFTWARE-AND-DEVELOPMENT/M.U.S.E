"""Tests for hermes_cli.scoring."""

from __future__ import annotations

import pytest

from hermes_cli.scoring import WEIGHTS, pick_winner, rank, score_one
from hermes_cli.workers.base import WorkerResult


def _make_result(name: str, *, success: bool = True, hint: float = 0.5,
                 length: int = 600, with_template: bool = True) -> WorkerResult:
    if with_template:
        body = (
            "**Worker:** " + name + "\n"
            "**Role:** test\n"
            "## Summary\n"
            + ("x" * max(0, length - 80))
        )
    else:
        body = "x" * length
    return WorkerResult(
        worker_name=name,
        task_id="task1",
        success=success,
        proposal=body,
        score_hint=hint,
    )


def test_weights_sum_to_one() -> None:
    assert pytest.approx(sum(WEIGHTS.values()), rel=1e-6) == 1.0


def test_score_one_obeys_weights() -> None:
    res = _make_result("codex", success=True, hint=1.0, length=1000)
    sb = score_one(res)
    # success (1.0) + structure (3/3) + coverage cap (1.0) + hint (1.0) → all weights.
    assert sb.total == pytest.approx(1.0, abs=1e-4)


def test_score_one_failed_proposal() -> None:
    res = _make_result("codex", success=False, hint=0.0, length=0, with_template=False)
    sb = score_one(res)
    assert sb.total == pytest.approx(0.0, abs=1e-6)
    assert sb.success == 0.0


def test_rank_orders_by_total_desc() -> None:
    high = _make_result("high", hint=0.9, length=800)
    mid = _make_result("mid", hint=0.5, length=400)
    low = _make_result("low", hint=0.1, length=120)
    ranked = rank([low, mid, high])
    assert [r[0].worker_name for r in ranked] == ["high", "mid", "low"]


def test_rank_breaks_ties_by_name() -> None:
    a = _make_result("alpha", hint=0.5, length=400)
    b = _make_result("bravo", hint=0.5, length=400)
    ranked = rank([b, a])
    # Both score identically; tie-break is by name descending.
    assert [r[0].worker_name for r in ranked] == ["bravo", "alpha"]


def test_pick_winner_returns_top() -> None:
    a = _make_result("a", hint=0.2, length=200)
    b = _make_result("b", hint=0.9, length=800)
    winner = pick_winner([a, b])
    assert winner is not None
    assert winner[0].worker_name == "b"


def test_pick_winner_empty() -> None:
    assert pick_winner([]) is None


def test_score_clamps_hint_above_one() -> None:
    res = _make_result("x", hint=10.0, length=800)
    sb = score_one(res)
    assert sb.hint <= WEIGHTS["hint"]


def test_score_clamps_hint_below_zero() -> None:
    res = _make_result("x", hint=-5.0, length=800)
    sb = score_one(res)
    assert sb.hint == 0.0
