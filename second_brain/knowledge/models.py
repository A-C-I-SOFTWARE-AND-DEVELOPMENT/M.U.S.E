"""Core data models and pure helpers for the Second Brain knowledge layer.

This module is intentionally dependency-free (standard library only) so that
the data contracts, ranking primitives, and math helpers can be imported and
exercised without any database driver, embedding model, or third-party
package installed. Heavy backends (Postgres, Neo4j) live in their own modules
and import their drivers lazily.

The :class:`MemoryNode` schema is the canonical unit of knowledge in the
system (Layer 1 — Ingestion & Representation).
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Protocol,
    Sequence,
    runtime_checkable,
)

__all__ = [
    "utcnow",
    "new_id",
    "estimate_tokens",
    "cosine_similarity",
    "RetrievalSource",
    "ConflictType",
    "Document",
    "Chunk",
    "Entity",
    "Relationship",
    "MemoryNode",
    "ProvenanceRecord",
    "RetrievalResult",
    "ContextBlock",
    "InjectionPayload",
    "SupportsVectorSearch",
    "SupportsGraphExpansion",
    "SupportsKeywordSearch",
    "SupportsGraphDelete",
    "SupportsProvenanceRecord",
    "LifecycleVectorStore",
    "GraphNeighbor",
]


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #
def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def new_id() -> str:
    """Return a fresh random UUID4 as a string."""
    return str(uuid.uuid4())


def estimate_tokens(text: str) -> int:
    """Estimate the token count of ``text``.

    Uses the widely-cited ~4-characters-per-token heuristic for English text.
    This avoids a hard dependency on a specific tokenizer while remaining
    stable enough for token-budget accounting.
    """
    if not text:
        return 0
    return max(1, round(len(text) / 4))


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Compute cosine similarity between two equal-length vectors.

    Returns a value in ``[-1.0, 1.0]``. Returns ``0.0`` when either vector is
    empty or has zero magnitude. Raises :class:`ValueError` on dimension
    mismatch so corrupt data fails loudly instead of silently mis-ranking.
    """
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        raise ValueError(f"vector dimension mismatch: {len(a)} != {len(b)}")
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class RetrievalSource(str, Enum):
    """Provenance of a retrieved candidate within the hybrid orchestrator."""

    VECTOR = "vector"
    GRAPH = "graph"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class ConflictType(str, Enum):
    """Categories of contradictions detected by the reasoning engine."""

    CONTRADICTION = "contradiction"
    VALUE_MISMATCH = "value_mismatch"
    NEGATION = "negation"
    TEMPORAL = "temporal"


# --------------------------------------------------------------------------- #
# Ingestion / representation models
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class Document:
    """A raw source document prior to chunking (Layer 1 input)."""

    content: str
    source_id: str
    id: str = field(default_factory=new_id)
    title: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if self.content_hash is None:
            self.content_hash = sha256_hex(self.content)


@dataclass(slots=True)
class Chunk:
    """A semantically coherent slice of a :class:`Document`."""

    content: str
    index: int
    source_id: str
    document_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Entity:
    """A named entity extracted from text."""

    name: str
    label: str = "ENTITY"
    salience: float = 1.0


@dataclass(slots=True)
class Relationship:
    """A directed, typed relationship between two entities.

    Serialized to the ``MemoryNode.relationships`` list as a stable
    ``subject|predicate|object`` triple string.
    """

    subject: str
    predicate: str
    object: str
    confidence: float = 0.5

    _SEP = "|"

    def encode(self) -> str:
        """Encode the triple as ``subject|predicate|object``."""
        return self._SEP.join(
            part.replace(self._SEP, "/") for part in (self.subject, self.predicate, self.object)
        )

    @classmethod
    def decode(cls, raw: str, confidence: float = 0.5) -> "Relationship":
        """Decode a ``subject|predicate|object`` triple string."""
        parts = raw.split(cls._SEP)
        if len(parts) != 3:
            raise ValueError(f"malformed relationship triple: {raw!r}")
        subject, predicate, obj = (p.strip() for p in parts)
        return cls(subject=subject, predicate=predicate, object=obj, confidence=confidence)


