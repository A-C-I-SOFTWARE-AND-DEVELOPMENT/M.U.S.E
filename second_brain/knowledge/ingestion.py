"""Ingestion & representation pipeline (Layer 1).

Turns a raw :class:`~knowledge.models.Document` into governed
:class:`~knowledge.models.MemoryNode` objects through:

#. semantic chunking,
#. metadata extraction,
#. entity extraction,
#. relationship mapping,
#. embedding generation (pluggable provider abstraction),
#. provenance tagging,

and persists the results to the vector store, graph store, and provenance log.

The default embedding/extraction components are pure standard library so the
pipeline runs offline and deterministically; richer providers
(sentence-transformers, OpenAI, spaCy) are available behind lazy imports.
"""

from __future__ import annotations

import abc
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional, Sequence

from .config import EmbeddingConfig, Settings
from .confidence import ConfidenceEngine
from .models import (
    Document,
    MemoryNode,
    ProvenanceRecord,
    Relationship,
    estimate_tokens,
    new_id,
    tokenize_words,
    utcnow,
)

logger = logging.getLogger(__name__)

__all__ = [
    "EmbeddingProvider",
    "HashingEmbeddingProvider",
    "SentenceTransformerEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "build_embedding_provider",
    "SemanticChunker",
    "EntityExtractor",
    "RegexEntityExtractor",
    "RelationshipExtractor",
    "MetadataExtractor",
    "IngestionResult",
    "IngestionPipeline",
]

_STOPWORDS = frozenset(
    """
    a an the and or but if then else for to of in on at by with from into over under
    is are was were be been being this that these those it its as not no yes do does did
    has have had will would can could should may might must i you he she we they them us
    me my your our their his her about above after again against all am any because before
    below between both during each few more most other own same so some such than too very
    """.split()
)

# Tokens that are usually just sentence starters, not entities.
_GENERIC_STARTERS = frozenset(
    {"The", "This", "That", "These", "Those", "It", "We", "They", "I", "A", "An",
     "He", "She", "There", "Here", "However", "Therefore", "Thus", "Then", "When",
     "While", "If", "As", "In", "On", "At", "But", "And", "Or", "So"}
)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_PROPER_NOUN_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,4})\b")
_ACRONYM_RE = re.compile(r"\b([A-Z]{2,6})\b")
_VERB_HINT_RE = re.compile(r"\b([a-z]+(?:s|ed|es|ing)?)\b")


