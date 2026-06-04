"""Postgres + pgvector backend (Layer 2 — Persistent Storage).

Provides :class:`PostgresClient` (a thread-safe pooled connection manager
shared by all Postgres-backed stores) and :class:`VectorStore` (persistence
and similarity search for :class:`~knowledge.models.MemoryNode`).

The ``psycopg2`` and ``pgvector`` packages are imported lazily so that the
rest of the package — and the evaluation suite — import cleanly on machines
without a database driver installed. Using any method that touches the
database will raise a clear :class:`RuntimeError` if the driver is missing.
"""

from __future__ import annotations

import logging
import weakref
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator, List, Optional, Sequence

from .config import PostgresConfig, Settings
from .models import (
    MemoryNode,
    RetrievalResult,
    RetrievalSource,
    utcnow,
)

logger = logging.getLogger(__name__)

__all__ = ["PostgresClient", "VectorStore"]


# Full column list for memory_nodes, in a stable order shared by reads.
_NODE_COLUMNS = (
    "id, content, embedding, entities, relationships, source_id, created_at, "
    "confidence_score, version, updated_at, last_accessed_at, reinforcement_count, "
    "ttl_expires_at, document_id, content_hash, metadata"
)


class PostgresClient:
    """A lazily-initialised, pooled psycopg2 connection manager.

    Construct once per process and inject into every Postgres-backed store so
    they share a single pool. The pgvector type is registered per physical
    connection exactly once.
    """

    def __init__(self, config: PostgresConfig) -> None:
        self._config = config
        self._pool: Any = None
        self._vector_registered: "weakref.WeakSet[Any]" = weakref.WeakSet()

    def _ensure_pool(self) -> Any:
        if self._pool is not None:
            return self._pool
        try:
            from psycopg2 import pool as pg_pool  # type: ignore import-not-found
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "psycopg2 is required for Postgres access. Install with "
                "`pip install psycopg2-binary pgvector`."
            ) from exc
        logger.debug(
            "Creating Postgres pool host=%s db=%s (min=%d max=%d)",
            self._config.host,
            self._config.database,
            self._config.min_connections,
            self._config.max_connections,
        )
        self._pool = pg_pool.ThreadedConnectionPool(
            self._config.min_connections,
            self._config.max_connections,
            dsn=self._config.dsn,
        )
        return self._pool

    def _register_vector(self, conn: Any) -> None:
        if conn in self._vector_registered:
            return
        try:
            from pgvector.psycopg2 import register_vector  # type: ignore import-not-found

            register_vector(conn)
            self._vector_registered.add(conn)
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "pgvector is required for vector columns. Install with "
                "`pip install pgvector`."
            ) from exc

    @contextmanager
    def connection(self) -> Iterator[Any]:
        """Yield a pooled connection, committing on success and rolling back
        on error, then returning the connection to the pool."""
        pool = self._ensure_pool()
        conn = pool.getconn()
        try:
            self._register_vector(conn)
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.putconn(conn)

    @contextmanager
    def cursor(self) -> Iterator[Any]:
        """Yield a cursor bound to a pooled connection."""
        with self.connection() as conn:
            cur = conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    def close(self) -> None:
        """Close all pooled connections."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None


def _json(value: Any) -> Any:
    """Wrap a dict for JSONB binding using psycopg2's Json adapter."""
    from psycopg2.extras import Json  # type: ignore import-not-found

    return Json(value)


def _vector_literal(embedding: Sequence[float]) -> str:
    """Render an embedding as a pgvector text literal, e.g. ``[0.1,0.2]``.

    Binding a text literal with an explicit ``::vector`` cast in SQL keeps
    inserts/queries correct whether or not a list adapter is registered.
    """
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


def _parse_embedding(value: Any) -> List[float]:
    """Parse a vector column value (numpy array, list, or ``[..]`` string)."""
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip().lstrip("[").rstrip("]")
        if not stripped:
            return []
        return [float(part) for part in stripped.split(",")]
    return [float(x) for x in value]


