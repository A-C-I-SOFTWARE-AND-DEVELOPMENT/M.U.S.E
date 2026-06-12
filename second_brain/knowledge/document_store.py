"""Raw document persistence (Layer 2 — Persistent Storage).

Stores the original source text and metadata so that every derived
:class:`~knowledge.models.MemoryNode` can be traced back to, and re-derived
from, an immutable raw document. Backed by Postgres via the shared
:class:`~knowledge.vector_store.PostgresClient`.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Sequence

from .models import Document, utcnow
from .vector_store import PostgresClient

logger = logging.getLogger(__name__)

__all__ = ["DocumentStore"]


def _json(value: Any) -> Any:
    from psycopg2.extras import Json  # ty: ignore[unresolved-import]

    return Json(value)


class DocumentStore:
    """CRUD for raw source documents, keyed by id and de-duplicated by hash."""

    def __init__(self, client: PostgresClient) -> None:
        self._client = client

    def save(self, document: Document) -> str:
        """Persist a document. If an identical hash exists, reuse its id.

        Returns the id of the stored (or pre-existing) document, enabling
        content-addressable de-duplication of re-ingested sources.
        """
        existing = self.find_by_hash(document.content_hash) if document.content_hash else None
        if existing is not None:
            logger.debug("Document hash already present; reusing id=%s", existing.id)
            return existing.id
        with self._client.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (id, source_id, title, raw_content, content_hash, "
                "metadata, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET "
                "raw_content = EXCLUDED.raw_content, metadata = EXCLUDED.metadata "
                "RETURNING id",
                (
                    document.id,
                    document.source_id,
                    document.title,
                    document.content,
                    document.content_hash,
                    _json(document.metadata),
                    document.created_at,
                ),
            )
            row = cur.fetchone()
        logger.debug("Saved document id=%s source=%s", document.id, document.source_id)
        return row[0] if row else document.id

    def get(self, document_id: str) -> Optional[Document]:
        with self._client.cursor() as cur:
            cur.execute(
                "SELECT id, source_id, title, raw_content, content_hash, metadata, "
                "created_at FROM documents WHERE id = %s",
                (document_id,),
            )
            row = cur.fetchone()
        return self._row_to_document(row) if row else None

    def find_by_hash(self, content_hash: Optional[str]) -> Optional[Document]:
        if not content_hash:
            return None
        with self._client.cursor() as cur:
            cur.execute(
                "SELECT id, source_id, title, raw_content, content_hash, metadata, "
                "created_at FROM documents WHERE content_hash = %s LIMIT 1",
                (content_hash,),
            )
            row = cur.fetchone()
        return self._row_to_document(row) if row else None

    def get_by_source(self, source_id: str) -> List[Document]:
        with self._client.cursor() as cur:
            cur.execute(
                "SELECT id, source_id, title, raw_content, content_hash, metadata, "
                "created_at FROM documents WHERE source_id = %s ORDER BY created_at",
                (source_id,),
            )
            rows = cur.fetchall()
        return [self._row_to_document(r) for r in rows]

    def exists(self, content_hash: str) -> bool:
        return self.find_by_hash(content_hash) is not None

    def delete(self, document_id: str) -> None:
        with self._client.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))

    @staticmethod
    def _row_to_document(row: Sequence[Any]) -> Document:
        return Document(
            id=row[0],
            source_id=row[1],
            title=row[2],
            content=row[3],
            content_hash=row[4],
            metadata=dict(row[5]) if row[5] else {},
            created_at=row[6] or utcnow(),
        )
