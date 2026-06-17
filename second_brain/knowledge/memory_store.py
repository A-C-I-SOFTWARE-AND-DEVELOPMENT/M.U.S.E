"""In-memory backend (Layer 2 — Persistent Storage, zero-infrastructure).

A dependency-free, process-local implementation of the three storage stores
(`VectorStore`, `DocumentStore`, `ProvenanceTracker`). It satisfies the exact
public surface the rest of the package depends on — the ingestion pipeline, the
hybrid :class:`~knowledge.retrieval_orchestrator.RetrievalOrchestrator`, and the
lifecycle manager all take their stores by injection — so the full
``ingest_text → retrieve`` path runs with **no Postgres, no Neo4j, no drivers**.

This is what makes the Second Brain usable in MUSE's local-first default and in
CI: it is selected with ``SECOND_BRAIN_BACKEND=memory`` (see
:func:`~knowledge.config.load_settings`). Vector search reuses
:func:`~knowledge.models.cosine_similarity`; the keyword fallback reuses the
in-memory :class:`~knowledge.retrieval_orchestrator.BM25Ranker`. Semantics
(TTL filtering, ``min_confidence`` gating, reinforcement, versioning) mirror the
Postgres backend so retrieval results are equivalent.

It is **not** durable (state lives in dicts for the life of the process) and is
not optimized for large corpora — for production scale use the Postgres backend.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Iterator, List, Optional, Sequence

from .config import Settings
from .models import (
    Document,
    MemoryNode,
    ProvenanceRecord,
    RetrievalResult,
    RetrievalSource,
    cosine_similarity,
    utcnow,
)
from .retrieval_orchestrator import BM25Ranker

logger = logging.getLogger(__name__)

__all__ = [
    "InMemoryVectorStore",
    "InMemoryDocumentStore",
    "InMemoryProvenanceTracker",
]


def _is_expired(node: MemoryNode, *, now: datetime) -> bool:
    return node.ttl_expires_at is not None and node.ttl_expires_at <= now


class InMemoryVectorStore:
    """Dict-backed node store + brute-force cosine search (no database).

    Mirrors :class:`~knowledge.vector_store.VectorStore`'s public surface. Nodes
    are stored by id; updates mutate the stored objects in place (``MemoryNode``
    is a mutable ``slots`` dataclass).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._dim = settings.embedding.dimension
        self._nodes: Dict[str, MemoryNode] = {}
        # Append-only version snapshots, mirroring the Postgres ``node_versions``
        # audit table (used for rollback/audit; never read on the hot path).
        self._versions: List[dict] = []

    # -- writes ------------------------------------------------------------ #
    def upsert_node(self, node: MemoryNode) -> None:
        self._nodes[node.id] = node

    def upsert_many(self, nodes: Sequence[MemoryNode]) -> None:
        for node in nodes:
            self._nodes[node.id] = node

    def update_confidence(self, node_id: str, confidence: float) -> None:
        node = self._nodes.get(node_id)
        if node is not None:
            node.confidence_score = confidence
            node.updated_at = utcnow()

    def update_embedding(self, node_id: str, embedding: Sequence[float]) -> None:
        node = self._nodes.get(node_id)
        if node is not None:
            node.embedding = [float(x) for x in embedding]
            node.updated_at = utcnow()

    def increment_reinforcement(
        self, node_id: str, *, confidence: float, ttl_until: Optional[datetime]
    ) -> None:
        node = self._nodes.get(node_id)
        if node is None:
            return
        node.reinforcement_count += 1
        node.confidence_score = confidence
        if ttl_until is not None:
            node.ttl_expires_at = ttl_until
        now = utcnow()
        node.last_accessed_at = now
        node.updated_at = now

    def mark_accessed(self, node_id: str) -> None:
        node = self._nodes.get(node_id)
        if node is not None:
            node.last_accessed_at = utcnow()

    def bump_version(self, node_id: str, *, content: Optional[str] = None) -> int:
        node = self._nodes.get(node_id)
        if node is None:
            return 0
        node.version += 1
        if content is not None:
            node.content = content
        node.updated_at = utcnow()
        return node.version

    def record_version(self, node: MemoryNode, *, reason: str) -> None:
        self._versions.append(
            {
                "node_id": node.id,
                "version": node.version,
                "content": node.content,
                "confidence_score": node.confidence_score,
                "reason": reason,
            }
        )

    def delete(self, node_id: str) -> None:
        self._nodes.pop(node_id, None)

    # -- reads ------------------------------------------------------------- #
    def get(self, node_id: str) -> Optional[MemoryNode]:
        return self._nodes.get(node_id)

    def get_many(self, node_ids: Sequence[str]) -> List[MemoryNode]:
        out: List[MemoryNode] = []
        for node_id in node_ids:
            node = self._nodes.get(node_id)
            if node is not None:
                out.append(node)
        return out

    def count(self) -> int:
        return len(self._nodes)

    def similarity_search(
        self,
        embedding: Sequence[float],
        top_k: int,
        *,
        min_confidence: float = 0.0,
        include_expired: bool = False,
    ) -> List[RetrievalResult]:
        if len(embedding) != self._dim:
            raise ValueError(
                f"query embedding dim {len(embedding)} != configured {self._dim}"
            )
        now = utcnow()
        scored: List[RetrievalResult] = []
        for node in self._nodes.values():
            if node.confidence_score < min_confidence:
                continue
            if not include_expired and _is_expired(node, now=now):
                continue
            similarity = cosine_similarity(embedding, node.embedding)
            scored.append(
                RetrievalResult(
                    node=node,
                    similarity=similarity,
                    sources=[RetrievalSource.VECTOR],
                )
            )
        scored.sort(key=lambda r: r.similarity, reverse=True)
        return scored[:top_k]

    def keyword_search(self, query: str, top_k: int) -> List[RetrievalResult]:
        now = utcnow()
        docs = {
            node.id: node.content
            for node in self._nodes.values()
            if not _is_expired(node, now=now)
        }
        if not docs:
            return []
        ranked = BM25Ranker(docs).normalized_scores(query, top_k)
        results: List[RetrievalResult] = []
        for node_id, score in ranked:
            node = self._nodes.get(node_id)
            if node is None:
                continue
            results.append(
                RetrievalResult(
                    node=node,
                    similarity=score,
                    sources=[RetrievalSource.KEYWORD],
                )
            )
        return results

    def iter_all(self, *, batch_size: int = 500) -> Iterator[MemoryNode]:
        # Deterministic order by id, matching the Postgres keyset iteration.
        for node_id in sorted(self._nodes):
            yield self._nodes[node_id]

    def expired_node_ids(self, *, confidence_floor: float) -> List[str]:
        now = utcnow()
        return [
            node.id
            for node in self._nodes.values()
            if node.ttl_expires_at is not None
            and node.ttl_expires_at <= now
            and node.confidence_score < confidence_floor
        ]


