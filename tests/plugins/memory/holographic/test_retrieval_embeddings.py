"""Retrieval tests: weight-invariance + semantic re-ranking."""

from __future__ import annotations

import math

from plugins.memory.holographic.embeddings import EmbeddingBackend
from plugins.memory.holographic.retrieval import FactRetriever
from plugins.memory.holographic.store import MemoryStore


class FakeBackend(EmbeddingBackend):
    name = "fake"

    def __init__(self, mapping, dim=2):
        self._mapping = mapping
        self.dim = dim

    def is_available(self) -> bool:
        return True

    def embed(self, text):
        return list(self._mapping.get(text, [1.0] + [0.0] * (self.dim - 1)))


def test_embedding_weight_zero_is_identical_to_no_backend(tmp_path):
    """With embedding_weight=0 the dense term must not change scores at all."""
    facts = [
        ("shared term", "general", ""),
        ("shared term extra extra extra widget", "general", ""),
        ("shared term something else entirely", "general", ""),
    ]

    # Store A: no embedding backend.
    store_a = MemoryStore(db_path=tmp_path / "a.db")
    for c, cat, tg in facts:
        store_a.add_fact(c, category=cat, tags=tg)
    ret_a = FactRetriever(store_a, embedding_weight=0.0)

    # Store B: embedding backend present, but retriever weight is 0.
    store_b = MemoryStore(db_path=tmp_path / "b.db", embedding_backend=FakeBackend({}))
    for c, cat, tg in facts:
        store_b.add_fact(c, category=cat, tags=tg)
    ret_b = FactRetriever(store_b, embedding_weight=0.0)

    try:
        res_a = ret_a.search("shared term", min_trust=0.0, limit=10)
        res_b = ret_b.search("shared term", min_trust=0.0, limit=10)
        assert [r["content"] for r in res_a] == [r["content"] for r in res_b]
        for ra, rb in zip(res_a, res_b):
            assert math.isclose(ra["score"], rb["score"], rel_tol=1e-9, abs_tol=1e-12)
        # Dense term inert, and the non-dense weights are byte-identical to the
        # no-backend retriever (whatever their values are for this environment,
        # which depends on numpy/HRR availability).
        assert ret_b.embedding_weight == 0.0
        assert math.isclose(ret_b.fts_weight, ret_a.fts_weight, abs_tol=1e-12)
        assert math.isclose(ret_b.jaccard_weight, ret_a.jaccard_weight, abs_tol=1e-12)
        assert math.isclose(ret_b.hrr_weight, ret_a.hrr_weight, abs_tol=1e-12)
    finally:
        store_a.close()
        store_b.close()


def test_dense_term_reranks_when_active(tmp_path):
    """A keyword-weaker but embedding-aligned fact should win once the dense
    term dominates — proving embeddings actually participate."""
    # Distinct strings (no content equals the query) so the embedding map has
    # no key collisions. Both facts contain the query tokens so both FTS-match.
    query = "anchor beacon"
    aligned = "anchor beacon filler filler filler"   # keyword-diluted (low jaccard)
    keyword_strong = "beacon anchor"                  # same tokens reordered (jaccard 1.0)

    mapping = {
        query: [1.0, 0.0],
        aligned: [1.0, 0.0],          # cosine 1.0 with query
        keyword_strong: [0.0, 1.0],   # cosine 0.0 with query
    }
    store = MemoryStore(db_path=tmp_path / "rank.db", embedding_backend=FakeBackend(mapping))
    store.add_fact(aligned)
    store.add_fact(keyword_strong)

    try:
        # Baseline (no dense term): the keyword-strong fact ranks first.
        ret0 = FactRetriever(store, embedding_weight=0.0)
        base = ret0.search(query, min_trust=0.0, limit=10)
        assert base[0]["content"] == keyword_strong

        # Dense-only weighting flips it to the embedding-aligned fact.
        ret1 = FactRetriever(
            store, fts_weight=0.0, jaccard_weight=0.0, hrr_weight=0.0, embedding_weight=1.0
        )
        ranked = ret1.search(query, min_trust=0.0, limit=10)
        assert ranked[0]["content"] == aligned
        # Weights must still normalize to 1.0.
        total = ret1.fts_weight + ret1.jaccard_weight + ret1.hrr_weight + ret1.embedding_weight
        assert math.isclose(total, 1.0, abs_tol=1e-9)
        # Result dicts stay JSON-clean (no raw vector bytes leak out).
        assert "embedding" not in ranked[0]
        assert "hrr_vector" not in ranked[0]
    finally:
        store.close()


def test_embeddings_off_when_backend_absent_even_if_weight_set(tmp_path):
    """Requesting an embedding weight with no backend must not activate it."""
    store = MemoryStore(db_path=tmp_path / "noemb.db")  # no backend
    store.add_fact("shared term alpha")
    try:
        ret = FactRetriever(store, embedding_weight=0.5)
        assert ret._embeddings_on is False
        assert ret.embedding_weight == 0.0
        # Still returns results normally.
        res = ret.search("shared term", min_trust=0.0, limit=10)
        assert res and res[0]["content"] == "shared term alpha"
    finally:
        store.close()
