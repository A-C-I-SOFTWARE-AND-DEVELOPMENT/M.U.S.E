from __future__ import annotations

from muse_cli.jarvis_prime import evidence_engine as ee
from muse_cli.jarvis_prime.memory_tree import MemoryLayer, MemoryTreeStore, SourceTrust
from muse_cli.jarvis_prime.research_vault import (
    EvidenceStrength,
    ResearchVault,
    SourceType,
)


def _vault(tmp_path) -> ResearchVault:
    vault = ResearchVault(path=tmp_path / "rvault.jsonl")
    vault.add(
        "vLLM continuous batching",
        "https://docs.vllm.ai/serving",
        source_type=SourceType.OFFICIAL_DOC,
        evidence_strength=EvidenceStrength.PRIMARY,
        excerpt="vLLM uses continuous batching to improve serving throughput.",
        citation_anchors=("serving.md:12",),
    )
    vault.add(
        "Community blog on batching",
        "https://blog.example/batching",
        source_type=SourceType.BLOG,
        evidence_strength=EvidenceStrength.WEAK,
        excerpt="A blog claims continuous batching helps throughput a lot.",
    )
    return vault


def test_retrieve_ranks_primary_above_community(tmp_path) -> None:
    vault = _vault(tmp_path)
    hits = ee.retrieve("continuous batching throughput", vault=vault)
    assert hits, "expected retrieval hits"
    # Primary/official doc trust must outrank the weak community blog.
    assert hits[0].trust is SourceTrust.PRIMARY
    assert hits[0].citation_anchors == ("serving.md:12",)


def test_bm25_zero_for_no_overlap(tmp_path) -> None:
    vault = _vault(tmp_path)
    assert ee.retrieve("kubernetes ingress", vault=vault) == []


def test_repo_symbol_search(tmp_path) -> None:
    (tmp_path / "mod.py").write_text("def widget_factory():\n    return 1\n", encoding="utf-8")
    hits = ee.repo_symbol_hits("widget factory", tmp_path)
    assert hits and hits[0].kind == "repo"
    assert hits[0].citation_anchors and ":" in hits[0].citation_anchors[0]


def test_verifier_flags_uncited_claim(tmp_path) -> None:
    vault = _vault(tmp_path)
    hits = ee.retrieve("continuous batching", vault=vault)
    verifier = ee.CitationVerifier()
    result = verifier.verify(
        ["vLLM uses continuous batching", "Postgres supports logical replication"],
        hits,
    )
    supported = [c for c in result.citations if c.supported]
    assert any("batching" in c.claim for c in supported)
    assert "Postgres supports logical replication" in result.uncertain


def test_verifier_rejects_secret_and_cot() -> None:
    verifier = ee.CitationVerifier()
    result = verifier.verify(
        [
            "api_key=sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
            "Let me think step by step about the answer",
        ],
        [],
    )
    assert len(result.rejected) == 2
    assert not result.citations


def test_detect_contradiction_between_hits() -> None:
    hits = [
        ee.EvidenceHit("vault", "Feature flag default", "u1", "the flag is enabled by default", SourceTrust.REPUTABLE, 1.0),
        ee.EvidenceHit("vault", "Feature flag default", "u2", "the flag is not enabled by default", SourceTrust.REPUTABLE, 1.0),
    ]
    contradictions = ee.detect_contradictions(hits)
    assert contradictions and contradictions[0].subject


def test_promote_low_confidence_rejected(tmp_path) -> None:
    vault = _vault(tmp_path)
    store = MemoryTreeStore(path=tmp_path / "mt.jsonl")
    weak = vault.add(
        "Unverified rumor",
        "https://forum.example/post",
        evidence_strength=EvidenceStrength.WEAK,
        excerpt="Someone on a forum says X.",
    )
    res = ee.promote_to_memory(weak, store, persist=False)
    # Weak trust → low confidence → durable write needs owner approval.
    assert not res.ok
    assert any("confidence" in r for r in res.reasons)


def test_promote_owner_approved_succeeds(tmp_path) -> None:
    vault = _vault(tmp_path)
    store = MemoryTreeStore(path=tmp_path / "mt.jsonl")
    art = vault.add(
        "Official spec detail",
        "https://spec.example/v1",
        source_type=SourceType.OFFICIAL_DOC,
        evidence_strength=EvidenceStrength.PRIMARY,
        excerpt="The spec mandates UTC timestamps.",
    )
    res = ee.promote_to_memory(art, store, owner_approved=True, persist=False)
    assert res.ok and res.node is not None
    assert res.node.layer is MemoryLayer.DURABLE


def test_promote_rejects_secret(tmp_path) -> None:
    vault = _vault(tmp_path)
    store = MemoryTreeStore(path=tmp_path / "mt.jsonl")
    bad = vault.add(
        "Leaked key",
        "https://paste.example",
        evidence_strength=EvidenceStrength.PRIMARY,
        excerpt="api_key=sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    )
    res = ee.promote_to_memory(bad, store, owner_approved=True, persist=False)
    assert not res.ok
