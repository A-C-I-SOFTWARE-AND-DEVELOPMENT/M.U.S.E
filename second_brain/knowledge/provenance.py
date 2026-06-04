"""Provenance tracking (Layer 1/2 — Representation & Storage).

Every node carries a provenance chain: which source it came from, what
transformations produced it, and when. Provenance is append-only and is the
backbone of the grounding-coverage evaluation metric and the governance
audit trail.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Sequence

from .models import ProvenanceRecord, utcnow
from .vector_store import PostgresClient

logger = logging.getLogger(__name__)

__all__ = ["ProvenanceTracker"]


def _json(value: Any) -> Any:
    from psycopg2.extras import Json  # type: ignore import-not-found

    return Json(value)


class ProvenanceTracker:
    """Append-only provenance store backed by Postgres."""

    def __init__(self, client: PostgresClient) -> None:
        self._client = client

    def record(self, record: ProvenanceRecord) -> str:
        """Append a provenance record and return its id."""
        with self._client.cursor() as cur:
            cur.execute(
                "INSERT INTO provenance (id, node_id, source_id, source_type, source_uri, "
                "transformation, content_hash, ingested_at, metadata) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    record.id,
                    record.node_id,
                    record.source_id,
                    record.source_type,
                    record.source_uri,
                    record.transformation,
                    record.content_hash,
                    record.ingested_at,
                    _json(record.metadata),
                ),
            )
            row = cur.fetchone()
        logger.debug("Recorded provenance for node=%s", record.node_id)
        return row[0] if row else record.id

    def for_node(self, node_id: str) -> List[ProvenanceRecord]:
        """Return the provenance chain for a node, oldest first."""
        with self._client.cursor() as cur:
            cur.execute(
                "SELECT id, node_id, source_id, source_type, source_uri, transformation, "
                "content_hash, ingested_at, metadata FROM provenance "
                "WHERE node_id = %s ORDER BY ingested_at",
                (node_id,),
            )
            rows = cur.fetchall()
        return [self._row_to_record(r) for r in rows]

    def sources_for_nodes(self, node_ids: Sequence[str]) -> List[str]:
        """Return the distinct source ids backing a set of nodes."""
        if not node_ids:
            return []
        with self._client.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT source_id FROM provenance WHERE node_id = ANY(%s)",
                (list(node_ids),),
            )
            rows = cur.fetchall()
        return [r[0] for r in rows]

    @staticmethod
    def _row_to_record(row: Sequence[Any]) -> ProvenanceRecord:
        return ProvenanceRecord(
            id=row[0],
            node_id=row[1],
            source_id=row[2],
            source_type=row[3] or "unknown",
            source_uri=row[4],
            transformation=row[5] or "",
            content_hash=row[6],
            ingested_at=row[7] or utcnow(),
            metadata=dict(row[8]) if row[8] else {},
        )
