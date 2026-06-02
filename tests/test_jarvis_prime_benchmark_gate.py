"""Tests for hermes_cli.jarvis_prime.benchmark_gate."""

from __future__ import annotations

from hermes_cli.jarvis_prime.benchmark_gate import (
    BENCHMARK_GATE,
    benchmark_gate,
    evaluate_improvement,
)
from hermes_cli.jarvis_prime.gates import GateOutcome, run_gate_summary


def test_pass_when_candidate_beats_baseline():
    result = evaluate_improvement(0.40, 0.80, task="t")
    assert result.outcome == GateOutcome.PASS
    assert "beats baseline" in result.reason


def test_fail_on_regression():
    result = evaluate_improvement(0.80, 0.40, task="t")
    assert result.outcome == GateOutcome.FAIL
    assert "regression" in result.reason


def test_fail_when_no_real_improvement():
    # Equal scores are not an improvement.
    result = evaluate_improvement(0.50, 0.50, task="t")
    assert result.outcome == GateOutcome.FAIL


def test_fail_when_below_margin():
    result = evaluate_improvement(0.50, 0.53, task="t", min_margin=0.05)
    assert result.outcome == GateOutcome.FAIL
    result_ok = evaluate_improvement(0.50, 0.56, task="t", min_margin=0.05)
    assert result_ok.outcome == GateOutcome.PASS


def test_skipped_when_no_benchmark():
    assert benchmark_gate({}).outcome == GateOutcome.SKIPPED
    assert (
        benchmark_gate({
            "benchmark_task": "t",
            "baseline_score": 0.4,
            "candidate_score": None,
        }).outcome
        == GateOutcome.SKIPPED
    )


def test_skipped_when_not_run():
    packet = {
        "benchmark_task": "t",
        "benchmark_ran": False,
        "baseline_score": 0.4,
        "candidate_score": 0.9,
    }
    assert benchmark_gate(packet).outcome == GateOutcome.SKIPPED


def test_gate_is_named_and_composes_with_summary():
    assert BENCHMARK_GATE.name == "benchmark"
    # Composing with the standard gates must not raise; benchmark SKIPs
    # cleanly on a packet that has no benchmark fields.
    summary = run_gate_summary({"rollback_plan": "revert"}, gates=(BENCHMARK_GATE,))
    assert summary.results[0].outcome == GateOutcome.SKIPPED
    assert summary.overall in (GateOutcome.PASS, GateOutcome.SKIPPED)
