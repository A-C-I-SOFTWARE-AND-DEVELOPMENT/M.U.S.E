"""Tests for the optional Memory Tree dense-embedding retrieval lane.

Mirrors the holographic embedding suite's posture: deterministic, no model
downloads, and explicit coverage of (a) byte-identical behavior when the lane
is off, (b) graceful degradation when a backend can't embed, (c) the blended
ranking surfacing semantic-only matches, and (d) the verifier gate promoting
only a real lift.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pytest

from hermes_cli.jarvis_prime import memory_tree_embeddings as mte
from hermes_cli.jarvis_prime.memory_tree import MemoryLayer, MemoryTreeStore
from hermes_cli.jarvis_prime.memory_tree_eval import RetrievalCase, score_retrieval


# ---------------------------------------------------------------------------
# Deterministic fake backends (no ML deps)
# ---------------------------------------------------------------------------


class _ConceptBackend:
    """Maps text to a small concept-space vector so semantically related text
    with *no shared tokens* still scores a high cosine (unlike bag-of-words)."""

    name = "concept"
    model_name = "v1"
    dim = 2

    _CONCEPTS = {
        0: {
            "vector", "search", "embeddings", "semantic", "similarity",
            "nearest", "neighbor", "neighbors", "retrieval", "dense", "knn",
            "lookup", "cosine",
        },
        1: {"france", "paris", "capital", "eiffel", "tower", "landmark"},
    }

    def embed(self, text):
        if not text:
            return None
        vec = [0.0, 0.0]
        for word in text.lower().split():
            for dim, bag in self._CONCEPTS.items():
                if word in bag:
                    vec[dim] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def is_available(self):
        return True


class _DeadBackend:
    """Available, but every embed() fails — exercises graceful degradation."""

    name = "dead"
    model_name = "v0"
    dim = 0

    def embed(self, text):
        return None

    def is_available(self):
        return True


def _enable_lane(store: MemoryTreeStore, backend, weight: float = 0.35) -> None:
    sidecar = store._embedding_sidecar_path()
    store.embedding_weight = weight
    store._emb_ready = True
    store._emb_weight = weight
    store._emb_index = mte.MemoryTreeEmbeddingIndex(backend, sidecar)


def _store(tmp_path: Path) -> MemoryTreeStore:
    return MemoryTreeStore(path=tmp_path / "memory_tree.jsonl")


# ---------------------------------------------------------------------------
# Off-path parity
# ---------------------------------------------------------------------------


def test_lane_off_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_MEMORY_TREE_EMBEDDINGS", raising=False)
    monkeypatch.delenv("HERMES_MEMORY_TREE_EMBED_WEIGHT", raising=False)
    store = _store(tmp_path)
    assert store._embeddings() is None
    assert getattr(store, "_emb_weight", 0.0) == 0.0


def test_score_unchanged_when_lane_off(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_MEMORY_TREE_EMBEDDINGS", raising=False)
    store = _store(tmp_path)
    store.write("Paris is the capital of France", namespace="jarvis/general",
                title="france", persist=False)
    node = next(iter(store.nodes.values()))
    # emb_sim=None (off) and any emb_sim with zero weight must match the base.
    base = store._score(node, 1, 2)
    assert store._score(node, 1, 2, emb_sim=None) == base
    assert store._score(node, 1, 2, emb_sim=0.99) == base  # weight is 0


def test_zero_overlap_excluded_when_lane_off(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_MEMORY_TREE_EMBEDDINGS", raising=False)
    store = _store(tmp_path)
    store.write("vector search embeddings dense knn", namespace="jarvis/general",
                title="retrieval note", persist=False)
    # Query shares no lexical term — off path drops it.
    hits = store.search("france capital paris")
    assert hits == []


# ---------------------------------------------------------------------------
# Blended ranking
# ---------------------------------------------------------------------------


def test_blend_surfaces_semantic_only_node(tmp_path):
    store = _store(tmp_path)
    store.write("vector search embeddings dense knn", namespace="jarvis/general",
                title="retrieval note", persist=True)
    store.write("The Eiffel Tower is in Paris", namespace="jarvis/general",
                title="paris landmark", persist=True)
    _enable_lane(store, _ConceptBackend(), weight=0.5)

    # Query has no lexical overlap with either title/text, but is concept-0.
    hits = store.search("semantic similarity lookup")
    assert hits, "dense lane should surface semantic-only candidates"
    assert hits[0].node.title == "retrieval note"


def test_graceful_degradation_when_backend_cannot_embed(tmp_path):
    store = _store(tmp_path)
    store.write("vector search embeddings dense knn", namespace="jarvis/general",
                title="retrieval note", persist=True)
    _enable_lane(store, _DeadBackend(), weight=0.5)
    # Query embed returns None -> lane inactive for this call -> lexical only.
    hits = store.search("semantic similarity lookup")
    assert hits == []  # no lexical overlap, and dense produced nothing
    # A lexical query still works normally.
    lexical = store.search("vector search")
    assert lexical and lexical[0].node.title == "retrieval note"


# ---------------------------------------------------------------------------
# Sidecar persistence + reindex + ingest hook
# ---------------------------------------------------------------------------


def test_sidecar_persisted_and_reloaded(tmp_path):
    store = _store(tmp_path)
    _enable_lane(store, _ConceptBackend(), weight=0.5)
    store.write("vector search embeddings", namespace="jarvis/general",
                title="a", persist=True)
    store.write("paris eiffel tower", namespace="jarvis/general",
                title="b", persist=True)
    count = store._emb_index.reindex(list(store.nodes.values()))
    assert count == 2
    sidecar = store._embedding_sidecar_path()
    assert sidecar.exists()

    # A fresh index over the same sidecar reads the cached vectors.
    reloaded = mte.MemoryTreeEmbeddingIndex(_ConceptBackend(), sidecar).load()
    assert len(reloaded._cache) == 2


def test_write_embeds_at_ingest_when_lane_on(tmp_path):
    store = _store(tmp_path)
    _enable_lane(store, _ConceptBackend(), weight=0.5)
    result = store.write("vector search embeddings", namespace="jarvis/general",
                         title="a", persist=True)
    assert result.ok
    assert result.node.id in store._emb_index._cache


def test_stale_text_reembeds(tmp_path):
    idx = mte.MemoryTreeEmbeddingIndex(_ConceptBackend(), tmp_path / "s.emb.jsonl")

    class _Node:
        id = "n1"
        title = "vector search"
        summary = ""
        text = "embeddings"
        tags = ()

    n = _Node()
    v1 = idx.vector_for(n)
    assert v1 is not None
    h1 = idx._cache["n1"]["hash"]
    # Changing the indexed text invalidates the cached vector by hash.
    n.text = "paris eiffel tower"
    idx.vector_for(n)
    assert idx._cache["n1"]["hash"] != h1


# ---------------------------------------------------------------------------
# Verifier-gated evaluation
# ---------------------------------------------------------------------------


def _semantic_corpus(tmp_path):
    store = _store(tmp_path)
    # Relevant node: concept-0, but NO lexical overlap with the eval query
    # (title/text share none of the query's tokens).
    rel = store.write("vector search embeddings dense knn", namespace="jarvis/general",
                      title="alpha", persist=True)
    # Distractors: concept-1, also lexically disjoint from the query.
    store.write("paris eiffel tower capital", namespace="jarvis/general",
                title="beta", persist=True)
    return store, rel.node.id


def test_gate_promotes_when_dense_beats_keyword(tmp_path):
    store, rel_id = _semantic_corpus(tmp_path)
    _enable_lane(store, _ConceptBackend(), weight=0.6)
    cases = [RetrievalCase(query="nearest neighbor cosine similarity",
                           relevant_ids=(rel_id,))]
    result = score_retrieval(store, cases, k=5, min_margin=0.05)
    # Keyword baseline can't reach the relevant node (no shared tokens);
    # the dense lane ranks it, so MRR improves and the gate passes.
    assert result["baseline"]["mrr"] == 0.0
    assert result["candidate"]["mrr"] > result["baseline"]["mrr"]
    assert result["gate"]["outcome"] == "pass"
    assert result["promote"] is True


def test_gate_does_not_promote_without_lift(tmp_path):
    store = _store(tmp_path)
    rel = store.write("vector search embeddings", namespace="jarvis/general",
                      title="retrieval", persist=True)
    _enable_lane(store, _ConceptBackend(), weight=0.6)
    # Query lexically matches the relevant node, so keyword already wins;
    # the dense term can't improve MRR (already 1.0) -> no promotion.
    cases = [RetrievalCase(query="vector search embeddings", relevant_ids=(rel.node.id,))]
    result = score_retrieval(store, cases, k=5, min_margin=0.05)
    assert result["baseline"]["mrr"] == pytest.approx(1.0)
    assert result["promote"] is False


def test_resolve_config_env(monkeypatch):
    monkeypatch.setenv("HERMES_MEMORY_TREE_EMBEDDINGS", "1")
    monkeypatch.setenv("HERMES_MEMORY_TREE_EMBED_WEIGHT", "0.4")
    cfg = mte.resolve_embedding_config()
    assert cfg["enabled"] is True
    assert cfg["weight"] == pytest.approx(0.4)
    assert cfg["embeddings"]["enabled"] is True


def test_indexed_text_matches_search_hay():
    class _Node:
        title = "T"
        summary = "S"
        text = "X"
        tags = ("a", "b")

    assert mte.indexed_text(_Node()) == "T S X a b"
