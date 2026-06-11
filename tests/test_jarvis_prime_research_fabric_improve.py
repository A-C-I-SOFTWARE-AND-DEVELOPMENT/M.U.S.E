"""Tests for the top-level improvement orchestration (ties the planes together)."""

from __future__ import annotations

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from hermes_cli.jarvis_prime.research_fabric.archive.store import ArchiveStore
from hermes_cli.jarvis_prime.research_fabric.improve import (
    run_algorithms_improvement,
    run_swe_improvement,
)
from hermes_cli.jarvis_prime.research_fabric.selfplay.swe_tasks import (
    demo_swe_baseline,
    make_demo_swe_repo,
)


def test_reference_improvement_runs_and_improves(tmp_path) -> None:
    ledger = GuardrailLedger(tmp_path / "l.jsonl")
    archive = ArchiveStore(path=tmp_path / "a.jsonl")
    run = run_algorithms_improvement(ledger=ledger, archive=archive)
    assert run.used_llm is False
    assert run.result.improved is True
    assert run.result.reduction > 0  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture
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


def test_swe_reference_improvement_fixes_repo(tmp_path) -> None:
    task = make_demo_swe_repo(tmp_path / "repo")
    ledger = GuardrailLedger(tmp_path / "l.jsonl")
    run = run_swe_improvement(task, demo_swe_baseline(), ledger=ledger)
    assert run.baseline_failed is True
    assert run.accepted is True
    assert run.used_llm is False
    assert "swe_improve" in [r.kind for r in ledger.read_all()]


def test_swe_llm_improvement(tmp_path) -> None:
    task = make_demo_swe_repo(tmp_path / "repo")
    provider = lambda _p: "```python\ndef f(x):\n    return x * x\n```"
    run = run_swe_improvement(task, demo_swe_baseline(), provider=provider)
    assert run.used_llm is True
    assert run.accepted is True


def test_swe_wrong_llm_patch_rejected(tmp_path) -> None:
    task = make_demo_swe_repo(tmp_path / "repo")
    provider = lambda _p: "```python\ndef f(x):\n    return x + 1\n```"
    run = run_swe_improvement(task, demo_swe_baseline(), provider=provider)
    assert run.accepted is False
