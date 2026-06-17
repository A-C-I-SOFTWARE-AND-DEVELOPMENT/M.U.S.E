"""The in-memory Second Brain backend makes ingest→retrieve run with no infra.

These are the "make it real" tests: the full SecondBrain ingest→retrieve path
runs end-to-end against the zero-infrastructure in-memory backend (no Postgres,
no Neo4j, no drivers), and the default backend stays ``postgres`` (unchanged).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from second_brain.knowledge import SecondBrain, load_settings
from second_brain.knowledge.config import EmbeddingConfig, Settings
from second_brain.knowledge.memory_store import (
    InMemoryDocumentStore,
    InMemoryProvenanceTracker,
    InMemoryVectorStore,
)
from second_brain.knowledge.models import (
    Document,
    MemoryNode,
    ProvenanceRecord,
    utcnow,
)


def _memory_settings(dim: int = 64) -> Settings:
    base = load_settings()
    return replace(
        base, backend="memory", embedding=replace(base.embedding, dimension=dim)
    )


# --- default unchanged ------------------------------------------------------


def test_default_backend_is_postgres():
    # The module's standalone default must stay postgres (existing behavior).
    assert load_settings().backend == "postgres"
    assert Settings().backend == "postgres"


# --- end-to-end ingest -> retrieve (no database) ----------------------------


def test_ingest_then_retrieve_returns_the_fact():
    brain = SecondBrain(_memory_settings(), enable_graph=False)
    try:
        assert brain.postgres is None  # no Postgres client constructed
        brain.ingest_text(
            "Ada Lovelace collaborated with Charles Babbage on the Analytical "
            "Engine. She is regarded as the first computer programmer.",
            source_id="hist/ada",
            metadata={"trust": 0.9},
        )
        payload = brain.retrieve("Who worked with Charles Babbage?")
        assert len(payload.blocks) >= 1
        prompt = payload.to_prompt()
        assert "Charles Babbage" in prompt
        assert "hist/ada" in prompt  # source-cited
    finally:
        brain.close()  # no-op for memory, must not raise


def test_retrieve_on_empty_brain_is_empty_not_error():
    brain = SecondBrain(_memory_settings(), enable_graph=False)
    try:
        payload = brain.retrieve("anything")
        assert list(payload.blocks) == []
    finally:
        brain.close()


# --- in-memory vector store units ------------------------------------------


def _node(content: str, vec, *, confidence: float = 0.8, ttl=None) -> MemoryNode:
    return MemoryNode(
        content=content,
        embedding=[float(x) for x in vec],
        source_id="t",
        confidence_score=confidence,
        ttl_expires_at=ttl,
    )


def test_similarity_search_orders_and_filters():
    store = InMemoryVectorStore(_memory_settings(dim=3))
    near = _node("near", [1.0, 0.0, 0.0])
    far = _node("far", [0.0, 1.0, 0.0])
    store.upsert_many([near, far])
    assert store.count() == 2
    out = store.similarity_search([1.0, 0.0, 0.0], top_k=2)
    assert [r.node.content for r in out] == ["near", "far"]
    assert out[0].similarity > out[1].similarity

    # dimension mismatch is rejected like the Postgres backend
    with pytest.raises(ValueError):
        store.similarity_search([1.0, 0.0], top_k=1)


def test_min_confidence_and_ttl_filtering():
    store = InMemoryVectorStore(_memory_settings(dim=3))
    low = _node("low-conf", [1.0, 0.0, 0.0], confidence=0.1)
    expired = _node("expired", [1.0, 0.0, 0.0], ttl=utcnow() - timedelta(days=1))
    live = _node("live", [1.0, 0.0, 0.0])
    store.upsert_many([low, expired, live])

    got = store.similarity_search([1.0, 0.0, 0.0], top_k=5, min_confidence=0.5)
    contents = {r.node.content for r in got}
    assert "low-conf" not in contents  # below min_confidence
    assert "expired" not in contents  # past TTL
    assert "live" in contents

    # include_expired surfaces the expired node again
    with_expired = store.similarity_search(
        [1.0, 0.0, 0.0], top_k=5, include_expired=True
    )
    assert "expired" in {r.node.content for r in with_expired}
    assert sorted(store.expired_node_ids(confidence_floor=1.0)) == [expired.id]


def test_keyword_search_matches_terms():
    store = InMemoryVectorStore(_memory_settings(dim=3))
    store.upsert_many(
        [
            _node("the quick brown fox", [1.0, 0.0, 0.0]),
            _node("lazy dogs sleep", [0.0, 1.0, 0.0]),
        ]
    )
    hits = store.keyword_search("quick fox", top_k=5)
    assert hits and hits[0].node.content == "the quick brown fox"
    assert 0.0 < hits[0].similarity <= 1.0


def test_lifecycle_mutations_and_get_many():
    store = InMemoryVectorStore(_memory_settings(dim=3))
    n = _node("v", [1.0, 0.0, 0.0])
    store.upsert_node(n)
    store.update_confidence(n.id, 0.99)
    assert store.get(n.id).confidence_score == 0.99
    assert store.bump_version(n.id, content="v2") == 2
    assert store.get(n.id).content == "v2"
    store.mark_accessed(n.id)
    assert store.get(n.id).last_accessed_at is not None
    assert [x.id for x in store.get_many([n.id, "missing"])] == [n.id]
    assert [x.id for x in store.iter_all()] == [n.id]
    store.delete(n.id)
    assert store.get(n.id) is None and store.count() == 0


# --- document + provenance stores ------------------------------------------


def test_document_store_dedup_by_hash():
    ds = InMemoryDocumentStore()
    d1 = Document(content="hello", source_id="s", content_hash="h1")
    d2 = Document(content="hello again", source_id="s", content_hash="h1")
    first = ds.save(d1)
    assert ds.save(d2) == first  # same hash ⇒ reused id
    assert ds.exists("h1") and ds.find_by_hash("h1").id == first
    assert [d.id for d in ds.get_by_source("s")] == [first]
    ds.delete(first)
    assert not ds.exists("h1")


def test_provenance_chain_and_sources():
    pt = InMemoryProvenanceTracker()
    pt.record(ProvenanceRecord(node_id="n1", source_id="srcA", source_type="doc"))
    pt.record(ProvenanceRecord(node_id="n2", source_id="srcB", source_type="doc"))
    assert [r.source_id for r in pt.for_node("n1")] == ["srcA"]
    assert sorted(pt.sources_for_nodes(["n1", "n2"])) == ["srcA", "srcB"]
    assert pt.sources_for_nodes([]) == []


# --- bridge backend selection ----------------------------------------------


def test_bridge_factory_defaults_to_memory_without_postgres(monkeypatch):
    from hermes_cli.jarvis_prime import second_brain_bridge as sbb

    monkeypatch.delenv("SECOND_BRAIN_BACKEND", raising=False)
    monkeypatch.delenv("SECOND_BRAIN_PG_HOST", raising=False)
    brain = sbb._default_factory(enable_graph=False)
    try:
        assert brain.settings.backend == "memory"  # zero-infra "just works"
    finally:
        brain.close()


def test_bridge_factory_respects_explicit_backend(monkeypatch):
    from hermes_cli.jarvis_prime import second_brain_bridge as sbb

    monkeypatch.setenv("SECOND_BRAIN_BACKEND", "postgres")
    brain = sbb._default_factory(enable_graph=False)
    try:
        assert brain.settings.backend == "postgres"  # explicit choice wins
    finally:
        brain.close()
