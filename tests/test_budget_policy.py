"""Tests for per-job budget evaluation (Sprint 10)."""

from __future__ import annotations

import pytest

from hermes_cli.budget_policy import (
    BudgetOutcome,
    evaluate_budget,
)


def test_within_budget():
    d = evaluate_budget(5.0, soft_limit=8.0, hard_limit=10.0)
    assert d.outcome is BudgetOutcome.WITHIN
    assert d.tier == "auto"
    assert not d.should_stop
    assert not d.needs_approval


def test_exactly_at_soft_is_soft_exceeded():
    d = evaluate_budget(8.0, soft_limit=8.0, hard_limit=10.0)
    assert d.outcome is BudgetOutcome.SOFT_EXCEEDED
    assert d.tier == "ask"
    assert d.needs_approval
    assert not d.should_stop


def test_between_soft_and_hard_is_soft_exceeded():
    d = evaluate_budget(9.0, soft_limit=8.0, hard_limit=10.0)
    assert d.outcome is BudgetOutcome.SOFT_EXCEEDED


def test_exactly_at_hard_is_hard_exceeded():
    d = evaluate_budget(10.0, soft_limit=8.0, hard_limit=10.0)
    assert d.outcome is BudgetOutcome.HARD_EXCEEDED
    assert d.tier == "refuse"
    assert d.should_stop


def test_above_hard_is_hard_exceeded():
    d = evaluate_budget(99.0, soft_limit=8.0, hard_limit=10.0)
    assert d.outcome is BudgetOutcome.HARD_EXCEEDED


def test_hard_takes_precedence_when_past_both():
    # spent past both soft and hard -> hard wins
    d = evaluate_budget(50.0, soft_limit=10.0, hard_limit=20.0)
    assert d.outcome is BudgetOutcome.HARD_EXCEEDED


def test_only_soft_limit_set():
    assert evaluate_budget(5.0, soft_limit=8.0).outcome is BudgetOutcome.WITHIN
    assert evaluate_budget(8.0, soft_limit=8.0).outcome is BudgetOutcome.SOFT_EXCEEDED


def test_only_hard_limit_set():
    assert evaluate_budget(5.0, hard_limit=10.0).outcome is BudgetOutcome.WITHIN
    assert evaluate_budget(10.0, hard_limit=10.0).outcome is BudgetOutcome.HARD_EXCEEDED


def test_no_limits_is_always_within():
    d = evaluate_budget(1_000_000.0)
    assert d.outcome is BudgetOutcome.WITHIN
    assert d.tier == "auto"


def test_meter_label_in_detail():
    cost = evaluate_budget(2.0, hard_limit=1.0, meter="cost")
    minutes = evaluate_budget(40.0, hard_limit=30.0, meter="minutes")
    assert "cost=" in cost.detail
    assert "minutes=" in minutes.detail


def test_zero_spent_within():
    assert evaluate_budget(0.0, soft_limit=1.0, hard_limit=2.0).outcome is BudgetOutcome.WITHIN


@pytest.mark.parametrize(
    "outcome,tier",
    [
        (BudgetOutcome.WITHIN, "auto"),
        (BudgetOutcome.SOFT_EXCEEDED, "ask"),
        (BudgetOutcome.HARD_EXCEEDED, "refuse"),
    ],
)
def test_outcome_tier_mapping(outcome, tier):
    from hermes_cli.budget_policy import OUTCOME_TIER

    assert OUTCOME_TIER[outcome] == tier


def test_negative_spent_raises():
    with pytest.raises(ValueError):
        evaluate_budget(-1.0, hard_limit=10.0)


def test_soft_greater_than_hard_raises():
    with pytest.raises(ValueError):
        evaluate_budget(5.0, soft_limit=20.0, hard_limit=10.0)


def test_negative_limit_raises():
    with pytest.raises(ValueError):
        evaluate_budget(5.0, hard_limit=-1.0)
