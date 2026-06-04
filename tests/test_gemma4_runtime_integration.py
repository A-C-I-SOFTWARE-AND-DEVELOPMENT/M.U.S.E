"""Gemma 4 — runtime integration tests (observe_turn curator + scorecards)."""

from __future__ import annotations

from pathlib import Path

from hermes_cli.jarvis_prime.memory import MemoryStore
from hermes_cli.jarvis_prime.memory_tree import ApprovalState, MemoryLayer, MemoryTreeStore
from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook
from hermes_cli.jarvis_prime.runtime import JarvisConfig, JarvisPrime


def _config(tmp_path: Path, **extra) -> JarvisConfig:
    return JarvisConfig(
        memory=MemoryStore(journal_path=tmp_path / "memory.jsonl"),
        memory_tree=MemoryTreeStore(path=tmp_path / "tree.jsonl"),
        **extra,
    )


def test_observe_turn_unchanged_without_runner(tmp_path: Path) -> None:
    jp = JarvisPrime(config=_config(tmp_path))
    summary = jp.observe_turn("just chatting about the weather", "ok")
    # Default behavior: no gemma keys added when no runner is configured.
    assert "gemma_proposed" not in summary
    assert set(summary) == {"captured", "rejected", "durable_worthy"}


def test_observe_turn_runs_gemma_curator_proposed_only(tmp_path: Path) -> None:
    def fake_runner(_prompt: str) -> str:
        return (
            "<think>scratch</think>"
            '[{"title": "Pref", "summary": "User prefers concise replies", '
            '"namespace": "jarvis/personal", "confidence": 0.95}]'
        )

    jp = JarvisPrime(config=_config(tmp_path, gemma_runner=fake_runner))
    # Neutral text so deterministic capture yields nothing — isolate the curator.
    summary = jp.observe_turn("hello there", "hi")
    assert summary.get("gemma_proposed", 0) >= 1
    tree = jp.memory_tree()
    proposed = tree.proposed()
    assert proposed
    assert all(n.layer is MemoryLayer.SESSION for n in proposed)
    assert all(n.approval_state is ApprovalState.PROPOSED for n in proposed)


def test_curator_can_be_disabled(tmp_path: Path) -> None:
    def fake_runner(_prompt: str) -> str:
        return '[{"title": "x", "summary": "y", "namespace": "jarvis/general"}]'

    jp = JarvisPrime(
        config=_config(tmp_path, gemma_runner=fake_runner, gemma_memory_curator_enabled=False)
    )
    summary = jp.observe_turn("hello", "hi")
    assert "gemma_proposed" not in summary


def test_record_route_outcome_requires_evidence(tmp_path: Path) -> None:
    jp = JarvisPrime(config=_config(tmp_path))
    book = ScorecardBook(path=tmp_path / "sc.jsonl")
    # No signals → nothing fabricated.
    assert jp.record_route_outcome(
        model="gemma4-e4b", task_class="memory_curator", book=book, persist=False
    ) is None
    # With real evidence → a scorecard is recorded.
    card = jp.record_route_outcome(
        model="gemma4-e4b",
        task_class="memory_curator",
        latency_ms=800.0,
        memory_usefulness=0.9,
        book=book,
        persist=False,
    )
    assert card is not None
    assert book.scorecards and book.scorecards[-1].model == "gemma4-e4b"


def test_turn_to_dict_carries_route_metadata_keys(tmp_path: Path) -> None:
    jp = JarvisPrime(config=_config(tmp_path))
    turn = jp.handle("audit the repo", skip_perceive=True)
    d = turn.to_dict()
    for key in (
        "selected_model", "selected_provider", "selected_task_class",
        "fallback_chain", "scorecard_basis", "gemma_variant",
    ):
        assert key in d
