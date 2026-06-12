from __future__ import annotations

from muse_cli.jarvis_prime.research_vault import (
    EvidenceStrength,
    ResearchVault,
    SourceType,
)
from muse_cli.jarvis_prime.memory_tree import SourceTrust


def _vault(tmp_path):
    return ResearchVault(path=tmp_path / "rvault.jsonl")


def test_add_summarizes_from_excerpt_only(tmp_path) -> None:
    vault = _vault(tmp_path)
    art = vault.add(
        "vLLM continuous batching",
        "https://docs.vllm.ai/serving",
        source_type=SourceType.OFFICIAL_DOC,
        evidence_strength=EvidenceStrength.PRIMARY,
        excerpt="vLLM uses continuous batching to improve throughput.",
    )
    assert art.summary.startswith("vLLM uses continuous batching")
    assert art.source_type is SourceType.OFFICIAL_DOC


def test_vendor_benchmark_is_recorded_as_unverified(tmp_path) -> None:
    vault = _vault(tmp_path)
    art = vault.add(
        "Qwen3 coder benchmark",
        "https://vendor.example/bench",
        source_type=SourceType.BENCHMARK,
        evidence_strength=EvidenceStrength.VENDOR_REPORTED,
        excerpt="Scores 90 on a vendor benchmark.",
    )
    assert art.evidence_strength is EvidenceStrength.VENDOR_REPORTED
    assert art.as_memory_source().trust is SourceTrust.UNVERIFIED


def test_memory_source_bridge_carries_provenance(tmp_path) -> None:
    vault = _vault(tmp_path)
    art = vault.add(
        "Anthropic skills doc",
        "https://docs.anthropic.com/skills",
        source_type=SourceType.OFFICIAL_DOC,
        evidence_strength=EvidenceStrength.PRIMARY,
        excerpt="Skills are markdown playbooks.",
    )
    src = art.as_memory_source()
    assert src.uri == "https://docs.anthropic.com/skills"
    assert src.trust is SourceTrust.PRIMARY
    assert "Skills are markdown" in src.excerpt


def test_search_and_audit_cards(tmp_path) -> None:
    vault = _vault(tmp_path)
    vault.add("DeepSeek serving", "u1", excerpt="deepseek model serving notes")
    vault.add("OWASP LLM top 10", "u2", excerpt="prompt injection is the top risk")
    hits = vault.search("prompt injection")
    assert hits and hits[0].title == "OWASP LLM top 10"
    cards = vault.export_audit_cards()
    assert len(cards) == 2


def test_persistence_round_trip(tmp_path) -> None:
    path = tmp_path / "rvault.jsonl"
    vault = ResearchVault(path=path)
    vault.add("a", "u1", excerpt="alpha")
    vault.add("b", "u2", excerpt="beta")
    reloaded = ResearchVault.load(path)
    assert len(reloaded.artifacts) == 2


def test_malformed_lines_tolerated(tmp_path) -> None:
    path = tmp_path / "rvault.jsonl"
    vault = ResearchVault(path=path)
    vault.add("a", "u1", excerpt="alpha")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("garbage\n")
    reloaded = ResearchVault.load(path)
    assert len(reloaded.artifacts) == 1
    assert reloaded.load_diagnostics


def test_export_markdown(tmp_path) -> None:
    vault = _vault(tmp_path)
    vault.add("a", "u1", excerpt="alpha note")
    md = vault.export_markdown()
    assert "# JARVIS Research Vault" in md
    assert "alpha note" in md
