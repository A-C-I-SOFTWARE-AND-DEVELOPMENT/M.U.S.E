"""Hybrid retrieval orchestrator (Layer 3).

Combines dense vector search, graph expansion, and an optional keyword
(BM25 / full-text) fallback into a single, ranked, token-budgeted context
payload ready for injection into a model prompt.

Ranking follows the architecture's priority formula::

    priority_score = (similarity * 0.5) + (confidence * 0.3) + (recency * 0.2)

The weights are configurable via :class:`~knowledge.config.RetrievalConfig`
but default to the values above.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Dict, List, Mapping, Optional, Sequence

from .config import Settings
from .ingestion import EmbeddingProvider
from .models import (
    ContextBlock,
    InjectionPayload,
    MemoryNode,
    RetrievalResult,
    RetrievalSource,
    SupportsGraphExpansion,
    SupportsVectorSearch,
    cosine_similarity,
    estimate_tokens,
    tokenize_words,
    utcnow,
)

logger = logging.getLogger(__name__)

__all__ = ["BM25Ranker", "recency_score", "RetrievalOrchestrator"]


def recency_score(created_at: datetime, *, now: datetime, half_life_days: float) -> float:
    """Map a node's age to a recency weight in ``(0, 1]`` via half-life decay."""
    age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    half_life = max(1e-6, half_life_days)
    return math.pow(0.5, age_days / half_life)


class BM25Ranker:
    """A compact in-memory BM25 ranker for the keyword fallback path.

    Suitable when no database full-text index is available (offline use,
    tests, or small candidate sets). Construct with a mapping of
    ``{node_id: text}`` and call :meth:`rank`.
    """

    def __init__(
        self, documents: Mapping[str, str], *, k1: float = 1.5, b: float = 0.75
    ) -> None:
        self._k1 = k1
        self._b = b
        self._doc_terms: Dict[str, List[str]] = {
            doc_id: tokenize_words(text) for doc_id, text in documents.items()
        }
        self._doc_len: Dict[str, int] = {
            doc_id: len(terms) for doc_id, terms in self._doc_terms.items()
        }
        self._avgdl = (
            sum(self._doc_len.values()) / len(self._doc_len) if self._doc_len else 0.0
        )
        self._term_freq: Dict[str, Dict[str, int]] = {}
        self._doc_freq: Dict[str, int] = {}
        for doc_id, terms in self._doc_terms.items():
            seen: Dict[str, int] = {}
            for term in terms:
                seen[term] = seen.get(term, 0) + 1
            self._term_freq[doc_id] = seen
            for term in seen:
                self._doc_freq[term] = self._doc_freq.get(term, 0) + 1
        self._n = len(self._doc_terms)

    def rank(self, query: str, top_k: int) -> List[tuple[str, float]]:
        """Return up to ``top_k`` ``(node_id, score)`` pairs sorted by score."""
        if self._n == 0:
            return []
        query_terms = tokenize_words(query)
        scores: Dict[str, float] = {}
        for doc_id in self._doc_terms:
            score = 0.0
            freqs = self._term_freq[doc_id]
            dl = self._doc_len[doc_id] or 1
            for term in query_terms:
                tf = freqs.get(term, 0)
                if tf == 0:
                    continue
                df = self._doc_freq.get(term, 0)
                idf = math.log(1.0 + (self._n - df + 0.5) / (df + 0.5))
                denom = tf + self._k1 * (1.0 - self._b + self._b * dl / (self._avgdl or 1.0))
                score += idf * (tf * (self._k1 + 1.0)) / denom
            if score > 0.0:
                scores[doc_id] = score
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:top_k]

    def normalized_scores(self, query: str, top_k: int) -> List[tuple[str, float]]:
        """Like :meth:`rank` but scores are squashed into ``(0, 1)``."""
        return [(doc_id, s / (s + 1.0)) for doc_id, s in self.rank(query, top_k)]


