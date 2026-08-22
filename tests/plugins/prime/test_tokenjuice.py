"""prime tokenjuice — the deterministic, token-bounded context compiler."""

from __future__ import annotations

import pytest

from plugins.prime.memory_tree import MemoryLayer, MemoryTreeStore, estimate_tokens
from plugins.prime.research_vault import ResearchVault
from plugins.prime.tokenjuice import TokenJuiceCompiler


@pytest.fixture
def compiler():
    return TokenJuiceCompiler()


@pytest.fixture
def memory(tmp_path):
    store = MemoryTreeStore(path=tmp_path / "memory.jsonl")
    store.write(
        "The prime cache lives under HERMES_HOME and is safe to delete.",
        namespace="prime/test",
        title="cache location",
        layer=MemoryLayer.DURABLE,
        source_uri="docs/architecture.md",
        confidence=0.9,
        persist=False,
    )
    store.write(
        "Painting the shed is unrelated work.",
        namespace="prime/test",
        title="shed",
        persist=False,
    )
    return store


def test_mission_is_always_packed_first(compiler):
    ctx = compiler.compile("fix the cache path", 500)
    assert ctx.sections[0].kind == "mission"
    assert ctx.sections[0].body == "fix the cache path"
    assert ctx.used_tokens == estimate_tokens("fix the cache path")


def test_memory_is_packed_with_its_provenance(compiler, memory):
    ctx = compiler.compile("where is the cache", 500, memory_store=memory)
    mem = [s for s in ctx.sections if s.kind == "memory"]
    # The durable, cited fact outranks the loosely-matching session note, and
    # sections preserve that search order via their priority.
    assert mem[0].title == "prime/test: cache location"
    assert mem[0].priority > mem[-1].priority
    assert mem[0].sources == ("docs/architecture.md",)
    assert "HERMES_HOME" in mem[0].body
    # The session note has no provenance, so it carries none.
    assert next(s for s in mem if s.title.endswith("shed")).sources == ()
    assert "sources: docs/architecture.md" in ctx.render()


def test_memory_query_can_differ_from_the_mission(compiler, memory):
    ctx = compiler.compile(
        "unrelated mission text", 500, memory_store=memory, memory_query="shed"
    )
    assert [s.title for s in ctx.sections if s.kind == "memory"] == [
        "prime/test: shed"
    ]


def test_namespace_filter_is_passed_through(compiler, memory):
    ctx = compiler.compile(
        "cache", 500, memory_store=memory, memory_namespaces=["other/ns"]
    )
    assert [s for s in ctx.sections if s.kind == "memory"] == []


def test_contested_memory_is_excluded_by_default(compiler, tmp_path):
    store = MemoryTreeStore(path=tmp_path / "m.jsonl")
    for text in ("The cache is at A", "The cache is at B"):
        store.write(
            text,
            namespace="ns",
            title="cache location",
            layer=MemoryLayer.DURABLE,
            source_uri="docs/x.md",
            confidence=0.9,
            persist=False,
        )
    assert not [
        s
        for s in compiler.compile("cache", 500, memory_store=store).sections
        if s.kind == "memory"
    ]
    contested = compiler.compile(
        "cache", 500, memory_store=store, include_contested=True
    )
    assert len([s for s in contested.sections if s.kind == "memory"]) == 2


def test_research_artifacts_are_packed_with_their_uri(compiler, tmp_path):
    vault = ResearchVault(path=tmp_path / "v.jsonl")
    art = vault.add(
        "GraphRAG paper",
        "https://example.invalid/p",
        excerpt="Graphs improve retrieval.",
        persist=False,
    )
    ctx = compiler.compile("retrieval", 500, research_artifacts=[art])
    section = next(s for s in ctx.sections if s.kind == "research")
    assert section.title == "GraphRAG paper"
    assert section.body == "Graphs improve retrieval."
    assert section.sources == ("https://example.invalid/p",)


def test_repo_snippets_are_packed_last(compiler, memory):
    ctx = compiler.compile(
        "cache",
        500,
        memory_store=memory,
        repo_snippets=[("pkg/client.py", "def fetch(): ...")],
    )
    kinds = [s.kind for s in ctx.sections]
    assert kinds.index("repo") > kinds.index("memory") > kinds.index("mission")
    assert ctx.sections[-1].sources == ("pkg/client.py",)


def test_sections_are_dropped_whole_when_the_budget_runs_out(compiler, memory):
    ctx = compiler.compile("where is the cache", 12, memory_store=memory)
    assert ctx.used_tokens <= 12
    assert ctx.sections[0].kind == "mission"
    assert ctx.dropped
    # A dropped section is named, never half-included.
    assert all(s.body for s in ctx.sections)
    assert any(d.startswith("memory:") for d in ctx.dropped)


def test_budget_is_never_exceeded(compiler, memory):
    for budget in (0, 1, 5, 50, 500):
        ctx = compiler.compile("where is the cache", budget, memory_store=memory)
        assert ctx.used_tokens <= budget
        assert sum(s.tokens for s in ctx.sections) == ctx.used_tokens


def test_secret_like_snippets_are_redacted(compiler):
    ctx = compiler.compile(
        "deploy",
        500,
        repo_snippets=[("secrets.py", "api_key = supersecretvalue123")],
    )
    body = next(s for s in ctx.sections if s.kind == "repo").body
    assert body == "[redacted: secret-like content removed by TokenJuice]"
    assert "supersecretvalue123" not in ctx.render()


def test_compilation_is_deterministic(compiler, memory):
    a = compiler.compile("where is the cache", 500, memory_store=memory)
    b = compiler.compile("where is the cache", 500, memory_store=memory)
    assert a.to_dict() == b.to_dict()


def test_render_reports_the_budget_and_drops(compiler, memory):
    ctx = compiler.compile("where is the cache", 12, memory_store=memory)
    header = ctx.render().splitlines()[1]
    assert f"budget: {ctx.used_tokens}/12 tokens" in header
    assert f"{len(ctx.dropped)} dropped" in header


def test_to_dict_shape(compiler):
    d = compiler.compile("mission", 100).to_dict()
    assert set(d) == {
        "mission",
        "token_budget",
        "used_tokens",
        "dropped",
        "sections",
    }
    assert set(d["sections"][0]) == {
        "kind",
        "title",
        "body",
        "sources",
        "tokens",
        "priority",
    }
