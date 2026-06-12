"""Tests for the evolutionary improvement loop (real execution + op-count)."""

from __future__ import annotations

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from hermes_cli.jarvis_prime.research_fabric.selfplay.evolve import evolve
from hermes_cli.jarvis_prime.research_fabric.selfplay.tasks import (
    DEMO_BASELINE_CODE,
    DEMO_EVOLVE_TASK,
    demo_variant_proposer,
)
from hermes_cli.jarvis_prime.research_fabric.verifier.algorithms import measure_opcount


def test_opcount_is_deterministic_and_lower_for_builtin() -> None:
    naive = measure_opcount(DEMO_BASELINE_CODE, DEMO_EVOLVE_TASK)
    builtin = measure_opcount("def solve(xs):\n    return sum(xs)\n", DEMO_EVOLVE_TASK)
    assert naive is not None and builtin is not None
    assert builtin < naive
    # Deterministic across runs.
    assert measure_opcount(DEMO_BASELINE_CODE, DEMO_EVOLVE_TASK) == naive


def test_evolve_discovers_lower_opcount(tmp_path) -> None:
    ledger = GuardrailLedger(tmp_path / "l.jsonl")
    result = evolve(
        DEMO_EVOLVE_TASK, DEMO_BASELINE_CODE, demo_variant_proposer, ledger=ledger
    )
    assert result.improved is True
    assert result.best_opcount < result.baseline_opcount  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture
    assert result.reduction > 0  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture
    assert "evolve_accept" in [r.kind for r in ledger.read_all()]
    assert ledger.verify_chain().ok is True


def test_evolve_is_monotone_never_worse() -> None:
    result = evolve(DEMO_EVOLVE_TASK, DEMO_BASELINE_CODE, demo_variant_proposer)
    # The evolved best can never be worse than the baseline.
    assert result.best_opcount <= result.baseline_opcount  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture


def test_incorrect_baseline_yields_no_evolution() -> None:
    result = evolve(
        DEMO_EVOLVE_TASK, "def solve(xs):\n    return 999\n", demo_variant_proposer
    )
    assert result.improved is False
    assert result.baseline_opcount is None


def test_incorrect_variants_are_rejected() -> None:
    def bad_proposer(_best: str) -> list[str]:
        return ["def solve(xs):\n    return -1\n"]

    result = evolve(DEMO_EVOLVE_TASK, DEMO_BASELINE_CODE, bad_proposer)
    assert result.improved is False
    # Best stays the (correct) baseline.
    assert result.best_code == DEMO_BASELINE_CODE


def test_correct_but_not_better_variant_not_accepted() -> None:
    # Propose the exact same baseline — correct, but no op-count reduction.
    result = evolve(DEMO_EVOLVE_TASK, DEMO_BASELINE_CODE, lambda b: [b])
    assert result.improved is False
    assert result.best_opcount == result.baseline_opcount