class InMemoryDocumentStore:
    """Dict-backed raw-document store, de-duplicated by content hash."""

    def __init__(self) -> None:
        self._docs: Dict[str, Document] = {}
        self._by_hash: Dict[str, str] = {}

    def save(self, document: Document) -> str:
        if document.content_hash:
            existing_id = self._by_hash.get(document.content_hash)
            if existing_id is not None:
                return existing_id
        self._docs[document.id] = document
        if document.content_hash:
            self._by_hash[document.content_hash] = document.id
        return document.id

    def get(self, document_id: str) -> Optional[Document]:
        return self._docs.get(document_id)

    def find_by_hash(self, content_hash: Optional[str]) -> Optional[Document]:
        if not content_hash:
            return None
        doc_id = self._by_hash.get(content_hash)
        return self._docs.get(doc_id) if doc_id is not None else None

    def get_by_source(self, source_id: str) -> List[Document]:
        matches = [d for d in self._docs.values() if d.source_id == source_id]
        matches.sort(key=lambda d: d.created_at)
        return matches

    def exists(self, content_hash: str) -> bool:
        return self.find_by_hash(content_hash) is not None

    def delete(self, document_id: str) -> None:
        doc = self._docs.pop(document_id, None)
        if doc is not None and doc.content_hash:
            self._by_hash.pop(doc.content_hash, None)


class InMemoryProvenanceTracker:
    """Append-only, in-memory provenance chain."""

    def __init__(self) -> None:
        self._records: List[ProvenanceRecord] = []

    def record(self, record: ProvenanceRecord) -> str:
        self._records.append(record)
        return record.id

    def for_node(self, node_id: str) -> List[ProvenanceRecord]:
        chain = [r for r in self._records if r.node_id == node_id]
        chain.sort(key=lambda r: r.ingested_at)
        return chain

    def sources_for_nodes(self, node_ids: Sequence[str]) -> List[str]:
        wanted = set(node_ids)
        seen: List[str] = []
        for record in self._records:
            if record.node_id in wanted and record.source_id not in seen:
                seen.append(record.source_id)
        return seen
