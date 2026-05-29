from __future__ import annotations

from hermes_cli.jarvis_prime.memory_tree import MemoryTree


def test_memory_tree_adds_and_searches_source_backed_chunks() -> None:
    tree = MemoryTree()
    chunk = tree.add(
        "JARVIS uses Hermes as the canonical operating backend.",
        namespace="jarvis/architecture",
        title="Hermes backend decision",
        source_uri="docs/jarvis-prime-operating-system.md",
        confidence=0.9,
        tags=("architecture",),
    )

    assert chunk is not None
    hits = tree.search("canonical Hermes backend")
    assert hits == [chunk]
    assert hits[0].source_uri == "docs/jarvis-prime-operating-system.md"


def test_memory_tree_outline_groups_by_namespace() -> None:
    tree = MemoryTree()
    tree.add("Owner gates stay active.", namespace="jarvis/safety", title="Owner gates")
    tree.add("Research vault stores evidence.", namespace="jarvis/research", title="Research vault")

    outline = tree.outline()

    assert "jarvis/research" in outline
    assert "jarvis/safety" in outline
    assert "Owner gates" in outline


def test_memory_tree_ignores_empty_text() -> None:
    tree = MemoryTree()
    assert tree.add("   ", namespace="jarvis", title="empty") is None
