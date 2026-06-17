"""Second Brain knowledge layer.

A hybrid (vector + graph), governed, research-grounded knowledge module.

The five architectural layers map onto modules as follows:

#. **Ingestion & Representation** — :mod:`knowledge.ingestion`, :mod:`knowledge.models`
#. **Persistent Storage** — :mod:`knowledge.vector_store`, :mod:`knowledge.graph_store`,
   :mod:`knowledge.document_store`, :mod:`knowledge.provenance`
#. **Hybrid Retrieval** — :mod:`knowledge.retrieval_orchestrator`
#. **Reasoning** — :mod:`knowledge.reasoning_engine`
#. **Governance & Lifecycle** — :mod:`knowledge.memory_lifecycle`, :mod:`knowledge.confidence`

The :class:`SecondBrain` facade wires the components together from a single
:class:`~knowledge.config.Settings` snapshot. Importing this package does not
require any database driver to be installed; drivers are imported lazily when
a backend is first used.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from .config import Settings, configure_logging, load_settings
from .confidence import ConfidenceEngine
from .document_store import DocumentStore
from .graph_store import GraphStore
from .ingestion import (
    EmbeddingProvider,
    IngestionPipeline,
    IngestionResult,
    build_embedding_provider,
)
from .memory_lifecycle import LifecycleReport, MemoryLifecycleManager
from .memory_store import (
    InMemoryDocumentStore,
    InMemoryProvenanceTracker,
    InMemoryVectorStore,
)
from .models import (
    Document,
    InjectionPayload,
    MemoryNode,
    ProvenanceRecord,
    Relationship,
)
from .provenance import ProvenanceTracker
from .reasoning_engine import ReasoningEngine, ReasoningResult
from .retrieval_orchestrator import RetrievalOrchestrator
from .vector_store import PostgresClient, VectorStore

logger = logging.getLogger(__name__)

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "Settings",
    "load_settings",
    "configure_logging",
    "Document",
    "MemoryNode",
    "Relationship",
    "ProvenanceRecord",
    "InjectionPayload",
    "PostgresClient",
    "VectorStore",
    "GraphStore",
    "DocumentStore",
    "ProvenanceTracker",
    "EmbeddingProvider",
    "build_embedding_provider",
    "IngestionPipeline",
    "IngestionResult",
    "RetrievalOrchestrator",
    "ReasoningEngine",
    "ReasoningResult",
    "ConfidenceEngine",
    "MemoryLifecycleManager",
    "LifecycleReport",
    "SecondBrain",
]


class SecondBrain:
    """High-level facade wiring all five layers from a :class:`Settings`.

    Example
    -------
    >>> from knowledge import SecondBrain, load_settings
    >>> brain = SecondBrain(load_settings())          # doctest: +SKIP
    >>> brain.ingest_text("Ada Lovelace wrote the first algorithm.", "bio")  # doctest: +SKIP
    >>> payload = brain.retrieve("Who wrote the first algorithm?")           # doctest: +SKIP
    >>> print(payload.to_prompt())                                           # doctest: +SKIP
    """

    def __init__(self, settings: Optional[Settings] = None, *, enable_graph: bool = True) -> None:
        self.settings = settings or load_settings()
        self.embedding_provider = build_embedding_provider(self.settings.embedding)
        # Backend selection. ``memory`` runs the full ingest→retrieve path with no
        # external infrastructure (Postgres/Neo4j) — local-first default, tests,
        # demos. ``postgres`` is the durable, production backend (unchanged).
        self.postgres: Optional[PostgresClient] = None
        if self.settings.backend == "memory":
            self.vector_store: Any = InMemoryVectorStore(self.settings)
            self.document_store: Any = InMemoryDocumentStore()
            self.provenance: Any = InMemoryProvenanceTracker()
        else:
            self.postgres = PostgresClient(self.settings.postgres)
            self.vector_store = VectorStore(self.postgres, self.settings)
            self.document_store = DocumentStore(self.postgres)
            self.provenance = ProvenanceTracker(self.postgres)
        self.graph_store: Optional[GraphStore] = (
            GraphStore(self.settings.neo4j) if enable_graph else None
        )
        self.confidence = ConfidenceEngine(self.settings.lifecycle)
        self.ingestion = IngestionPipeline(
            vector_store=self.vector_store,
            document_store=self.document_store,
            provenance=self.provenance,
            embedding_provider=self.embedding_provider,
            settings=self.settings,
            graph_store=self.graph_store,
            confidence_engine=self.confidence,
        )
        self.orchestrator = RetrievalOrchestrator(
            self.vector_store,
            embedding_provider=self.embedding_provider,
            settings=self.settings,
            graph_store=self.graph_store,
        )
        self.reasoning = ReasoningEngine(
            settings=self.settings, graph_store=self.graph_store
        )
        self.lifecycle = MemoryLifecycleManager(
            self.vector_store,
            settings=self.settings,
            confidence_engine=self.confidence,
            graph_store=self.graph_store,
            embedding_provider=self.embedding_provider,
            provenance=self.provenance,
        )

    # -- thin convenience delegations ------------------------------------- #
    def ingest(self, document: Document) -> IngestionResult:
        return self.ingestion.ingest(document)

    def ingest_text(
        self,
        content: str,
        source_id: str,
        *,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        return self.ingestion.ingest_text(
            content, source_id, title=title, metadata=metadata
        )

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
        return self.orchestrator.retrieve(
            query,
            top_k=top_k,
            token_budget=token_budget,
            hops=hops,
            use_keyword_fallback=use_keyword_fallback,
            min_confidence=min_confidence,
        )

    def reason(
        self,
        nodes: Sequence[MemoryNode],
        *,
        seeds: Optional[Sequence[str]] = None,
        max_hops: Optional[int] = None,
    ) -> ReasoningResult:
        return self.reasoning.reason(nodes, seeds=seeds, max_hops=max_hops)

    def retrieve_and_reason(
        self,
        query: str,
        *,
        top_k: Optional[int] = None,
        token_budget: Optional[int] = None,
        hops: Optional[int] = None,
        use_keyword_fallback: Optional[bool] = None,
        min_confidence: float = 0.0,
    ) -> ReasoningResult:
        """Retrieve context for ``query`` then reason over the retrieved nodes."""
        payload = self.retrieve(
            query,
            top_k=top_k,
            token_budget=token_budget,
            hops=hops,
            use_keyword_fallback=use_keyword_fallback,
            min_confidence=min_confidence,
        )
        node_ids = [block.node_id for block in payload.blocks]
        nodes: List[MemoryNode] = self.vector_store.get_many(node_ids)
        return self.reason(nodes)

    def maintain(self, *, refresh: bool = False) -> LifecycleReport:
        return self.lifecycle.run_maintenance(refresh=refresh)

    def ensure_graph_schema(self) -> None:
        if self.graph_store is not None:
            self.graph_store.ensure_constraints()

    def close(self) -> None:
        """Release database resources (no-op for the in-memory backend)."""
        if self.postgres is not None:
            self.postgres.close()
        if self.graph_store is not None:
            self.graph_store.close()
