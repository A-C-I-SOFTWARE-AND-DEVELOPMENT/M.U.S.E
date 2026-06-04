"""Governance & lifecycle management (Layer 5).

Implements the knowledge-lifecycle controls that keep the store healthy over
time:

* **TTL decay** — confidence decays with age; expired, low-confidence nodes
  are pruned.
* **Reinforcement scoring** — re-accessed/corroborated nodes gain confidence
  and an extended TTL.
* **Consolidation** — near-duplicate embeddings are merged into a single
  canonical node with a bumped version and audit snapshot.
* **Scheduled embedding refresh** — a pluggable scheduler decides which nodes
  to re-embed (e.g. after an embedding-model upgrade).
* **Version tracking** — every mutation can append an immutable snapshot to
  ``node_versions`` for audit and rollback.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Optional, Sequence

from .config import Settings
from .confidence import ConfidenceEngine
from .models import (
    LifecycleVectorStore,
    MemoryNode,
    ProvenanceRecord,
    SupportsGraphDelete,
    SupportsProvenanceRecord,
    cosine_similarity,
    utcnow,
)

if TYPE_CHECKING:
    from .ingestion import EmbeddingProvider

logger = logging.getLogger(__name__)

__all__ = [
    "LifecycleReport",
    "EmbeddingRefreshScheduler",
    "IntervalRefreshScheduler",
    "MemoryLifecycleManager",
]


@dataclass(slots=True)
class LifecycleReport:
    """Counters describing a maintenance run."""

    scanned: int = 0
    decayed: int = 0
    expired: int = 0
    consolidated: int = 0
    duplicates_removed: int = 0
    refreshed: int = 0
    versions_recorded: int = 0

    def merge(self, other: "LifecycleReport") -> "LifecycleReport":
        return LifecycleReport(
            scanned=self.scanned + other.scanned,
            decayed=self.decayed + other.decayed,
            expired=self.expired + other.expired,
            consolidated=self.consolidated + other.consolidated,
            duplicates_removed=self.duplicates_removed + other.duplicates_removed,
            refreshed=self.refreshed + other.refreshed,
            versions_recorded=self.versions_recorded + other.versions_recorded,
        )


class EmbeddingRefreshScheduler(abc.ABC):
    """Abstraction deciding which nodes are due for re-embedding."""

    @abc.abstractmethod
    def is_due(self, node: MemoryNode, *, now: datetime) -> bool:
        """Return ``True`` if ``node`` should be re-embedded now."""

    def due_nodes(
        self, nodes: Sequence[MemoryNode], *, now: Optional[datetime] = None
    ) -> List[MemoryNode]:
        now = now or utcnow()
        return [node for node in nodes if self.is_due(node, now=now)]


class IntervalRefreshScheduler(EmbeddingRefreshScheduler):
    """Refresh nodes whose embedding is older than a fixed interval.

    Also honours an explicit ``metadata['embedding_stale'] is True`` flag set
    by an upstream model-version migration.
    """

    def __init__(self, interval_days: float) -> None:
        self._interval = max(0.0, interval_days)

    def is_due(self, node: MemoryNode, *, now: datetime) -> bool:
        if node.metadata.get("embedding_stale") is True:
            return True
        if self._interval <= 0:
            return False
        age_days = (now - node.updated_at).total_seconds() / 86400.0
        return age_days >= self._interval


class MemoryLifecycleManager:
    """Coordinates decay, expiry, reinforcement, consolidation, and refresh."""

    def __init__(
        self,
        vector_store: LifecycleVectorStore,
        *,
        settings: Settings,
        confidence_engine: Optional[ConfidenceEngine] = None,
        graph_store: Optional[SupportsGraphDelete] = None,
        embedding_provider: Optional["EmbeddingProvider"] = None,
        provenance: Optional[SupportsProvenanceRecord] = None,
    ) -> None:
        self._vector_store = vector_store
        self._settings = settings
        self._confidence = confidence_engine or ConfidenceEngine(settings.lifecycle)
        self._graph_store = graph_store
        self._embeddings = embedding_provider
        self._provenance = provenance

    # -- TTL decay & expiry ----------------------------------------------- #
    def decay_confidence(self, *, now: Optional[datetime] = None) -> LifecycleReport:
        """Apply time decay to every node's confidence score."""
        now = now or utcnow()
        report = LifecycleReport()
        for node in self._vector_store.iter_all():
            report.scanned += 1
            age_days = (now - node.updated_at).total_seconds() / 86400.0
            new_conf = self._confidence.apply_time_decay(
                node.confidence_score, age_days=age_days
            )
            if abs(new_conf - node.confidence_score) > 1e-4:
                self._vector_store.update_confidence(node.id, new_conf)
                report.decayed += 1
        logger.info("decay_confidence scanned=%d decayed=%d",
                    report.scanned, report.decayed)
        return report

    def expire_stale(self) -> LifecycleReport:
        """Delete nodes past their TTL whose confidence is below the floor."""
        report = LifecycleReport()
        floor = self._settings.lifecycle.expiry_confidence_floor
        node_ids = self._vector_store.expired_node_ids(confidence_floor=floor)
        for node_id in node_ids:
            self._delete_everywhere(node_id)
            report.expired += 1
        logger.info("expire_stale expired=%d", report.expired)
        return report

    # -- reinforcement ----------------------------------------------------- #
    def reinforce(self, node_id: str, *, times: int = 1) -> Optional[MemoryNode]:
        """Reinforce a node: raise confidence and extend its TTL."""
        node = self._vector_store.get(node_id)
        if node is None:
            logger.warning("reinforce: node %s not found", node_id)
            return None
        new_conf = self._confidence.apply_reinforcement(node.confidence_score, times=times)
        extension_days = self._settings.lifecycle.reinforcement_ttl_extension_days
        ttl_until = utcnow() + timedelta(days=extension_days) if extension_days > 0 else None
        self._vector_store.increment_reinforcement(
            node_id, confidence=new_conf, ttl_until=ttl_until
        )
        # Re-read so the returned node reflects authoritative post-write state
        # regardless of how the store implements identity/caching.
        return self._vector_store.get(node_id) or node

    # -- consolidation ----------------------------------------------------- #
    def consolidate(self, *, similarity_threshold: Optional[float] = None) -> LifecycleReport:
        """Merge near-duplicate nodes (by embedding cosine similarity)."""
        threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else self._settings.lifecycle.consolidation_similarity_threshold
        )
        nodes = [n for n in self._vector_store.iter_all() if n.embedding]
        report = LifecycleReport(scanned=len(nodes))
        consumed: set[str] = set()
        for i, anchor in enumerate(nodes):
            if anchor.id in consumed:
                continue
            duplicates: List[MemoryNode] = []
            for other in nodes[i + 1:]:
                if other.id in consumed or len(other.embedding) != len(anchor.embedding):
                    continue
                if cosine_similarity(anchor.embedding, other.embedding) >= threshold:
                    duplicates.append(other)
            if not duplicates:
                continue
            canonical = self._merge_group(anchor, duplicates)
            report.consolidated += 1
            report.versions_recorded += 1
            for dup in duplicates:
                consumed.add(dup.id)
                self._delete_everywhere(dup.id)
                report.duplicates_removed += 1
            consumed.add(canonical.id)
        logger.info(
            "consolidate scanned=%d groups=%d removed=%d",
            report.scanned, report.consolidated, report.duplicates_removed,
        )
        return report

    def _merge_group(self, anchor: MemoryNode, duplicates: Sequence[MemoryNode]) -> MemoryNode:
        group = [anchor, *duplicates]
        canonical = max(group, key=lambda n: (n.confidence_score, n.updated_at))
        entities = list(dict.fromkeys(e for n in group for e in n.entities))
        relationships = list(dict.fromkeys(r for n in group for r in n.relationships))
        merged_conf = self._confidence.adjust_for_corroboration(
            canonical.confidence_score, corroborations=len(duplicates)
        )
        self._vector_store.record_version(canonical, reason="pre-consolidation snapshot")
        canonical.entities = entities
        canonical.relationships = relationships
        canonical.confidence_score = merged_conf
        canonical.version += 1
        canonical.updated_at = utcnow()
        canonical.metadata = dict(canonical.metadata)
        canonical.metadata["consolidated_from"] = [d.id for d in duplicates]
        self._vector_store.upsert_node(canonical)
        if self._provenance is not None:
            try:
                self._provenance.record(
                    ProvenanceRecord(
                        node_id=canonical.id,
                        source_id=canonical.source_id,
                        source_type="consolidation",
                        transformation="consolidate_near_duplicates",
                        content_hash=canonical.content_hash,
                        metadata={"merged": [d.id for d in duplicates]},
                    )
                )
            except Exception:  # pragma: no cover - best effort
                logger.exception("consolidation provenance failed for %s", canonical.id)
        return canonical

    # -- scheduled refresh ------------------------------------------------- #
    def refresh_embeddings(
        self, scheduler: EmbeddingRefreshScheduler, *, batch_size: int = 64
    ) -> LifecycleReport:
        """Re-embed nodes the scheduler marks as due, in batches."""
        if self._embeddings is None:
            raise RuntimeError("refresh_embeddings requires an embedding_provider")
        report = LifecycleReport()
        now = utcnow()
        batch: List[MemoryNode] = []
        for node in self._vector_store.iter_all():
            report.scanned += 1
            if scheduler.is_due(node, now=now):
                batch.append(node)
            if len(batch) >= batch_size:
                report.refreshed += self._reembed_batch(batch)
                batch = []
        if batch:
            report.refreshed += self._reembed_batch(batch)
        logger.info("refresh_embeddings scanned=%d refreshed=%d",
                    report.scanned, report.refreshed)
        return report

    def _reembed_batch(self, batch: Sequence[MemoryNode]) -> int:
        provider = self._embeddings
        if provider is None:
            raise RuntimeError("refresh_embeddings requires an embedding_provider")
        texts = [node.content for node in batch]
        vectors = provider.embed(texts)
        count = 0
        for node, vector in zip(batch, vectors):
            self._vector_store.update_embedding(node.id, vector)
            if node.metadata.get("embedding_stale"):
                node.metadata.pop("embedding_stale", None)
            count += 1
        return count

    # -- orchestration ----------------------------------------------------- #
    def run_maintenance(self, *, refresh: bool = False) -> LifecycleReport:
        """Run decay, expiry, consolidation, and (optionally) refresh."""
        report = self.decay_confidence()
        report = report.merge(self.expire_stale())
        report = report.merge(self.consolidate())
        if refresh and self._embeddings is not None:
            scheduler = IntervalRefreshScheduler(
                self._settings.lifecycle.refresh_interval_days
            )
            report = report.merge(self.refresh_embeddings(scheduler))
        return report

    # -- helpers ----------------------------------------------------------- #
    def _delete_everywhere(self, node_id: str) -> None:
        self._vector_store.delete(node_id)
        if self._graph_store is not None:
            try:
                self._graph_store.delete_node(node_id)
            except Exception:  # pragma: no cover - best effort
                logger.exception("graph delete failed for %s", node_id)
