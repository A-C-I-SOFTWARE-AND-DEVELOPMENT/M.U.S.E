"""GraphRAG query engine — three retrieval modes over the knowledge graph.

* :func:`local_query` — answer from the nodes nearest the question (seed by
  term overlap, expand one hop). Good for "what is X / where is X".
* :func:`global_query` — summarize the relevant communities/clusters. Good for
  "how does the whole system do Y".
* :func:`coding_query` — retrieve the code + tests + docs + recorded memory a
  coding task needs, so it *reuses* existing implementations instead of adding
  duplicates.

Every answer is a :class:`GraphAnswer`: ranked nodes, the edges among them, and
the de-duplicated provenance citations — fully inspectable and source-backed.
Deterministic and stdlib-only (no embeddings, no LLM).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from plugins.prime.graphrag.graph import (
    Edge,
    EdgeType,
    KnowledgeGraph,
    Node,
    NodeType,
)

# Deliberately small: question words and articles only. Imperative verbs like
# "add" / "find" / "show" / "get" are *kept* — they double as code identifiers,
# and dropping them blinds coding queries (e.g. "add function").
_STOPWORDS = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "into", "how", "what",
    "where", "which", "a", "an", "of", "to", "in", "on", "is", "are",
})

_CODE_NODE_TYPES = (NodeType.FILE, NodeType.FUNCTION, NodeType.CLASS)


def _terms(text: str) -> set[str]:
    toks = re.split(r"\W+", (text or "").lower())
    return {t for t in toks if len(t) > 2 and t not in _STOPWORDS}


def _node_haystack(node: Node) -> str:
    parts = [node.title, node.key]
    for v in node.attrs.values():
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts).lower()


def _score_node(node: Node, terms: set[str]) -> float:
    if not terms:
        return 0.0
    hay = _node_haystack(node)
    hay_tokens = set(re.split(r"\W+", hay))
    score = 0.0
    for t in terms:
        if t in hay_tokens:
            score += 2.0
        elif t in hay:
            score += 1.0
    return score


@dataclass
class GraphAnswer:
    mode: str
    question: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    communities: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "question": self.question,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "citations": self.citations,
            "communities": self.communities,
        }

    def render(self) -> str:
        lines = [f"# GraphRAG ({self.mode}) — {self.question}", ""]
        if self.communities:
            for c in self.communities:
                lines.append(
                    f"## cluster {c.get('label', '?')[:8]} "
                    f"({c.get('size', 0)} nodes)"
                )
                for t in c.get("top_titles", []):
                    lines.append(f"  - {t}")
                lines.append("")
        if self.nodes:
            lines.append("## related nodes")
            for n in self.nodes:
                lines.append(f"  - [{n.type.value}] {n.title}")
        if self.citations:
            lines.append("")
            lines.append("## sources")
            for c in self.citations[:20]:
                lines.append(f"  - {c.get('kind', '?')}: {c.get('uri', '')}")
        return "\n".join(lines)


def _collect_citations(nodes: Iterable[Node], edges: Iterable[Edge]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for item in list(nodes) + list(edges):
        for src in item.sources:
            sig = (src.get("uri", ""), src.get("kind", ""))
            if sig in seen:
                continue
            seen.add(sig)
            out.append(src)
    return out


def _edges_among(graph: KnowledgeGraph, node_ids: set[str]) -> list[Edge]:
    return [
        e for e in graph.edges.values() if e.src in node_ids and e.dst in node_ids
    ]


def seed_nodes(
    graph: KnowledgeGraph,
    question: str,
    *,
    limit: int = 8,
    node_types: Optional[Iterable[NodeType]] = None,
) -> list[Node]:
    terms = _terms(question)
    wanted = {t for t in node_types} if node_types else None
    scored: list[tuple[float, str, Node]] = []
    for node in graph.nodes.values():
        if wanted is not None and node.type not in wanted:
            continue
        s = _score_node(node, terms)
        if s > 0:
            scored.append((s, node.id, node))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [n for _, _, n in scored[:limit]]


# ---------------------------------------------------------------------------
# Query modes
# ---------------------------------------------------------------------------


def local_query(graph: KnowledgeGraph, question: str, *, limit: int = 8) -> GraphAnswer:
    seeds = seed_nodes(graph, question, limit=limit)
    keep: set[str] = {n.id for n in seeds}
    for n in seeds:
        keep.update(graph.neighbors(n.id, depth=1))
    nodes = [graph.nodes[i] for i in keep if i in graph.nodes]
    # Rank kept nodes: seeds first (by score), then neighbors by degree.
    terms = _terms(question)
    nodes.sort(key=lambda n: (-_score_node(n, terms), n.id))
    edges = _edges_among(graph, keep)
    answer = GraphAnswer(
        mode="local",
        question=question,
        nodes=nodes[: limit * 3],
        edges=edges,
        citations=_collect_citations(nodes[: limit * 3], edges),
    )
    return answer


def global_query(
    graph: KnowledgeGraph, question: str, *, max_communities: int = 5
) -> GraphAnswer:
    terms = _terms(question)
    communities = graph.communities()
    ranked: list[tuple[float, str, list[str]]] = []
    for label, members in communities.items():
        rel = sum(_score_node(graph.nodes[m], terms) for m in members if m in graph.nodes)
        # Prefer relevant clusters; fall back to larger clusters when no terms.
        key = rel if terms else float(len(members))
        ranked.append((key, label, members))
    ranked.sort(key=lambda x: (-x[0], x[1]))

    summaries: list[dict] = []
    shown_nodes: list[Node] = []
    for score, label, members in ranked[:max_communities]:
        if score <= 0 and terms:
            continue
        member_nodes = [graph.nodes[m] for m in members if m in graph.nodes]
        member_nodes.sort(
            key=lambda n: (
                -(len(graph._out.get(n.id, set())) + len(graph._in.get(n.id, set()))),
                n.id,
            )
        )
        top = member_nodes[:6]
        shown_nodes.extend(top)
        edge_counts: dict[str, int] = {}
        for e in graph.edges.values():
            if e.src in members and e.dst in members:
                edge_counts[e.type.value] = edge_counts.get(e.type.value, 0) + 1
        summaries.append({
            "label": label,
            "size": len(members),
            "relevance": round(score, 2),
            "top_titles": [n.title for n in top],
            "edge_types": dict(sorted(edge_counts.items())),
        })
    # Rank the surfaced nodes by the *same* deterministic contract as
    # ``local_query``/``coding_query`` — relevance score, then id — so all
    # modes hand back a consistently-ranked ``GraphAnswer.nodes`` (reusing
    # ``_score_node`` rather than duplicating any ranking logic). The
    # per-community degree sort above still chooses which representatives to
    # surface; this only fixes their final, cross-cluster order.
    shown_nodes.sort(key=lambda n: (-_score_node(n, terms), n.id))
    edges = _edges_among(graph, {n.id for n in shown_nodes})
    answer = GraphAnswer(
        mode="global",
        question=question,
        nodes=shown_nodes,
        edges=edges,
        citations=_collect_citations(shown_nodes, edges),
        communities=summaries,
    )
    return answer


def coding_query(graph: KnowledgeGraph, question: str, *, limit: int = 6) -> GraphAnswer:
    """Retrieve the code context a coding task needs: candidate files, their
    tests, the docs/sources that cite them, and any recorded memory touching
    them — so existing implementations get reused.
    """

    seeds = seed_nodes(graph, question, limit=limit, node_types=_CODE_NODE_TYPES)
    keep: set[str] = {n.id for n in seeds}
    for n in seeds:
        # Tests (incoming TESTS), the docs/sources that cite this node
        # (incoming CITES), and the code it depends on or calls.
        keep.update(
            graph.neighbors(
                n.id,
                depth=1,
                edge_types=[
                    EdgeType.TESTS,
                    EdgeType.CITES,
                    EdgeType.DEPENDS_ON,
                    EdgeType.CALLS,
                    EdgeType.OWNS,
                ],
            )
        )
    nodes = [graph.nodes[i] for i in keep if i in graph.nodes]
    terms = _terms(question)

    def _rank(n: Node) -> tuple:
        type_bonus = {
            NodeType.FILE: 0, NodeType.FUNCTION: 0, NodeType.CLASS: 0,
            NodeType.DECISION: -1, NodeType.DOCUMENT: -1, NodeType.SOURCE: -2,
        }.get(n.type, -3)
        return (-_score_node(n, terms), type_bonus, n.id)

    nodes.sort(key=_rank)
    edges = _edges_among(graph, keep)
    answer = GraphAnswer(
        mode="coding",
        question=question,
        nodes=nodes[: limit * 4],
        edges=edges,
        citations=_collect_citations(nodes[: limit * 4], edges),
    )
    return answer


# ---------------------------------------------------------------------------
# Related-items ("related files / sources / decisions" for a given node)
# ---------------------------------------------------------------------------

# How a neighbour node's type maps to the UI bucket.
_RELATED_BUCKET = {
    NodeType.FILE: "file",
    NodeType.FUNCTION: "file",
    NodeType.CLASS: "file",
    NodeType.MODULE: "file",
    NodeType.SOURCE: "source",
    NodeType.DOCUMENT: "source",
    NodeType.DECISION: "decision",
}


def related_items(
    graph: KnowledgeGraph, start_id: str, *, depth: int = 1, limit: int = 30
) -> list[dict]:
    """Return related files / sources / decisions for a node, each labelled
    with the relationship and whether it is source-backed.
    """

    if start_id not in graph.nodes:
        return []
    items: list[dict] = []
    neighbor_ids = graph.neighbors(start_id, depth=depth)
    # Determine the relationship label from the directly-connecting edge.
    rel_by_node: dict[str, str] = {}
    for e in graph.edges.values():
        if e.src == start_id and e.dst in neighbor_ids:
            rel_by_node.setdefault(e.dst, e.type.value)
        elif e.dst == start_id and e.src in neighbor_ids:
            rel_by_node.setdefault(e.src, e.type.value)
    for nid in neighbor_ids:
        node = graph.nodes.get(nid)
        if node is None:
            continue
        items.append({
            "kind": _RELATED_BUCKET.get(node.type, "file"),
            "node_type": node.type.value,
            "title": node.title,
            "ref": node.key,
            "relation": rel_by_node.get(nid, "related"),
            "source_backed": bool(node.sources),
            "sources": node.sources[:3],
        })
    # Sort: files, then sources, then decisions; alpha within bucket.
    order = {"file": 0, "source": 1, "decision": 2}
    items.sort(key=lambda i: (order.get(i["kind"], 3), i["title"]))
    return items[:limit]


def find_entity_node(graph: KnowledgeGraph, *, key: str) -> Optional[str]:
    """Resolve a graph node id from a node id, repo path, or memory id.

    Turns a caller-supplied key (e.g. the ``--key`` of ``hermes graph
    related``) into a graph node id, trying the key shapes the indexers use.
    """

    if not key:
        return None
    if key in graph.nodes:
        return key
    candidates = {key, f"memory:{key}", f"research:{key}", key.lstrip("./")}
    for n in graph.nodes.values():
        if n.key in candidates:
            return n.id
    return None
