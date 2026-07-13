"""Tests for clean-room JARVIS Memory Tree primitives."""

from __future__ import annotations

from pathlib import Path

from hermes_cli.jarvis_prime.memory_tree import MemoryTreeStore, estimate_tokens


def test_memory_tree_ingests_bounded_chunk_and_builds_outline(tmp_path: Path) -> None:
    store = MemoryTreeStore(journal_path=tmp_path / "tree.jsonl")
    chunk = store.ingest_text(
        "JARVIS should localize code before editing and use Codex as reviewer.",
        namespace="jarvis/coding",
        title="Coding discipline",
        source_uri="owner-note",
        tags=("coding",),
    )
    assert chunk is not None
    assert chunk.token_estimate > 0
    outline = store.outline("jarvis/coding")
    assert "jarvis/coding" in outline
    assert "coding" in outline.lower()


def test_memory_tree_rejects_secret_like_text(tmp_path: Path) -> None:
    store = MemoryTreeStore(journal_path=tmp_path / "tree.jsonl")
    chunk = store.ingest_text(
        "api_key = sk-test-redacted",
        namespace="jarvis/security",
        title="bad",
    )
    assert chunk is None
    assert store.chunks == {}


def test_memory_tree_search_and_context_pack(tmp_path: Path) -> None:
    store = MemoryTreeStore(journal_path=tmp_path / "tree.jsonl")
    store.ingest_text(
        "The living avatar must separate animation from real AccessibilityService taps.",
        namespace="jarvis/avatar",
        title="Avatar safety",
        source_uri="research",
        trust_tier="official",
        confidence=0.9,
        tags=("avatar",),
    )
    hits = store.search("avatar accessibility taps")
    assert hits
    pack = store.context_pack("avatar taps", token_budget=120)
    assert "AccessibilityService" in pack
    assert estimate_tokens(pack) <= 160


def test_memory_tree_persists_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "tree.jsonl"
    s1 = MemoryTreeStore(journal_path=path)
    s1.ingest_text("Persistent local memory tree.", namespace="jarvis/memory", title="Memory")
    s2 = MemoryTreeStore(journal_path=path)
    assert s2.chunks
    assert s2.nodes