@dataclass(slots=True)
class MemoryNode:
    """The canonical unit of governed knowledge.

    The first nine fields are the schema mandated by the architecture spec.
    The remaining fields carry governance/lifecycle state (Layer 5) and all
    have safe defaults so the core schema stays minimal.
    """

    content: str
    embedding: List[float]
    entities: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    source_id: str = ""
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    confidence_score: float = 0.5
    version: int = 1

    # Governance / lifecycle state.
    updated_at: datetime = field(default_factory=utcnow)
    last_accessed_at: Optional[datetime] = None
    reinforcement_count: int = 0
    ttl_expires_at: Optional[datetime] = None
    document_id: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.content_hash is None:
            self.content_hash = sha256_hex(self.content)

    # -- convenience views ------------------------------------------------- #
    def decoded_relationships(self) -> List[Relationship]:
        """Return relationships parsed back into :class:`Relationship` objects."""
        decoded: List[Relationship] = []
        for raw in self.relationships:
            try:
                decoded.append(Relationship.decode(raw, confidence=self.confidence_score))
            except ValueError:
                continue
        return decoded

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dictionary (embedding included)."""
        return {
            "id": self.id,
            "content": self.content,
            "embedding": list(self.embedding),
            "entities": list(self.entities),
            "relationships": list(self.relationships),
            "source_id": self.source_id,
            "created_at": self.created_at.isoformat(),
            "confidence_score": self.confidence_score,
            "version": self.version,
            "updated_at": self.updated_at.isoformat(),
            "last_accessed_at": (
                self.last_accessed_at.isoformat() if self.last_accessed_at else None
            ),
            "reinforcement_count": self.reinforcement_count,
            "ttl_expires_at": (
                self.ttl_expires_at.isoformat() if self.ttl_expires_at else None
            ),
            "document_id": self.document_id,
            "content_hash": self.content_hash,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ProvenanceRecord:
    """An immutable record of where a node came from and how (Layer 1/2)."""

    node_id: str
    source_id: str
    source_type: str = "unknown"
    source_uri: Optional[str] = None
    transformation: str = ""
    content_hash: Optional[str] = None
    id: str = field(default_factory=new_id)
    ingested_at: datetime = field(default_factory=utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Retrieval models (Layer 3)
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class RetrievalResult:
    """A candidate node plus its scoring breakdown."""

    node: MemoryNode
    similarity: float
    recency: float = 0.0
    priority_score: float = 0.0
    sources: List[RetrievalSource] = field(default_factory=list)
    graph_distance: Optional[int] = None

    @property
    def confidence(self) -> float:
        return self.node.confidence_score


@dataclass(slots=True)
class ContextBlock:
    """A single, citation-tagged context block in an injection payload."""

    citation: int
    node_id: str
    content: str
    source_id: str
    similarity: float
    confidence: float
    recency: float
    priority_score: float
    retrieval_sources: List[str]
    tokens: int


@dataclass(slots=True)
class InjectionPayload:
    """Context-ready, structured payload returned by the orchestrator."""

    query: str
    blocks: List[ContextBlock] = field(default_factory=list)
    total_tokens: int = 0
    token_budget: int = 0
    truncated: bool = False

    def to_prompt(self) -> str:
        """Render the payload as a prompt-injectable context string."""
        if not self.blocks:
            return "No relevant context was retrieved."
        lines: List[str] = ["# Retrieved context", ""]
        for block in self.blocks:
            lines.append(f"[{block.citation}] (source={block.source_id}, "
                         f"score={block.priority_score:.3f})")
            lines.append(block.content.strip())
            lines.append("")
        lines.append("# Sources")
        for block in self.blocks:
            lines.append(f"[{block.citation}] node={block.node_id} source={block.source_id}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dictionary."""
        return {
            "query": self.query,
            "total_tokens": self.total_tokens,
            "token_budget": self.token_budget,
            "truncated": self.truncated,
            "blocks": [
                {
                    "citation": b.citation,
                    "node_id": b.node_id,
                    "content": b.content,
                    "source_id": b.source_id,
                    "similarity": b.similarity,
                    "confidence": b.confidence,
                    "recency": b.recency,
                    "priority_score": b.priority_score,
                    "retrieval_sources": b.retrieval_sources,
                    "tokens": b.tokens,
                }
                for b in self.blocks
            ],
        }


# --------------------------------------------------------------------------- #
# Storage interfaces (Protocols) for dependency injection
# --------------------------------------------------------------------------- #
@runtime_checkable
class SupportsVectorSearch(Protocol):
    """Minimal interface the orchestrator needs from a vector store."""

    def similarity_search(
        self,
        embedding: Sequence[float],
        top_k: int,
        *,
        min_confidence: float = 0.0,
        include_expired: bool = False,
    ) -> List[RetrievalResult]:
        ...

    def get(self, node_id: str) -> Optional[MemoryNode]:
        ...


@runtime_checkable
class SupportsGraphExpansion(Protocol):
    """Minimal interface the orchestrator needs from a graph store."""

    def expand(
        self, node_ids: Sequence[str], hops: int, limit: int
    ) -> List["GraphNeighbor"]:
        ...


@runtime_checkable
class SupportsKeywordSearch(Protocol):
    """Optional keyword/full-text search interface."""

    def keyword_search(self, query: str, top_k: int) -> List[RetrievalResult]:
        ...


@runtime_checkable
class SupportsGraphDelete(Protocol):
    """Graph store surface used by the lifecycle manager."""

    def delete_node(self, node_id: str) -> None:
        ...


@runtime_checkable
class SupportsProvenanceRecord(Protocol):
    """Provenance tracker surface used by the lifecycle manager."""

    def record(self, record: "ProvenanceRecord") -> str:
        ...


@runtime_checkable
class LifecycleVectorStore(Protocol):
    """Vector-store surface required by the governance/lifecycle layer."""

    def get(self, node_id: str) -> Optional["MemoryNode"]:
        ...

    def upsert_node(self, node: "MemoryNode") -> None:
        ...

    def iter_all(self, *, batch_size: int = ...) -> Iterator["MemoryNode"]:
        ...

    def update_confidence(self, node_id: str, confidence: float) -> None:
        ...

    def update_embedding(self, node_id: str, embedding: Sequence[float]) -> None:
        ...

    def increment_reinforcement(
        self, node_id: str, *, confidence: float, ttl_until: Optional[datetime]
    ) -> None:
        ...

    def record_version(self, node: "MemoryNode", *, reason: str) -> None:
        ...

    def delete(self, node_id: str) -> None:
        ...

    def expired_node_ids(self, *, confidence_floor: float) -> List[str]:
        ...


@dataclass(slots=True)
class GraphNeighbor:
    """A node reachable from a seed via graph traversal."""

    node_id: str
    distance: int
    path_entities: List[str] = field(default_factory=list)


# Imported here (not at top) only to avoid a circular import of the hashing
# helper used by Document/MemoryNode defaults.
def sha256_hex(text: str) -> str:
    """Return the hex SHA-256 digest of ``text`` (UTF-8 encoded)."""
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def tokenize_words(text: str) -> List[str]:
    """Lowercase word tokenizer shared by hashing embeddings and BM25."""
    return _WORD_RE.findall(text.lower())