class RetrievalOrchestrator:
    """Coordinates vector, graph, and keyword retrieval into one payload."""

    def __init__(
        self,
        vector_store: SupportsVectorSearch,
        *,
        embedding_provider: EmbeddingProvider,
        settings: Settings,
        graph_store: Optional[SupportsGraphExpansion] = None,
        keyword_ranker: Optional[BM25Ranker] = None,
    ) -> None:
        self._vector_store = vector_store
        self._graph_store = graph_store
        self._embeddings = embedding_provider
        self._settings = settings
        self._keyword_ranker = keyword_ranker

    def retrieve(
        self,
        query: str,
        *,
        top_k: Optional[int] = None,
        token_budget: Optional[int] = None,
        hops: Optional[int] = None,
        use_keyword_fallback: Optional[bool] = None,
        min_confidence: float = 0.0,
    ) -> InjectionPayload:
        """Retrieve, rank, and budget a context payload for ``query``."""
        cfg = self._settings.retrieval
        top_k = top_k or cfg.top_k
        token_budget = token_budget or cfg.token_budget
        hops = cfg.graph_hops if hops is None else hops
        if use_keyword_fallback is None:
            use_keyword_fallback = cfg.enable_keyword_fallback

        query_embedding = self._embeddings.embed_one(query)
        candidates: Dict[str, RetrievalResult] = {}

        # 1) Dense vector search.
        vector_hits = self._vector_store.similarity_search(
            query_embedding, top_k, min_confidence=min_confidence
        )
        for hit in vector_hits:
            self._merge(candidates, hit)
        logger.debug("vector hits=%d", len(vector_hits))

        # 2) Graph expansion on the strongest seeds.
        if self._graph_store is not None and vector_hits:
            seed_ids = [hit.node.id for hit in vector_hits[: max(1, top_k // 2)]]
            self._expand_graph(candidates, seed_ids, query_embedding, hops)

        # 3) Optional keyword fallback when dense recall is thin.
        if use_keyword_fallback and len(candidates) < cfg.keyword_fallback_threshold:
            self._keyword_fallback(candidates, query, top_k)

        ranked = self._rank(list(candidates.values()))
        payload = self._build_payload(query, ranked, token_budget)
        logger.info(
            "retrieve query_len=%d candidates=%d returned=%d tokens=%d",
            len(query), len(candidates), len(payload.blocks), payload.total_tokens,
        )
        return payload

    # -- pipeline stages --------------------------------------------------- #
    def _expand_graph(
        self,
        candidates: Dict[str, RetrievalResult],
        seed_ids: Sequence[str],
        query_embedding: Sequence[float],
        hops: int,
    ) -> None:
        cfg = self._settings.retrieval
        graph_store = self._graph_store
        if graph_store is None:
            return
        try:
            neighbors = graph_store.expand(seed_ids, hops, cfg.graph_expansion_limit)
        except Exception:  # pragma: no cover - graph is best-effort
            logger.exception("Graph expansion failed; continuing without it")
            return
        new_ids = [n.node_id for n in neighbors if n.node_id not in candidates]
        if not new_ids:
            return
        fetched = self._fetch_nodes(new_ids)
        distance_by_id = {n.node_id: n.distance for n in neighbors}
        for node in fetched:
            similarity = cosine_similarity(query_embedding, node.embedding)
            self._merge(
                candidates,
                RetrievalResult(
                    node=node,
                    similarity=similarity,
                    sources=[RetrievalSource.GRAPH],
                    graph_distance=distance_by_id.get(node.id),
                ),
            )

    def _keyword_fallback(
        self, candidates: Dict[str, RetrievalResult], query: str, top_k: int
    ) -> None:
        # Prefer a database-backed full-text search when available.
        keyword_search = getattr(self._vector_store, "keyword_search", None)
        if callable(keyword_search):
            try:
                for hit in keyword_search(query, top_k):
                    self._merge(candidates, hit)
                return
            except Exception:  # pragma: no cover - fall through to BM25
                logger.exception("DB keyword search failed; trying BM25 ranker")
        if self._keyword_ranker is not None:
            scored = self._keyword_ranker.normalized_scores(query, top_k)
            new_ids = [doc_id for doc_id, _ in scored if doc_id not in candidates]
            nodes = {n.id: n for n in self._fetch_nodes(new_ids)}
            for doc_id, score in scored:
                node = nodes.get(doc_id)
                if node is None:
                    continue
                self._merge(
                    candidates,
                    RetrievalResult(
                        node=node, similarity=score, sources=[RetrievalSource.KEYWORD]
                    ),
                )

    def _fetch_nodes(self, node_ids: Sequence[str]) -> List[MemoryNode]:
        get_many = getattr(self._vector_store, "get_many", None)
        if callable(get_many):
            return get_many(node_ids)
        nodes: List[MemoryNode] = []
        for node_id in node_ids:
            node = self._vector_store.get(node_id)
            if node is not None:
                nodes.append(node)
        return nodes

    @staticmethod
    def _merge(
        candidates: Dict[str, RetrievalResult], result: RetrievalResult
    ) -> None:
        existing = candidates.get(result.node.id)
        if existing is None:
            candidates[result.node.id] = result
            return
        existing.similarity = max(existing.similarity, result.similarity)
        for source in result.sources:
            if source not in existing.sources:
                existing.sources.append(source)
        if result.graph_distance is not None and existing.graph_distance is None:
            existing.graph_distance = result.graph_distance

    def _rank(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        cfg = self._settings.retrieval
        now = utcnow()
        for result in results:
            result.recency = recency_score(
                result.node.created_at,
                now=now,
                half_life_days=cfg.recency_half_life_days,
            )
            # Clamp similarity into [0, 1]; anti-correlated vectors score 0.
            similarity_unit = max(0.0, min(1.0, result.similarity))
            result.priority_score = (
                cfg.weight_similarity * similarity_unit
                + cfg.weight_confidence * result.confidence
                + cfg.weight_recency * result.recency
            )
            if len(result.sources) > 1:
                result.sources = [RetrievalSource.HYBRID, *result.sources]
        results.sort(key=lambda r: r.priority_score, reverse=True)
        return results

    def _build_payload(
        self, query: str, ranked: List[RetrievalResult], token_budget: int
    ) -> InjectionPayload:
        payload = InjectionPayload(query=query, token_budget=token_budget)
        used = 0
        citation = 0
        for result in ranked:
            block_tokens = estimate_tokens(result.node.content)
            if used + block_tokens > token_budget and payload.blocks:
                payload.truncated = True
                break
            citation += 1
            payload.blocks.append(
                ContextBlock(
                    citation=citation,
                    node_id=result.node.id,
                    content=result.node.content,
                    source_id=result.node.source_id,
                    similarity=round(result.similarity, 6),
                    confidence=round(result.confidence, 6),
                    recency=round(result.recency, 6),
                    priority_score=round(result.priority_score, 6),
                    retrieval_sources=[s.value for s in result.sources],
                    tokens=block_tokens,
                )
            )
            used += block_tokens
        if len(payload.blocks) < len(ranked):
            payload.truncated = True
        payload.total_tokens = used
        return payload
