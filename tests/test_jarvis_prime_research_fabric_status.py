"""Tests for the fabric status view + the research-fabric slash command."""

from __future__ import annotations

from muse_cli.commands import resolve_command
from muse_cli.jarvis_prime.research_fabric.archive.store import ArchiveStore
from muse_cli.jarvis_prime.research_fabric.pipeline import open_context
from muse_cli.jarvis_prime.research_fabric.status import fabric_status


def test_status_empty_fabric(tmp_path) -> None:
    ctx = open_context(tmp_path)
    try:
        st = fabric_status(ctx, ArchiveStore(path=tmp_path / "a.jsonl"))
    finally:
        ctx.close()
    assert st["autonomy_active"] is False
    assert st["champion"] is None
    assert st["archive_members"] == 0
    assert st["ledger_chain_ok"] is True
    assert st["store_chain_ok"] is True


def test_status_reflects_activity(tmp_path) -> None:
    archive = ArchiveStore(path=tmp_path / "a.jsonl")
    ctx = open_context(tmp_path)
    try:
        from muse_cli.jarvis_prime.research_fabric.improve import (
            run_algorithms_improvement,
        )

        run_algorithms_improvement(ledger=ctx.ledger, archive=archive)
        st = fabric_status(ctx, archive)
    finally:
        ctx.close()
    assert "evolve_accept" in st["ledger_events"]
    assert st["archive_members"] >= 2
    assert st["ledger_length"] >= 1


def test_research_fabric_slash_command_registered() -> None:
    entry = resolve_command("research-fabric")
    assert entry is not None
    assert entry.name == "research-fabric"
    assert "rf" in entry.aliases
    assert entry.category == "Tools & Skills"
    # Alias resolves to the same canonical command.
    assert resolve_command("/rf").name == "research-fabric"  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    # Key subcommands are advertised for completion.
    assert {"charter", "improve", "benchmarks", "status"} <= set(entry.subcommands)
