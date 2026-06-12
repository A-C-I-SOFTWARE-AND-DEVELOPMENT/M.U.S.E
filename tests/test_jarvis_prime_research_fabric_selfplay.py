"""Tests for the ReST-EM self-play loop (runnable, verifier-gated)."""

from __future__ import annotations

from muse_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from muse_cli.jarvis_prime.research_fabric.selfplay.loop import run_selfplay
from muse_cli.jarvis_prime.research_fabric.selfplay.tasks import (
    SEED_TASKS,
    reference_solver,
)
from muse_cli.jarvis_prime.research_fabric.verifier.algorithms import AlgorithmTask


def test_reference_solver_passes_all_seed_tasks(tmp_path) -> None:
    ledger = GuardrailLedger(tmp_path / "l.jsonl")
    result = run_selfplay(SEED_TASKS, reference_solver, ledger=ledger)
    assert result.attempted == len(SEED_TASKS)
    assert len(result.accepted) == len(SEED_TASKS)
    assert result.acceptance_rate == 1.0
    # Accepted traces are recorded to the hash-chained ledger.
    kinds = [r.kind for r in ledger.read_all()]
    assert kinds.count("selfplay_accept") == len(SEED_TASKS)
    assert ledger.verify_chain().ok is True


def test_bad_solver_is_rejected_by_verifier() -> None:
    def bad_solver(task: AlgorithmTask) -> str:
        return "def solve(*a):\n    return 'wrong'\n"

    result = run_selfplay(SEED_TASKS, bad_solver)
    assert len(result.accepted) == 0
    assert result.acceptance_rate == 0.0


def test_solver_exception_counts_as_rejection() -> None:
    def crashing_solver(task: AlgorithmTask) -> str:
        raise RuntimeError("solver blew up")

    result = run_selfplay(SEED_TASKS, crashing_solver)
    assert len(result.accepted) == 0
    assert len(result.rejected) == len(SEED_TASKS)


def test_learnability_filter_skips_trivial_or_impossible() -> None:
    # Estimator says every task is trivially easy (0.99) -> filtered out.
    result = run_selfplay(
        SEED_TASKS,
        reference_solver,
        difficulty_estimator=lambda _t: 0.99,
    )
    assert result.skipped_unlearnable == len(SEED_TASKS)
    assert result.attempted == 0