class VectorStore:
    """Persistence and vector similarity search for memory nodes."""

    def __init__(self, client: PostgresClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._dim = settings.embedding.dimension

    # -- writes ------------------------------------------------------------ #
    def upsert_node(self, node: MemoryNode) -> None:
        """Insert or update a single node by primary key."""
        self.upsert_many([node])

    def upsert_many(self, nodes: Sequence[MemoryNode]) -> None:
        """Insert or update many nodes in one transaction."""
        if not nodes:
            return
        sql = f"""
            INSERT INTO memory_nodes ({_NODE_COLUMNS})
            VALUES (%s, %s, %s::vector, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                entities = EXCLUDED.entities,
                relationships = EXCLUDED.relationships,
                source_id = EXCLUDED.source_id,
                confidence_score = EXCLUDED.confidence_score,
                version = EXCLUDED.version,
                updated_at = EXCLUDED.updated_at,
                last_accessed_at = EXCLUDED.last_accessed_at,
                reinforcement_count = EXCLUDED.reinforcement_count,
                ttl_expires_at = EXCLUDED.ttl_expires_at,
                document_id = EXCLUDED.document_id,
                content_hash = EXCLUDED.content_hash,
                metadata = EXCLUDED.metadata
        """
        rows = [self._node_to_row(node) for node in nodes]
        with self._client.cursor() as cur:
            cur.executemany(sql, rows)
        logger.debug("Upserted %d node(s)", len(rows))

    def update_confidence(self, node_id: str, confidence: float) -> None:
        with self._client.cursor() as cur:
            cur.execute(
                "UPDATE memory_nodes SET confidence_score = %s, updated_at = now() "
                "WHERE id = %s",
                (confidence, node_id),
            )

    def update_embedding(self, node_id: str, embedding: Sequence[float]) -> None:
        with self._client.cursor() as cur:
            cur.execute(
                "UPDATE memory_nodes SET embedding = %s::vector, updated_at = now() "
                "WHERE id = %s",
                (_vector_literal(embedding), node_id),
            )

    def increment_reinforcement(
        self, node_id: str, *, confidence: float, ttl_until: Optional[datetime]
    ) -> None:
        with self._client.cursor() as cur:
            cur.execute(
                "UPDATE memory_nodes SET reinforcement_count = reinforcement_count + 1, "
                "confidence_score = %s, ttl_expires_at = COALESCE(%s, ttl_expires_at), "
                "last_accessed_at = now(), updated_at = now() WHERE id = %s",
                (confidence, ttl_until, node_id),
            )

    def mark_accessed(self, node_id: str) -> None:
        with self._client.cursor() as cur:
            cur.execute(
                "UPDATE memory_nodes SET last_accessed_at = now() WHERE id = %s",
                (node_id,),
            )

    def bump_version(self, node_id: str, *, content: Optional[str] = None) -> int:
        """Increment a node's version, optionally replacing content. Returns new version."""
        with self._client.cursor() as cur:
            if content is None:
                cur.execute(
                    "UPDATE memory_nodes SET version = version + 1, updated_at = now() "
                    "WHERE id = %s RETURNING version",
                    (node_id,),
                )
            else:
                cur.execute(
                    "UPDATE memory_nodes SET version = version + 1, content = %s, "
                    "updated_at = now() WHERE id = %s RETURNING version",
                    (content, node_id),
                )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def record_version(
        self, node: MemoryNode, *, reason: str
    ) -> None:
        """Append an immutable snapshot to ``node_versions`` for audit/rollback."""
        with self._client.cursor() as cur:
            cur.execute(
                "INSERT INTO node_versions (node_id, version, content, confidence_score, "
                "reason) VALUES (%s, %s, %s, %s, %s)",
                (node.id, node.version, node.content, node.confidence_score, reason),
            )

    def delete(self, node_id: str) -> None:
        with self._client.cursor() as cur:
            cur.execute("DELETE FROM memory_nodes WHERE id = %s", (node_id,))

    # -- reads ------------------------------------------------------------- #
    def get(self, node_id: str) -> Optional[MemoryNode]:
        with self._client.cursor() as cur:
            cur.execute(
                f"SELECT {_NODE_COLUMNS} FROM memory_nodes WHERE id = %s",
                (node_id,),
            )
            row = cur.fetchone()
        return self._row_to_node(row) if row else None

    def get_many(self, node_ids: Sequence[str]) -> List[MemoryNode]:
        if not node_ids:
            return []
        with self._client.cursor() as cur:
            cur.execute(
                f"SELECT {_NODE_COLUMNS} FROM memory_nodes WHERE id = ANY(%s)",
                (list(node_ids),),
            )
            rows = cur.fetchall()
        return [self._row_to_node(r) for r in rows]

    def count(self) -> int:
        with self._client.cursor() as cur:
            cur.execute("SELECT count(*) FROM memory_nodes")
            row = cur.fetchone()
        return int(row[0]) if row else 0

    def similarity_search(
        self,
        embedding: Sequence[float],
        top_k: int,
        *,
        min_confidence: float = 0.0,
        include_expired: bool = False,
    ) -> List[RetrievalResult]:
        """Return the ``top_k`` nearest nodes by cosine similarity."""
        if len(embedding) != self._dim:
            raise ValueError(
                f"query embedding dim {len(embedding)} != configured {self._dim}"
            )
        ttl_clause = "" if include_expired else (
            "AND (ttl_expires_at IS NULL OR ttl_expires_at > now())"
        )
        sql = f"""
            SELECT {_NODE_COLUMNS}, 1 - (embedding <=> %s::vector) AS similarity
            FROM memory_nodes
            WHERE confidence_score >= %s {ttl_clause}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        query_vec = _vector_literal(embedding)
        with self._client.cursor() as cur:
            cur.execute(sql, (query_vec, min_confidence, query_vec, top_k))
            rows = cur.fetchall()
        results: List[RetrievalResult] = []
        for row in rows:
            node = self._row_to_node(row[:-1])
            similarity = float(row[-1])
            results.append(
                RetrievalResult(
                    node=node,
                    similarity=similarity,
                    sources=[RetrievalSource.VECTOR],
                )
            )
        logger.debug("similarity_search returned %d row(s)", len(results))
        return results

    def keyword_search(self, query: str, top_k: int) -> List[RetrievalResult]:
        """Full-text search fallback using Postgres ``tsvector``/``ts_rank``."""
        sql = f"""
            SELECT {_NODE_COLUMNS},
                   ts_rank(to_tsvector('english', content),
                           plainto_tsquery('english', %s)) AS rank
            FROM memory_nodes
            WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
              AND (ttl_expires_at IS NULL OR ttl_expires_at > now())
            ORDER BY rank DESC
            LIMIT %s
        """
        with self._client.cursor() as cur:
            cur.execute(sql, (query, query, top_k))
            rows = cur.fetchall()
        results: List[RetrievalResult] = []
        for row in rows:
            node = self._row_to_node(row[:-1])
            rank = float(row[-1])
            # Map an unbounded ts_rank into (0, 1) for fair merging.
            similarity = rank / (rank + 1.0)
            results.append(
                RetrievalResult(
                    node=node,
                    similarity=similarity,
                    sources=[RetrievalSource.KEYWORD],
                )
            )
        return results

    def iter_all(self, *, batch_size: int = 500) -> Iterator[MemoryNode]:
        """Yield every node using keyset pagination over the primary key."""
        last_id: Optional[str] = None
        while True:
            with self._client.cursor() as cur:
                if last_id is None:
                    cur.execute(
                        f"SELECT {_NODE_COLUMNS} FROM memory_nodes "
                        "ORDER BY id LIMIT %s",
                        (batch_size,),
                    )
                else:
                    cur.execute(
                        f"SELECT {_NODE_COLUMNS} FROM memory_nodes "
                        "WHERE id > %s ORDER BY id LIMIT %s",
                        (last_id, batch_size),
                    )
                rows = cur.fetchall()
            if not rows:
                return
            for row in rows:
                node = self._row_to_node(row)
                last_id = node.id
                yield node
            if len(rows) < batch_size:
                return

    def expired_node_ids(self, *, confidence_floor: float) -> List[str]:
        """Return ids of nodes past TTL whose confidence is below the floor."""
        with self._client.cursor() as cur:
            cur.execute(
                "SELECT id FROM memory_nodes WHERE ttl_expires_at IS NOT NULL "
                "AND ttl_expires_at <= now() AND confidence_score < %s",
                (confidence_floor,),
            )
            rows = cur.fetchall()
        return [r[0] for r in rows]

    # -- row mapping ------------------------------------------------------- #
    def _node_to_row(self, node: MemoryNode) -> tuple:
        return (
            node.id,
            node.content,
            _vector_literal(node.embedding),
            list(node.entities),
            list(node.relationships),
            node.source_id,
            node.created_at,
            node.confidence_score,
            node.version,
            node.updated_at,
            node.last_accessed_at,
            node.reinforcement_count,
            node.ttl_expires_at,
            node.document_id,
            node.content_hash,
            _json(node.metadata),
        )

    @staticmethod
    def _row_to_node(row: Sequence[Any]) -> MemoryNode:
        return MemoryNode(
            id=row[0],
            content=row[1],
            embedding=_parse_embedding(row[2]),
            entities=list(row[3]) if row[3] else [],
            relationships=list(row[4]) if row[4] else [],
            source_id=row[5] or "",
            created_at=row[6] or utcnow(),
            confidence_score=float(row[7]),
            version=int(row[8]),
            updated_at=row[9] or utcnow(),
            last_accessed_at=row[10],
            reinforcement_count=int(row[11]) if row[11] is not None else 0,
            ttl_expires_at=row[12],
            document_id=row[13],
            content_hash=row[14],
            metadata=dict(row[15]) if row[15] else {},
        )
