"""Benchmark validation gate for MUSE self-improvement.

Adds an objective, score-based gate to the verification system: a
candidate scaffold/skill/agent (e.g. one produced by the SIA worker) is
*promotable* only when it beats the baseline on a benchmark task by a
margin. The evaluator is duck-typed exactly like the eight gates in
:mod:`muse_cli.jarvis_prime.gates`, so it composes with
``run_gate_summary`` or runs standalone.

Outcomes:
- ``SKIPPED``  — no benchmark task / no numeric scores to compare.
- ``FAIL``     — regression, or improvement below the required margin.
- ``PASS``     — candidate beats baseline by at least ``min_margin``.

It never blocks on "no benchmark" (SKIPPED), so adding it to the gate
set can't break jobs that don't opt into benchmarking.
"""

from __future__ import annotations

from typing import Any, Mapping

from muse_cli.jarvis_prime.gates import Gate, GateOutcome, GateResult, _get

GATE_NAME = "benchmark"
DEFAULT_MIN_MARGIN = 0.0


def benchmark_gate(packet: Mapping[str, Any]) -> GateResult:
    """Score-based promotion gate. See module docstring for outcomes."""

    name = GATE_NAME
    task = _get(packet, "benchmark_task")
    ran = _get(packet, "benchmark_ran")
    baseline = _get(packet, "baseline_score")
    candidate = _get(packet, "candidate_score")
    margin = _get(packet, "min_margin")
    if margin is None:
        margin = DEFAULT_MIN_MARGIN

    if not task or ran is False or baseline is None or candidate is None:
        return GateResult(
            name=name,
            outcome=GateOutcome.SKIPPED,
            reason="no benchmark score to compare",
        )

    try:
        base = float(baseline)
        cand = float(candidate)
        marg = float(margin)
    except (TypeError, ValueError):
        return GateResult(
            name=name,
            outcome=GateOutcome.SKIPPED,
            reason="benchmark scores are not numeric",
        )

    delta = cand - base
    findings = (
        f"task={task}",
        f"baseline={base:.4f}",
        f"candidate={cand:.4f}",
        f"delta={delta:+.4f}",
    )

    if delta < 0:
        return GateResult(
            name=name,
            outcome=GateOutcome.FAIL,
            reason=f"regression: candidate {cand:.4f} < baseline {base:.4f}",
            findings=findings,
        )
    if delta == 0 or delta < marg:
        return GateResult(
            name=name,
            outcome=GateOutcome.FAIL,
            reason=(f"no real improvement (delta {delta:+.4f} < margin {marg:.4f})"),
            findings=findings,
        )
    return GateResult(
        name=name,
        outcome=GateOutcome.PASS,
        reason=f"candidate beats baseline by {delta:+.4f}",
        findings=findings,
    )


BENCHMARK_GATE = Gate(GATE_NAME, benchmark_gate)


def evaluate_improvement(
    baseline_score: float,
    candidate_score: float,
    *,
    task: str = "custom",
    min_margin: float = DEFAULT_MIN_MARGIN,
    benchmark_ran: bool = True,
) -> GateResult:
    """Convenience wrapper: build a packet and run :func:`benchmark_gate`."""
    return benchmark_gate({
        "benchmark_task": task,
        "benchmark_ran": benchmark_ran,
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "min_margin": min_margin,
    })


__all__ = [
    "GATE_NAME",
    "BENCHMARK_GATE",
    "benchmark_gate",
    "evaluate_improvement",
]
