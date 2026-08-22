"""GraphRAG knowledge graph — typed, source-backed nodes and edges.

A deterministic, stdlib-only, source-backed property graph that *supplements*
(never replaces) the Memory Tree, Research Vault, and repo-navigation
substrates. Every :class:`Node` and :class:`Edge` carries ``sources`` —
provenance pointers back to the repo path, memory node, or
research artifact it was derived from — so the graph is fully inspectable and
nothing is invented. Genuinely-absent values stay empty.

This module is pure data + graph algorithms. Indexers (``graphrag.indexers``)
populate it from existing subsystems; :mod:`graphrag.query` reads it; and
:mod:`graphrag.store` persists it. No network, no LLM, no heavy deps.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional, TypedDict


class GraphStats(TypedDict):
    """Precise shape of :meth:`KnowledgeGraph.stats` (keeps type-checkers
    happy when callers index into the counts)."""

    nodes: int
    edges: int
    by_node_type: dict[str, int]
    by_edge_type: dict[str, int]


class NodeType(str, Enum):
    """Entity kinds an indexer can produce. Every member has a producer:
    FILE/MODULE/FUNCTION/CLASS come from the code indexer, DOCUMENT from the
    docs indexer, SOURCE from the Research Vault and Memory Tree provenance,
    DECISION from the Memory Tree."""

    FILE = "file"
    MODULE = "module"
    FUNCTION = "function"
    CLASS = "class"
    DOCUMENT = "document"
    SOURCE = "source"
    DECISION = "decision"


class EdgeType(str, Enum):
    """Relationship kinds. Like :class:`NodeType`, each one is emitted by an
    indexer in this package — nothing here is aspirational vocabulary."""

    CALLS = "calls"
    IMPORTS = "imports"
    OWNS = "owns"
    TESTS = "tests"
    CITES = "cites"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    DEPENDS_ON = "depends_on"


def node_id(node_type: "NodeType | str", key: str) -> str:
    """Stable, collision-resistant id for a ``(type, key)`` identity.

    Deterministic so re-indexing the same entity merges onto the same node
    instead of creating a duplicate.
    """

    t = node_type.value if isinstance(node_type, NodeType) else str(node_type)
    digest = hashlib.sha1(f"{t}:{key}".encode("utf-8")).hexdigest()[:16]
    return f"{t}:{digest}"


def _dedup_sources(sources: Iterable[dict]) -> list[dict]:
    """Stable de-duplication of provenance pointers (order preserved)."""

    seen: set[tuple] = set()
    out: list[dict] = []
    for src in sources:
        if not isinstance(src, dict):
            continue
        sig = (src.get("uri", ""), src.get("kind", ""), src.get("line_ref", ""))
        if sig in seen:
            continue
        seen.add(sig)
        out.append(dict(src))
    return out


@dataclass
class Node:
    """A typed graph node with provenance.

    ``key`` is the human-meaningful identity (e.g. a repo path, a job id, a
    source uri). ``id`` is derived from ``(type, key)`` and is what edges
    reference. ``sources`` are provenance pointers — never fabricated.
    """

    id: str
    type: NodeType
    key: str
    title: str = ""
    attrs: dict = field(default_factory=dict)
    sources: list[dict] = field(default_factory=list)

    @classmethod
    def make(
        cls,
        node_type: NodeType,
        key: str,
        *,
        title: str = "",
        attrs: Optional[dict] = None,
        sources: Optional[Iterable[dict]] = None,
    ) -> "Node":
        return cls(
            id=node_id(node_type, key),
            type=node_type,
            key=key,
            title=title or key,
            attrs=dict(attrs or {}),
            sources=_dedup_sources(sources or []),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "type": self.type.value,
            "key": self.key,
            "title": self.title,
            "attrs": self.attrs,
            "sources": self.sources,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Node":
        return cls(
            id=d["id"],
            type=NodeType(d["type"]),
            key=d.get("key", ""),
            title=d.get("title", ""),
            attrs=dict(d.get("attrs", {}) or {}),
            sources=_dedup_sources(d.get("sources", []) or []),
        )


@dataclass
class Edge:
    """A typed, weighted, source-backed relationship between two nodes."""

    src: str
    dst: str
    type: EdgeType
    weight: float = 1.0
    attrs: dict = field(default_factory=dict)
    sources: list[dict] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.src, self.dst, self.type.value)

    def to_dict(self) -> dict[str, object]:
        return {
            "src": self.src,
            "dst": self.dst,
            "type": self.type.value,
            "weight": round(self.weight, 4),
            "attrs": self.attrs,
            "sources": self.sources,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Edge":
        return cls(
            src=d["src"],
            dst=d["dst"],
            type=EdgeType(d["type"]),
            weight=float(d.get("weight", 1.0)),
            attrs=dict(d.get("attrs", {}) or {}),
            sources=_dedup_sources(d.get("sources", []) or []),
        )


@dataclass
class KnowledgeGraph:
    """An in-memory typed property graph with deterministic algorithms."""

    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[tuple[str, str, str], Edge] = field(default_factory=dict)
    _out: dict[str, set[tuple[str, str, str]]] = field(default_factory=dict)
    _in: dict[str, set[tuple[str, str, str]]] = field(default_factory=dict)

    # -- mutation -----------------------------------------------------------

    def add_node(
        self,
        node_type: NodeType,
        key: str,
        *,
        title: str = "",
        attrs: Optional[dict] = None,
        sources: Optional[Iterable[dict]] = None,
    ) -> Node:
        """Add or merge a node. Idempotent — re-adding the same identity
        merges attrs/sources rather than overwriting (never silent clobber).
        """

        node = Node.make(
            node_type, key, title=title, attrs=attrs, sources=sources
        )
        existing = self.nodes.get(node.id)
        if existing is None:
            self.nodes[node.id] = node
            self._out.setdefault(node.id, set())
            self._in.setdefault(node.id, set())
            return node
        # Merge: keep a non-empty title, union attrs (new wins per-key),
        # and accumulate provenance.
        if node.title and node.title != node.key:
            existing.title = node.title
        existing.attrs.update(node.attrs)
        existing.sources = _dedup_sources(existing.sources + node.sources)
        return existing

    def add_edge(
        self,
        src_id: str,
        dst_id: str,
        edge_type: EdgeType,
        *,
        weight: float = 1.0,
        attrs: Optional[dict] = None,
        sources: Optional[Iterable[dict]] = None,
    ) -> Optional[Edge]:
        """Add or merge an edge. Endpoints must already exist; unknown
        endpoints are ignored (best-effort, never fatal). Re-adding sums a
        small weight bump and accumulates provenance.
        """

        if src_id not in self.nodes or dst_id not in self.nodes:
            return None
        key = (src_id, dst_id, edge_type.value)
        existing = self.edges.get(key)
        if existing is None:
            edge = Edge(
                src=src_id,
                dst=dst_id,
                type=edge_type,
                weight=weight,
                attrs=dict(attrs or {}),
                sources=_dedup_sources(sources or []),
            )
            self.edges[key] = edge
            self._out.setdefault(src_id, set()).add(key)
            self._in.setdefault(dst_id, set()).add(key)
            return edge
        existing.weight = round(existing.weight + weight, 4)
        if attrs:
            existing.attrs.update(attrs)
        if sources:
            existing.sources = _dedup_sources(existing.sources + list(sources))
        return existing

    # -- traversal ----------------------------------------------------------

    def out_edges(self, node_id_: str) -> list[Edge]:
        return [self.edges[k] for k in sorted(self._out.get(node_id_, set()))]

    def in_edges(self, node_id_: str) -> list[Edge]:
        return [self.edges[k] for k in sorted(self._in.get(node_id_, set()))]

    def neighbors(
        self,
        node_id_: str,
        *,
        depth: int = 1,
        edge_types: Optional[Iterable[EdgeType]] = None,
        direction: str = "both",
    ) -> list[str]:
        """Breadth-first neighbor ids up to ``depth`` hops. Deterministic
        (results sorted), excludes the seed itself.
        """

        wanted = {e.value for e in edge_types} if edge_types else None
        seen: set[str] = {node_id_}
        frontier = [node_id_]
        for _ in range(max(0, depth)):
            nxt: list[str] = []
            for nid in frontier:
                edges: list[Edge] = []
                if direction in ("out", "both"):
                    edges += self.out_edges(nid)
                if direction in ("in", "both"):
                    edges += self.in_edges(nid)
                for e in edges:
                    if wanted is not None and e.type.value not in wanted:
                        continue
                    other = e.dst if e.src == nid else e.src
                    if other not in seen:
                        seen.add(other)
                        nxt.append(other)
            frontier = nxt
        seen.discard(node_id_)
        return sorted(seen)

    # -- algorithms ---------------------------------------------------------

    def communities(self, *, max_iter: int = 20) -> dict[str, list[str]]:
        """Detect communities via deterministic label propagation.

        Each node starts in its own community; on every pass (nodes visited
        in sorted id order) a node adopts the most common label among its
        undirected neighbors, breaking ties by the smallest label so the
        result is reproducible. Returns ``{label -> sorted member ids}``.
        """

        if not self.nodes:
            return {}
        labels: dict[str, str] = {nid: nid for nid in self.nodes}
        order = sorted(self.nodes)
        adj: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for edge in self.edges.values():
            adj[edge.src].append(edge.dst)
            adj[edge.dst].append(edge.src)
        for _ in range(max_iter):
            changed = False
            for nid in order:
                nbrs = adj[nid]
                if not nbrs:
                    continue
                counts: dict[str, int] = {}
                for nb in nbrs:
                    lbl = labels[nb]
                    counts[lbl] = counts.get(lbl, 0) + 1
                # Most frequent label; tie -> smallest label string.
                best = min(counts, key=lambda l: (-counts[l], l))
                if labels[nid] != best:
                    labels[nid] = best
                    changed = True
            if not changed:
                break
        groups: dict[str, list[str]] = {}
        for nid, lbl in labels.items():
            groups.setdefault(lbl, []).append(nid)
        return {lbl: sorted(members) for lbl, members in groups.items()}

    # -- views --------------------------------------------------------------

    def stats(self) -> GraphStats:
        by_node_type: dict[str, int] = {}
        for n in self.nodes.values():
            by_node_type[n.type.value] = by_node_type.get(n.type.value, 0) + 1
        by_edge_type: dict[str, int] = {}
        for e in self.edges.values():
            by_edge_type[e.type.value] = by_edge_type.get(e.type.value, 0) + 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "by_node_type": dict(sorted(by_node_type.items())),
            "by_edge_type": dict(sorted(by_edge_type.items())),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeGraph":
        g = cls()
        for nd in d.get("nodes", []) or []:
            node = Node.from_dict(nd)
            g.nodes[node.id] = node
            g._out.setdefault(node.id, set())
            g._in.setdefault(node.id, set())
        for ed in d.get("edges", []) or []:
            edge = Edge.from_dict(ed)
            if edge.src in g.nodes and edge.dst in g.nodes:
                g.edges[edge.key] = edge
                g._out.setdefault(edge.src, set()).add(edge.key)
                g._in.setdefault(edge.dst, set()).add(edge.key)
        return g
