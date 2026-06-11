"""Tests for per-job cost / token aggregation (Sprint 10)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hermes_cli.budget_policy import BudgetOutcome
from hermes_cli.job_cost import JobCost


class _Usage:
    """Minimal CanonicalUsage-like stand-in for add_usage()."""

    def __init__(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        reasoning_tokens: int = 0,
    ) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_tokens = cache_read_tokens
        self.cache_write_tokens = cache_write_tokens
        self.reasoning_tokens = reasoning_tokens


def test_fresh_accumulator_is_zero():
    jc = JobCost()
    assert jc.cost_usd == 0.0
    assert jc.total_tokens == 0
    assert jc.call_count == 0
    assert jc.totals()["by_model"] == {}


def test_add_usage_sums_cost_and_tokens():
    jc = JobCost()
    jc.add_usage(_Usage(input_tokens=100, output_tokens=50), cost_usd=0.01)
    jc.add_usage(_Usage(input_tokens=20, output_tokens=5), cost_usd=0.002)
    assert jc.input_tokens == 120
    assert jc.output_tokens == 55
    assert jc.call_count == 2
    assert jc.cost_usd == pytest.approx(0.012)


def test_add_usage_accepts_decimal_cost():
    # CostResult.amount_usd is a Decimal — must be accepted and normalized.
    jc = JobCost()
    jc.add_usage(_Usage(input_tokens=10), cost_usd=Decimal("0.0123"))
    assert jc.cost_usd == pytest.approx(0.0123)


def test_add_usage_accepts_numeric_string_cost():
    jc = JobCost()
    jc.add_usage(None, cost_usd="0.25")
    assert jc.cost_usd == pytest.approx(0.25)


def test_cost_only_entry_skips_token_counters():
    jc = JobCost()
    jc.add_usage(None, cost_usd=0.5)
    assert jc.cost_usd == pytest.approx(0.5)
    assert jc.total_tokens == 0
    assert jc.call_count == 1


def test_none_cost_is_treated_as_zero():
    # An unpriced / "included" call records tokens without moving the meter.
    jc = JobCost()
    jc.add_usage(_Usage(input_tokens=10, output_tokens=5), cost_usd=None)
    assert jc.cost_usd == 0.0
    assert jc.total_tokens == 15
    assert jc.call_count == 1


def test_prompt_and_total_tokens_mirror_canonical_usage():
    jc = JobCost()
    jc.add_usage(
        _Usage(
            input_tokens=100,
            output_tokens=40,
            cache_read_tokens=10,
            cache_write_tokens=5,
        )
    )
    # prompt = input + cache_read + cache_write; total = prompt + output
    assert jc.prompt_tokens == 115
    assert jc.total_tokens == 155


def test_by_model_breakdown_accumulates_per_route():
    jc = JobCost()
    jc.add_usage(_Usage(), cost_usd=0.01, provider="anthropic", model="claude-opus-4-7")
    jc.add_usage(_Usage(), cost_usd=0.02, provider="anthropic", model="claude-opus-4-7")
    jc.add_usage(_Usage(), cost_usd=0.05, provider="openai", model="gpt-4o")
    totals = jc.totals()
    assert totals["by_model"] == {
        "anthropic/claude-opus-4-7": 0.03,
        "openai/gpt-4o": 0.05,
    }


def test_by_model_key_falls_back_to_model_or_provider_only():
    jc = JobCost()
    jc.add_usage(_Usage(), cost_usd=0.01, model="claude-opus-4-7")
    jc.add_usage(_Usage(), cost_usd=0.02, provider="anthropic")
    keys = set(jc.totals()["by_model"])
    assert keys == {"claude-opus-4-7", "anthropic"}


def test_no_model_means_no_breakdown_entry():
    jc = JobCost()
    jc.add_usage(_Usage(), cost_usd=0.01)
    assert jc.totals()["by_model"] == {}


def test_add_usage_returns_self_for_chaining():
    jc = JobCost()
    out = jc.add_usage(_Usage(input_tokens=1), cost_usd=0.001)
    assert out is jc


def test_negative_cost_raises():
    jc = JobCost()
    with pytest.raises(ValueError):
        jc.add_usage(None, cost_usd=-1.0)


def test_bool_cost_rejected():
    # bool is an int subclass; a stray True must not be summed as 1.0.
    jc = JobCost()
    with pytest.raises(TypeError):
        jc.add_usage(None, cost_usd=True)


def test_non_numeric_string_cost_raises():
    jc = JobCost()
    with pytest.raises(ValueError):
        jc.add_usage(None, cost_usd="not-a-number")


def test_garbage_token_value_coerces_to_zero():
    # A worker payload with a junk token field must not crash aggregation.
    jc = JobCost()
    jc.add_usage(_Usage(input_tokens="bad"), cost_usd=0.0)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture
    assert jc.input_tokens == 0


# ---------------------------------------------------------------------------
# budget_decision — bridges the accumulated cost into the budget kernel
# ---------------------------------------------------------------------------


def test_budget_decision_no_limits_is_within():
    jc = JobCost()
    jc.add_usage(None, cost_usd=1_000.0)
    d = jc.budget_decision()
    assert d.outcome is BudgetOutcome.WITHIN
    assert d.tier == "auto"
    assert not d.should_stop
    assert not d.needs_approval


def test_budget_decision_soft_exceeded_asks():
    jc = JobCost()
    jc.add_usage(None, cost_usd=0.08)
    d = jc.budget_decision(soft_limit=0.05, hard_limit=0.10)
    assert d.outcome is BudgetOutcome.SOFT_EXCEEDED
    assert d.needs_approval
    assert not d.should_stop


def test_budget_decision_hard_exceeded_stops():
    jc = JobCost()
    jc.add_usage(None, cost_usd=0.10)
    d = jc.budget_decision(soft_limit=0.05, hard_limit=0.10)
    assert d.outcome is BudgetOutcome.HARD_EXCEEDED
    assert d.should_stop


def test_budget_decision_spent_tracks_accumulated_cost():
    jc = JobCost()
    jc.add_usage(_Usage(input_tokens=1), cost_usd=Decimal("0.0123"))
    jc.add_usage(_Usage(input_tokens=1), cost_usd=Decimal("0.0077"))
    d = jc.budget_decision(hard_limit=1.0)
    assert d.spent == pytest.approx(0.02)


def test_budget_decision_custom_meter_label():
    jc = JobCost()
    jc.add_usage(None, cost_usd=2.0)
    d = jc.budget_decision(hard_limit=1.0, meter="usd")
    assert d.meter == "usd"
    assert "usd=" in d.detail


def test_to_dict_is_totals_alias():
    jc = JobCost()
    jc.add_usage(_Usage(input_tokens=5), cost_usd=0.01)
    assert jc.to_dict() == jc.totals()
