"""Repository-safe configuration for the Second Brain module.

All credentials and tunables are read from environment variables. Nothing is
hardcoded. Call :func:`load_settings` to obtain an immutable :class:`Settings`
snapshot; pass it explicitly into stores and orchestrators (no global state).

Environment variables are documented in ``.env.example``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

__all__ = [
    "PostgresConfig",
    "Neo4jConfig",
    "EmbeddingConfig",
    "ChunkingConfig",
    "RetrievalConfig",
    "LifecycleConfig",
    "Settings",
    "load_settings",
    "configure_logging",
]


def _env_str(key: str, default: str) -> str:
    value = os.environ.get(key)
    return value if value is not None and value != "" else default


def _env_opt(key: str) -> Optional[str]:
    value = os.environ.get(key)
    return value if value else None


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid int for %s=%r; using default %d", key, raw, default)
        return default


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r; using default %s", key, raw, default)
        return default


@dataclass(frozen=True, slots=True)
class PostgresConfig:
    """Connection settings for Postgres + pgvector."""

    host: str = "localhost"
    port: int = 5432
    database: str = "second_brain"
    user: str = "second_brain"
    password: str = ""
    sslmode: str = "prefer"
    min_connections: int = 1
    max_connections: int = 8

    @property
    def dsn(self) -> str:
        """Return a libpq DSN. Password is included only if provided."""
        parts = [
            f"host={self.host}",
            f"port={self.port}",
            f"dbname={self.database}",
            f"user={self.user}",
            f"sslmode={self.sslmode}",
        ]
        if self.password:
            parts.append(f"password={self.password}")
        return " ".join(parts)


@dataclass(frozen=True, slots=True)
class Neo4jConfig:
    """Connection settings for the Neo4j graph store."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    max_connection_pool_size: int = 16


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    """Embedding provider configuration.

    ``dimension`` MUST match the ``vector(N)`` column declared in
    ``migrations/001_init.sql``. The default (1536) matches common hosted
    embedding models; change both together if you swap providers.
    """

    provider: str = "hashing"
    model: str = "deterministic-hash-v1"
    dimension: int = 1536
    batch_size: int = 64


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    """Semantic chunking parameters (Layer 1)."""

    target_tokens: int = 320
    overlap_tokens: int = 64
    min_chunk_tokens: int = 32
    max_entities_per_chunk: int = 32


@dataclass(frozen=True, slots=True)
class RetrievalConfig:
    """Hybrid retrieval + ranking parameters (Layer 3)."""

    top_k: int = 8
    graph_hops: int = 2
    graph_expansion_limit: int = 32
    token_budget: int = 4096
    weight_similarity: float = 0.5
    weight_confidence: float = 0.3
    weight_recency: float = 0.2
    recency_half_life_days: float = 30.0
    enable_keyword_fallback: bool = True
    keyword_fallback_threshold: int = 3


@dataclass(frozen=True, slots=True)
class LifecycleConfig:
    """Governance & lifecycle parameters (Layer 5)."""

    default_ttl_days: float = 180.0
    confidence_half_life_days: float = 90.0
    confidence_floor: float = 0.05
    confidence_ceiling: float = 0.97
    reinforcement_boost: float = 0.05
    reinforcement_ttl_extension_days: float = 30.0
    consolidation_similarity_threshold: float = 0.95
    refresh_interval_days: float = 30.0
    expiry_confidence_floor: float = 0.1


@dataclass(frozen=True, slots=True)
class Settings:
    """Top-level immutable settings snapshot."""

    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    lifecycle: LifecycleConfig = field(default_factory=LifecycleConfig)
    log_level: str = "INFO"
    #: Storage backend: ``"postgres"`` (default, durable) or ``"memory"``
    #: (zero-infrastructure, process-local — for local-first use, tests, demos).
    backend: str = "postgres"


