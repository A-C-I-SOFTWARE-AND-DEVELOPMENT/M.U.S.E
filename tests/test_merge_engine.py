"""Tests for hermes_cli.merge_engine and the arbiter feeding it."""

from __future__ import annotations

import pytest

from hermes_cli.arbiter import DRAW_MARGIN, MIN_PASS_SCORE, decide
from hermes_cli.merge_engine import MergeArtifact, merge
from hermes_cli.workers.base import WorkerResult


def _proposal(name: str, hint: float, *, length: int = 600) -> WorkerResult:
    body = (
        f"**Worker:** {name}\n"
        f"**Role:** test\n"
        "## Summary\n"
        + ("x" * max(0, length - 80))
    )
    return WorkerResult(
        worker_name=name,
        task_id="t",
        success=True,
        proposal=body,
        score_hint=hint,
        metadata={"role": "test"},
    )


def test_arbiter_returns_winner_when_clear() -> None:
    a = _proposal("alpha", 0.9, length=800)
    b = _proposal("bravo", 0.2, length=200)
    d = decide([a, b])
    assert not d.requires_human
    assert [s.worker_name for s in d.selected] == ["alpha"]


def test_arbiter_flags_human_when_below_minimum() -> None:
    # Construct proposals with low success and no template markers so the
    # total score is reliably below MIN_PASS_SCORE.
    bad = WorkerResult(
        worker_name="bad",
        task_id="t",
        success=False,
        proposal="empty",
        score_hint=0.0,
    )
    worse = WorkerResult(
        worker_name="worse",
        task_id="t",
        success=False,
        proposal="",
        score_hint=0.0,
    )
    d = decide([bad, worse])
    assert d.requires_human
    assert d.selected == []


def test_arbiter_detects_draw() -> None:
    a = _proposal("alpha", 0.9, length=800)
    b = _proposal("bravo", 0.9, length=800)
    d = decide([a, b])
    assert sorted(s.worker_name for s in d.selected) == ["alpha", "bravo"]
    assert not d.requires_human


def test_arbiter_handles_empty() -> None:
    d = decide([])
    assert d.requires_human
    assert d.selected == []


def test_merge_single_winner_forwards_proposal() -> None:
    a = _proposal("alpha", 0.9, length=800)
    d = decide([a])
    art = merge(d, task_title="task title")
    assert isinstance(art, MergeArtifact)
    assert not art.is_draw
    assert art.contributors == ["alpha"]
    assert "alpha" in art.body


def test_merge_draw_preserves_all_contributors() -> None:
    a = _proposal("alpha", 0.9, length=800)
    b = _proposal("bravo", 0.9, length=800)
    d = decide([a, b])
    art = merge(d, task_title="draw task")
    assert art.is_draw
    assert set(art.contributors) == {"alpha", "bravo"}
    assert "alpha" in art.body and "bravo" in art.body
    assert "draw" in art.title


def test_merge_no_selection_returns_explanation() -> None:
    d = decide([])
    art = merge(d, task_title="empty")
    assert art.contributors == []
    assert "abstained" in art.body.lower() or "no proposals" in art.body.lower()


def test_draw_margin_threshold_constants() -> None:
    assert 0.0 < DRAW_MARGIN < 0.1
    assert 0.0 < MIN_PASS_SCORE < 1.0
