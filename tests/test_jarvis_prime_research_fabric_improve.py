"""Tests for the top-level improvement orchestration (ties the planes together)."""

from __future__ import annotations

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from hermes_cli.jarvis_prime.research_fabric.archive.store import ArchiveStore
from hermes_cli.jarvis_prime.research_fabric.improve import run_algorithms_improvement


def test_reference_improvement_runs_and_improves(tmp_path) -> None:
    ledger = GuardrailLedger(tmp_path / "l.jsonl")
    archive = ArchiveStore(path=tmp_path / "a.jsonl")
    run = run_algorithms_improvement(ledger=ledger, archive=archive)
    assert run.used_llm is False
    assert run.result.improved is True
    assert run.result.reduction > 0
    # Lineage recorded.
    assert len(archive.members()) >= 2
    assert ledger.verify_chain().ok is True


def test_llm_driven_improvement(tmp_path) -> None:
    # A fake provider that returns the optimized rewrite drives the same loop.
    provider = lambda _p: "```python\ndef solve(xs):\n    return sum(xs)\n```"
    run = run_algorithms_improvement(
        provider=provider, archive=ArchiveStore(path=tmp_path / "a.jsonl")
    )
    assert run.used_llm is True
    assert run.result.improved is True


def test_llm_with_wrong_output_does_not_improve(tmp_path) -> None:
    # The verifier blocks an incorrect "improvement" even from the model.
    provider = lambda _p: "```python\ndef solve(xs):\n    return 0\n```"
    run = run_algorithms_improvement(
        provider=provider, archive=ArchiveStore(path=tmp_path / "a.jsonl")
    )
    assert run.used_llm is True
    assert run.result.improved is False