def load_settings() -> Settings:
    """Build a :class:`Settings` snapshot from the current environment.

    This function is pure with respect to process state: it reads ``os.environ``
    and returns a fresh frozen object. It never mutates global state and never
    raises on missing optional values (sensible defaults are used).
    """
    postgres = PostgresConfig(
        host=_env_str("SECOND_BRAIN_PG_HOST", "localhost"),
        port=_env_int("SECOND_BRAIN_PG_PORT", 5432),
        database=_env_str("SECOND_BRAIN_PG_DB", "second_brain"),
        user=_env_str("SECOND_BRAIN_PG_USER", "second_brain"),
        password=_env_str("SECOND_BRAIN_PG_PASSWORD", ""),
        sslmode=_env_str("SECOND_BRAIN_PG_SSLMODE", "prefer"),
        min_connections=_env_int("SECOND_BRAIN_PG_MIN_CONN", 1),
        max_connections=_env_int("SECOND_BRAIN_PG_MAX_CONN", 8),
    )
    neo4j = Neo4jConfig(
        uri=_env_str("SECOND_BRAIN_NEO4J_URI", "bolt://localhost:7687"),
        user=_env_str("SECOND_BRAIN_NEO4J_USER", "neo4j"),
        password=_env_str("SECOND_BRAIN_NEO4J_PASSWORD", ""),
        database=_env_str("SECOND_BRAIN_NEO4J_DB", "neo4j"),
        max_connection_pool_size=_env_int("SECOND_BRAIN_NEO4J_POOL", 16),
    )
    embedding = EmbeddingConfig(
        provider=_env_str("SECOND_BRAIN_EMBEDDING_PROVIDER", "hashing"),
        model=_env_str("SECOND_BRAIN_EMBEDDING_MODEL", "deterministic-hash-v1"),
        dimension=_env_int("SECOND_BRAIN_EMBEDDING_DIM", 1536),
        batch_size=_env_int("SECOND_BRAIN_EMBEDDING_BATCH", 64),
    )
    chunking = ChunkingConfig(
        target_tokens=_env_int("SECOND_BRAIN_CHUNK_TARGET", 320),
        overlap_tokens=_env_int("SECOND_BRAIN_CHUNK_OVERLAP", 64),
        min_chunk_tokens=_env_int("SECOND_BRAIN_CHUNK_MIN", 32),
        max_entities_per_chunk=_env_int("SECOND_BRAIN_CHUNK_MAX_ENTITIES", 32),
    )
    retrieval = RetrievalConfig(
        top_k=_env_int("SECOND_BRAIN_TOP_K", 8),
        graph_hops=_env_int("SECOND_BRAIN_GRAPH_HOPS", 2),
        graph_expansion_limit=_env_int("SECOND_BRAIN_GRAPH_LIMIT", 32),
        token_budget=_env_int("SECOND_BRAIN_TOKEN_BUDGET", 4096),
        weight_similarity=_env_float("SECOND_BRAIN_W_SIMILARITY", 0.5),
        weight_confidence=_env_float("SECOND_BRAIN_W_CONFIDENCE", 0.3),
        weight_recency=_env_float("SECOND_BRAIN_W_RECENCY", 0.2),
        recency_half_life_days=_env_float("SECOND_BRAIN_RECENCY_HALFLIFE", 30.0),
        enable_keyword_fallback=_env_str("SECOND_BRAIN_KEYWORD_FALLBACK", "1")
        not in ("0", "false", "False", "no"),
        keyword_fallback_threshold=_env_int("SECOND_BRAIN_KEYWORD_THRESHOLD", 3),
    )
    lifecycle = LifecycleConfig(
        default_ttl_days=_env_float("SECOND_BRAIN_TTL_DAYS", 180.0),
        confidence_half_life_days=_env_float("SECOND_BRAIN_CONF_HALFLIFE", 90.0),
        confidence_floor=_env_float("SECOND_BRAIN_CONF_FLOOR", 0.05),
        confidence_ceiling=_env_float("SECOND_BRAIN_CONF_CEILING", 0.97),
        reinforcement_boost=_env_float("SECOND_BRAIN_REINFORCE_BOOST", 0.05),
        reinforcement_ttl_extension_days=_env_float("SECOND_BRAIN_REINFORCE_TTL", 30.0),
        consolidation_similarity_threshold=_env_float("SECOND_BRAIN_CONSOLIDATE_SIM", 0.95),
        refresh_interval_days=_env_float("SECOND_BRAIN_REFRESH_DAYS", 30.0),
        expiry_confidence_floor=_env_float("SECOND_BRAIN_EXPIRY_FLOOR", 0.1),
    )
    return Settings(
        postgres=postgres,
        neo4j=neo4j,
        embedding=embedding,
        chunking=chunking,
        retrieval=retrieval,
        lifecycle=lifecycle,
        log_level=_env_str("SECOND_BRAIN_LOG_LEVEL", "INFO"),
        backend=_env_str("SECOND_BRAIN_BACKEND", "postgres").strip().lower(),
    )


def configure_logging(level: Optional[str] = None) -> None:
    """Configure root logging for standalone / CLI use.

    Libraries should not configure logging on import; call this only from an
    application entry point. ``level`` falls back to ``SECOND_BRAIN_LOG_LEVEL``.
    """
    resolved = (level or os.environ.get("SECOND_BRAIN_LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, resolved, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
