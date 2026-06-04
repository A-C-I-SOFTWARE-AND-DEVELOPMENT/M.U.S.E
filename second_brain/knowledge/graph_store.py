"""Neo4j graph backend (Layer 2 — Persistent Storage).

Models knowledge as a property graph:

* ``(:MemoryNode {id, source_id, confidence, ...})`` — one per memory node.
* ``(:Entity {name})`` — canonicalised named entities.
* ``(:MemoryNode)-[:MENTIONS]->(:Entity)`` — node-to-entity membership.
* ``(:Entity)-[:REL {predicate, confidence, node_id}]->(:Entity)`` — typed
  relationships extracted at ingestion, used for multi-hop reasoning.

The ``neo4j`` driver is imported lazily so the package imports without it.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Sequence

from .config import Neo4jConfig
from .models import GraphNeighbor, MemoryNode, Relationship

logger = logging.getLogger(__name__)

__all__ = ["GraphStore"]

_MAX_HOPS = 6


class GraphStore:
    """Thin, well-typed wrapper over the official Neo4j Python driver."""

    def __init__(self, config: Neo4jConfig) -> None:
        self._config = config
        self._driver: Any = None

    def _ensure_driver(self) -> Any:
        if self._driver is not None:
            return self._driver
        try:
            from neo4j import GraphDatabase  # type: ignore import-not-found
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "The neo4j driver is required for graph features. Install with "
                "`pip install neo4j`."
            ) from exc
        self._driver = GraphDatabase.driver(
            self._config.uri,
            auth=(self._config.user, self._config.password),
            max_connection_pool_size=self._config.max_connection_pool_size,
        )
        logger.debug("Opened Neo4j driver to %s", self._config.uri)
        return self._driver

    # -- schema ------------------------------------------------------------ #
    def ensure_constraints(self) -> None:
        """Create uniqueness constraints/indexes (idempotent)."""
        statements = [
            "CREATE CONSTRAINT memory_node_id IF NOT EXISTS "
            "FOR (n:MemoryNode) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT entity_name IF NOT EXISTS "
            "FOR (e:Entity) REQUIRE e.name IS UNIQUE",
        ]
        driver = self._ensure_driver()
        with driver.session(database=self._config.database) as session:
            for stmt in statements:
                session.run(stmt)
        logger.debug("Ensured Neo4j constraints")

    # -- writes ------------------------------------------------------------ #
    def upsert_node(
        self, node: MemoryNode, relationships: Optional[Sequence[Relationship]] = None
    ) -> None:
        """MERGE a memory node, its entities, and their relationships."""
        driver = self._ensure_driver()
        rels = [
            {
                "subject": r.subject,
                "predicate": r.predicate,
                "object": r.object,
                "confidence": r.confidence,
            }
            for r in (relationships or [])
        ]
        with driver.session(database=self._config.database) as session:
            session.execute_write(self._upsert_tx, node, rels)
        logger.debug("Graph upsert node=%s entities=%d", node.id, len(node.entities))

    @staticmethod
    def _upsert_tx(tx: Any, node: MemoryNode, rels: List[dict]) -> None:
        tx.run(
            """
            MERGE (n:MemoryNode {id: $id})
            SET n.source_id = $source_id,
                n.confidence = $confidence,
                n.version = $version,
                n.content_preview = $preview
            """,
            id=node.id,
            source_id=node.source_id,
            confidence=node.confidence_score,
            version=node.version,
            preview=node.content[:280],
        )
        if node.entities:
            tx.run(
                """
                MATCH (n:MemoryNode {id: $id})
                UNWIND $entities AS ename
                MERGE (e:Entity {name: ename})
                MERGE (n)-[:MENTIONS]->(e)
                """,
                id=node.id,
                entities=list(node.entities),
            )
        if rels:
            tx.run(
                """
                UNWIND $rels AS rel
                MERGE (s:Entity {name: rel.subject})
                MERGE (o:Entity {name: rel.object})
                MERGE (s)-[r:REL {predicate: rel.predicate, node_id: $id}]->(o)
                SET r.confidence = rel.confidence
                """,
                rels=rels,
                id=node.id,
            )

    def delete_node(self, node_id: str) -> None:
        driver = self._ensure_driver()
        with driver.session(database=self._config.database) as session:
            session.run(
                "MATCH (n:MemoryNode {id: $id}) DETACH DELETE n", id=node_id
            )

    # -- reads ------------------------------------------------------------- #
    def expand(
        self, node_ids: Sequence[str], hops: int, limit: int
    ) -> List[GraphNeighbor]:
        """Return memory nodes reachable from ``node_ids`` within ``hops``.

        Traversal goes node -> shared entities -> co-mentioning nodes, which
        is the practical "related knowledge" expansion for hybrid retrieval.
        """
        if not node_ids:
            return []
        safe_hops = max(1, min(_MAX_HOPS, int(hops)))
        # Each logical hop is node->entity->node, i.e. two relationships.
        depth = safe_hops * 2
        cypher = (
            "MATCH (seed:MemoryNode) WHERE seed.id IN $ids "
            f"MATCH path = (seed)-[:MENTIONS|REL*1..{depth}]-(m:MemoryNode) "
            "WHERE NOT m.id IN $ids "
            "WITH m, min(length(path)) AS dist "
            "RETURN m.id AS id, dist ORDER BY dist ASC LIMIT $limit"
        )
        driver = self._ensure_driver()
        out: List[GraphNeighbor] = []
        with driver.session(database=self._config.database) as session:
            result = session.run(cypher, ids=list(node_ids), limit=int(limit))
            for record in result:
                out.append(
                    GraphNeighbor(
                        node_id=record["id"],
                        distance=int(record["dist"]),
                    )
                )
        logger.debug("Graph expand from %d seeds -> %d neighbors", len(node_ids), len(out))
        return out

    def entity_neighbors(
        self, entities: Sequence[str], hops: int, limit: int = 64
    ) -> List[dict]:
        """Return entity-level relationship paths for reasoning (Layer 4)."""
        if not entities:
            return []
        safe_hops = max(1, min(_MAX_HOPS, int(hops)))
        cypher = (
            "MATCH (e:Entity) WHERE e.name IN $names "
            f"MATCH path = (e)-[r:REL*1..{safe_hops}]-(e2:Entity) "
            "RETURN [n IN nodes(path) | n.name] AS chain, "
            "[rel IN relationships(path) | rel.predicate] AS predicates, "
            "length(path) AS dist ORDER BY dist ASC LIMIT $limit"
        )
        driver = self._ensure_driver()
        out: List[dict] = []
        with driver.session(database=self._config.database) as session:
            result = session.run(cypher, names=list(entities), limit=int(limit))
            for record in result:
                out.append(
                    {
                        "chain": list(record["chain"]),
                        "predicates": list(record["predicates"]),
                        "distance": int(record["dist"]),
                    }
                )
        return out

    def close(self) -> None:
        """Close the underlying driver."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