# --------------------------------------------------------------------------- #
# Embedding providers
# --------------------------------------------------------------------------- #
class EmbeddingProvider(abc.ABC):
    """Abstract embedding provider returning unit-comparable float vectors."""

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Return the fixed embedding dimension."""

    @abc.abstractmethod
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed a batch of texts."""

    def embed_one(self, text: str) -> List[float]:
        """Embed a single text (convenience wrapper)."""
        return self.embed([text])[0]


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic, dependency-free hashing embedding (feature hashing).

    Maps tokens into a fixed-dimension space using SHA-1 bucketing with signed
    contributions, then L2-normalises. Useful for offline runs, CI, and tests
    where similarity must be reproducible without a model download.
    """

    def __init__(self, dimension: int = 1536) -> None:
        if dimension <= 0:
            raise ValueError("embedding dimension must be positive")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> List[float]:
        vec = [0.0] * self._dimension
        for token in tokenize_words(text):
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:8], "big") % self._dimension
            sign = 1.0 if digest[8] & 1 else -1.0
            vec[idx] += sign
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0.0:
            vec = [x / norm for x in vec]
        return vec


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by ``sentence-transformers`` (lazy import)."""

    def __init__(self, model: str, dimension: int) -> None:
        self._model_name = model
        self._dimension = dimension
        self._model: Any = None

    @property
    def dimension(self) -> int:
        return self._dimension

    def _ensure_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError(
                    "sentence-transformers is not installed. "
                    "`pip install sentence-transformers`."
                ) from exc
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        model = self._ensure_model()
        vectors = model.encode(list(texts), normalize_embeddings=True)
        return [list(map(float, v)) for v in vectors]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by the OpenAI API (lazy import).

    The API key is read from the ``OPENAI_API_KEY`` environment variable by
    the OpenAI client itself; it is never stored on this object.
    """

    def __init__(self, model: str, dimension: int) -> None:
        self._model_name = model
        self._dimension = dimension
        self._client: Any = None

    @property
    def dimension(self) -> int:
        return self._dimension

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI  # type: ignore import-not-found
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError(
                    "openai is not installed. `pip install openai`."
                ) from exc
            self._client = OpenAI()
        return self._client

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        client = self._ensure_client()
        response = client.embeddings.create(model=self._model_name, input=list(texts))
        return [list(map(float, item.embedding)) for item in response.data]


def build_embedding_provider(config: EmbeddingConfig) -> EmbeddingProvider:
    """Factory selecting an embedding provider from configuration."""
    provider = config.provider.lower()
    if provider in ("hashing", "hash", "local"):
        return HashingEmbeddingProvider(dimension=config.dimension)
    if provider in ("sentence-transformers", "sbert", "st"):
        return SentenceTransformerEmbeddingProvider(config.model, config.dimension)
    if provider in ("openai",):
        return OpenAIEmbeddingProvider(config.model, config.dimension)
    raise ValueError(f"unknown embedding provider: {config.provider!r}")


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #
class SemanticChunker:
    """Sentence-aware chunker that respects paragraph boundaries.

    Greedily packs whole sentences up to ``target_tokens`` with a sliding
    ``overlap_tokens`` window between adjacent chunks to preserve local
    context across boundaries.
    """

    def __init__(
        self,
        target_tokens: int = 320,
        overlap_tokens: int = 64,
        min_chunk_tokens: int = 32,
    ) -> None:
        self._target = max(16, target_tokens)
        self._overlap = max(0, min(overlap_tokens, self._target - 1))
        self._min = max(1, min_chunk_tokens)

    def chunk(self, text: str) -> List[str]:
        """Split ``text`` into a list of semantically coherent chunks."""
        text = (text or "").strip()
        if not text:
            return []
        sentences = self._split_sentences(text)
        chunks: List[str] = []
        current: List[str] = []
        current_tokens = 0
        for sentence in sentences:
            sent_tokens = estimate_tokens(sentence)
            if current and current_tokens + sent_tokens > self._target:
                chunks.append(" ".join(current).strip())
                current, current_tokens = self._carry_overlap(current)
            current.append(sentence)
            current_tokens += sent_tokens
        if current:
            tail = " ".join(current).strip()
            if chunks and estimate_tokens(tail) < self._min:
                chunks[-1] = (chunks[-1] + " " + tail).strip()
            elif tail:
                chunks.append(tail)
        return chunks

    def _carry_overlap(self, sentences: List[str]) -> tuple[List[str], int]:
        if self._overlap <= 0:
            return [], 0
        carried: List[str] = []
        tokens = 0
        for sentence in reversed(sentences):
            sent_tokens = estimate_tokens(sentence)
            if tokens + sent_tokens > self._overlap and carried:
                break
            carried.insert(0, sentence)
            tokens += sent_tokens
        return carried, tokens

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        sentences: List[str] = []
        for paragraph in re.split(r"\n\s*\n", text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            parts = _SENTENCE_RE.split(paragraph)
            sentences.extend(p.strip() for p in parts if p.strip())
        return sentences


# --------------------------------------------------------------------------- #
# Entity / relationship / metadata extraction
# --------------------------------------------------------------------------- #
class EntityExtractor(abc.ABC):
    """Abstract entity extractor."""

    @abc.abstractmethod
    def extract(self, text: str) -> List[str]:
        """Return a list of distinct entity surface forms."""


class RegexEntityExtractor(EntityExtractor):
    """Heuristic proper-noun + acronym entity extractor (no ML dependency)."""

    def __init__(self, max_entities: int = 32) -> None:
        self._max = max_entities

    def extract(self, text: str) -> List[str]:
        if not text:
            return []
        seen: Dict[str, str] = {}
        for match in _PROPER_NOUN_RE.finditer(text):
            phrase = match.group(1).strip()
            words = phrase.split()
            if len(words) == 1 and words[0] in _GENERIC_STARTERS:
                continue
            key = phrase.lower()
            if key not in seen and key not in _STOPWORDS:
                seen[key] = phrase
        for match in _ACRONYM_RE.finditer(text):
            acronym = match.group(1)
            key = acronym.lower()
            if key not in seen:
                seen[key] = acronym
        return list(seen.values())[: self._max]


class RelationshipExtractor:
    """Co-occurrence + lightweight subject-verb-object relationship mapper."""

    def __init__(self, max_relationships: int = 64) -> None:
        self._max = max_relationships

    def extract(self, text: str, entities: Sequence[str]) -> List[Relationship]:
        if not text or len(entities) < 2:
            return []
        relationships: List[Relationship] = []
        seen: set[tuple[str, str, str]] = set()
        lower_text = text
        for sentence in SemanticChunker._split_sentences(lower_text):
            present = self._entities_in_sentence(sentence, entities)
            if len(present) < 2:
                continue
            predicate = self._guess_predicate(sentence, present[0], present[1])
            for i in range(len(present)):
                for j in range(i + 1, len(present)):
                    subj, obj = present[i], present[j]
                    pred = predicate if (i, j) == (0, 1) else "co_occurs_with"
                    key = (subj.lower(), pred, obj.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    confidence = 0.6 if pred != "co_occurs_with" else 0.5
                    relationships.append(
                        Relationship(subject=subj, predicate=pred, object=obj,
                                     confidence=confidence)
                    )
                    if len(relationships) >= self._max:
                        return relationships
        return relationships

    @staticmethod
    def _entities_in_sentence(sentence: str, entities: Sequence[str]) -> List[str]:
        present: List[str] = []
        lowered = sentence.lower()
        for entity in entities:
            if entity.lower() in lowered and entity not in present:
                present.append(entity)
        return present

    @staticmethod
    def _guess_predicate(sentence: str, subject: str, obj: str) -> str:
        lowered = sentence.lower()
        start = lowered.find(subject.lower())
        end = lowered.find(obj.lower())
        if start == -1 or end == -1 or end <= start:
            return "related_to"
        between = lowered[start + len(subject):end]
        verbs = [
            v for v in _VERB_HINT_RE.findall(between)
            if v not in _STOPWORDS and len(v) > 2
        ]
        return verbs[0] if verbs else "related_to"


class MetadataExtractor:
    """Derive lightweight, structured metadata from a chunk."""

    def extract(self, text: str) -> Dict[str, Any]:
        tokens = tokenize_words(text)
        freq: Dict[str, int] = {}
        for token in tokens:
            if token in _STOPWORDS or len(token) < 3:
                continue
            freq[token] = freq.get(token, 0) + 1
        top_terms = [
            term for term, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:8]
        ]
        return {
            "char_len": len(text),
            "word_count": len(tokens),
            "est_tokens": estimate_tokens(text),
            "top_terms": top_terms,
            "has_numbers": bool(re.search(r"\d", text)),
            "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class IngestionResult:
    """Summary of an ingestion run."""

    document_id: str
    node_ids: List[str] = field(default_factory=list)
    chunks: int = 0
    entities: int = 0
    relationships: int = 0
    skipped_duplicate: bool = False


class IngestionPipeline:
    """Orchestrates the Layer 1 ingestion flow with injected components."""

    def __init__(
        self,
        *,
        vector_store: Any,
        document_store: Any,
        provenance: Any,
        embedding_provider: EmbeddingProvider,
        settings: Settings,
        graph_store: Optional[Any] = None,
        entity_extractor: Optional[EntityExtractor] = None,
        relationship_extractor: Optional[RelationshipExtractor] = None,
        metadata_extractor: Optional[MetadataExtractor] = None,
        chunker: Optional[SemanticChunker] = None,
        confidence_engine: Optional[ConfidenceEngine] = None,
    ) -> None:
        self._vector_store = vector_store
        self._document_store = document_store
        self._provenance = provenance
        self._embeddings = embedding_provider
        self._settings = settings
        self._graph_store = graph_store
        self._entities = entity_extractor or RegexEntityExtractor(
            max_entities=settings.chunking.max_entities_per_chunk
        )
        self._relationships = relationship_extractor or RelationshipExtractor()
        self._metadata = metadata_extractor or MetadataExtractor()
        self._chunker = chunker or SemanticChunker(
            target_tokens=settings.chunking.target_tokens,
            overlap_tokens=settings.chunking.overlap_tokens,
            min_chunk_tokens=settings.chunking.min_chunk_tokens,
        )
        self._confidence = confidence_engine or ConfidenceEngine(settings.lifecycle)

    def ingest_text(
        self,
        content: str,
        source_id: str,
        *,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Convenience wrapper that builds and ingests a :class:`Document`."""
        document = Document(
            content=content,
            source_id=source_id,
            title=title,
            metadata=metadata or {},
        )
        return self.ingest(document)

    def ingest(self, document: Document, *, skip_duplicates: bool = True) -> IngestionResult:
        """Ingest a document end-to-end and persist all derived nodes."""
        if skip_duplicates and self._document_store.exists(document.content_hash):
            existing = self._document_store.find_by_hash(document.content_hash)
            logger.info("Skipping duplicate document hash=%s", document.content_hash)
            return IngestionResult(
                document_id=existing.id if existing else document.id,
                skipped_duplicate=True,
            )

        document_id = self._document_store.save(document)
        chunks = self._chunker.chunk(document.content)
        logger.info("Ingesting document=%s source=%s chunks=%d",
                    document_id, document.source_id, len(chunks))

        ttl_days = self._settings.lifecycle.default_ttl_days
        ttl_expires = utcnow() + timedelta(days=ttl_days) if ttl_days > 0 else None
        source_trust = float(document.metadata.get("trust", 0.6))

        node_ids: List[str] = []
        total_entities = 0
        total_relationships = 0
        nodes_to_persist: List[MemoryNode] = []
        graph_payload: List[tuple[MemoryNode, List[Relationship]]] = []

        embeddings = self._embeddings.embed(chunks) if chunks else []
        for index, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            entities = self._entities.extract(chunk_text)
            relationships = self._relationships.extract(chunk_text, entities)
            meta = self._metadata.extract(chunk_text)
            meta.update({
                "chunk_index": index,
                "document_id": document_id,
                "source_id": document.source_id,
                "title": document.title,
            })
            extraction_quality = self._extraction_quality(entities, meta["est_tokens"])
            confidence = self._confidence.initial_confidence(
                source_trust=source_trust,
                extraction_quality=extraction_quality,
                content_tokens=int(meta["est_tokens"]),
            )
            node = MemoryNode(
                id=new_id(),
                content=chunk_text,
                embedding=embedding,
                entities=entities,
                relationships=[r.encode() for r in relationships],
                source_id=document.source_id,
                confidence_score=confidence,
                version=1,
                ttl_expires_at=ttl_expires,
                document_id=document_id,
                content_hash=meta["content_hash"],
                metadata=meta,
            )
            nodes_to_persist.append(node)
            graph_payload.append((node, relationships))
            node_ids.append(node.id)
            total_entities += len(entities)
            total_relationships += len(relationships)

        if nodes_to_persist:
            self._vector_store.upsert_many(nodes_to_persist)
            self._persist_graph(graph_payload)
            self._persist_provenance(nodes_to_persist, document)

        return IngestionResult(
            document_id=document_id,
            node_ids=node_ids,
            chunks=len(chunks),
            entities=total_entities,
            relationships=total_relationships,
        )

    # -- helpers ----------------------------------------------------------- #
    @staticmethod
    def _extraction_quality(entities: Sequence[str], est_tokens: int) -> float:
        entity_signal = min(1.0, len(entities) / 5.0)
        length_signal = min(1.0, est_tokens / 200.0)
        return 0.6 * entity_signal + 0.4 * length_signal

    def _persist_graph(
        self, payload: Sequence[tuple[MemoryNode, List[Relationship]]]
    ) -> None:
        if self._graph_store is None:
            return
        for node, relationships in payload:
            try:
                self._graph_store.upsert_node(node, relationships)
            except Exception:  # pragma: no cover - graph is best-effort
                logger.exception("Graph upsert failed for node=%s", node.id)

    def _persist_provenance(
        self, nodes: Sequence[MemoryNode], document: Document
    ) -> None:
        source_type = str(document.metadata.get("source_type", "document"))
        source_uri = document.metadata.get("source_uri")
        for node in nodes:
            record = ProvenanceRecord(
                node_id=node.id,
                source_id=document.source_id,
                source_type=source_type,
                source_uri=source_uri,
                transformation="semantic_chunk;entity_extract;relationship_map;embed",
                content_hash=node.content_hash,
                metadata={"document_id": document.id},
            )
            try:
                self._provenance.record(record)
            except Exception:  # pragma: no cover - provenance is best-effort
                logger.exception("Provenance record failed for node=%s", node.id)
