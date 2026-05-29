from __future__ import annotations

from hermes_cli.jarvis_prime.memory_tree import (
    MemoryLayer,
    MemorySource,
    MemoryTreeStore,
    SourceTrust,
)
from hermes_cli.jarvis_prime.natural_language_coder import build_work_packet
from hermes_cli.jarvis_prime.research_vault import ResearchVault
from hermes_cli.jarvis_prime.tokenjuice import TokenJuiceCompiler


def test_compile_orders_mission_first_and_includes_packet() -> None:
    packet = build_work_packet("add durable memory tree support")
    ctx = TokenJuiceCompiler().compile(
        "add durable memory tree support", token_budget=2000, work_packet=packet
    )
    assert ctx.sections[0].kind == "mission"
    assert any(s.kind == "packet" for s in ctx.sections)


def test_compile_is_deterministic() -> None:
    packet = build_work_packet("add a helper")
    c = TokenJuiceCompiler()
    a = c.compile("mission text", 1000, work_packet=packet)
    b = c.compile("mission text", 1000, work_packet=packet)
    # output should be identical run-to-run (deterministic ordering)
    assert [s.title for s in a.sections] == [s.title for s in b.sections]


def test_budget_is_enforced_and_dropped_tracked(tmp_path) -> None:
    store = MemoryTreeStore(path=tmp_path / "m.jsonl")
    for i in range(10):
        store.write(
            f"backend fact number {i} with some descriptive text to consume tokens",
            namespace="jarvis/architecture",
            title=f"fact-{i}",
            layer=MemoryLayer.DURABLE,
            confidence=0.9,
            source_uri=f"doc{i}.md",
            source_trust=SourceTrust.PRIMARY,
        )
    ctx = TokenJuiceCompiler().compile(
        "backend", token_budget=40, memory_store=store, memory_query="backend"
    )
    assert ctx.used_tokens <= 40
    assert ctx.dropped  # some sections didn't fit


def test_sources_are_included(tmp_path) -> None:
    store = MemoryTreeStore(path=tmp_path / "m.jsonl")
    store.write(
        "Hermes is the canonical backend.",
        namespace="jarvis/architecture",
        title="backend",
        layer=MemoryLayer.DURABLE,
        confidence=0.95,
        sources=[MemorySource(uri="docs/spec.md", trust=SourceTrust.PRIMARY)],
    )
    ctx = TokenJuiceCompiler().compile(
        "backend", token_budget=2000, memory_store=store, memory_query="backend"
    )
    mem = [s for s in ctx.sections if s.kind == "memory"]
    assert mem and "docs/spec.md" in mem[0].sources


def test_research_artifacts_are_packed(tmp_path) -> None:
    vault = ResearchVault(path=tmp_path / "r.jsonl")
    art = vault.add(
        "vLLM doc", "https://docs.vllm.ai", excerpt="continuous batching note"
    )
    ctx = TokenJuiceCompiler().compile(
        "serving", token_budget=2000, research_artifacts=[art]
    )
    research = [s for s in ctx.sections if s.kind == "research"]
    assert research and "https://docs.vllm.ai" in research[0].sources


def test_secrets_are_screened_out() -> None:
    ctx = TokenJuiceCompiler().compile(
        "mission",
        token_budget=2000,
        repo_snippets=[("cfg.py", "api_key = sk-abcdefghijklmnop1234567890")],
    )
    repo = [s for s in ctx.sections if s.kind == "repo"]
    assert repo and "redacted" in repo[0].body
    assert "sk-abcdefghijklmnop" not in ctx.render()
