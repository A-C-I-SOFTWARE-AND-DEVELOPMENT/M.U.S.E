"""Memory indexer — bring the Memory Tree into the graph.

Each active :class:`MemoryNode` becomes a DECISION node. Its provenance pointer
becomes a SOURCE node with a CITES edge; ``supersedes`` becomes SUPERSEDES
edges; and contradiction reports become CONTRADICTS edges. This makes "what
recorded this / what contradicts it" walkable from the graph.

Privacy: only already-stored, policy-filtered memory is read, and only the
title plus a short summary are copied — never the full ``text`` and never
anything the Memory Tree's write policy already rejects (secrets, raw
chain-of-thought, credentials).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from plugins.prime.graphrag.graph import EdgeType, KnowledgeGraph, NodeType, node_id

_SUMMARY_CAP = 240


def _decision_key(memory_id: str) -> str:
    return f"memory:{memory_id}"


def index_memory(
    graph: KnowledgeGraph, *, store=None, store_path: Optional[Path] = None
) -> KnowledgeGraph:
    if store is None:
        from plugins.prime.memory_tree import MemoryTreeStore

        store = MemoryTreeStore.load(store_path)

    # DECISION nodes + their provenance.
    for mem in store.nodes.values():
        if not getattr(mem, "active", True):
            continue
        mem_ref = {"uri": mem.id, "kind": "memory_tree"}
        dec = graph.add_node(
            NodeType.DECISION,
            _decision_key(mem.id),
            title=mem.title or mem.summary[:80] or mem.id,
            attrs={
                "namespace": mem.namespace,
                "summary": (mem.summary or "")[:_SUMMARY_CAP],
                "confidence": mem.confidence,
                "contradiction_status": mem.contradiction_status.value,
                "approval_state": mem.approval_state.value,
            },
            sources=[mem_ref],
        )
        # Provenance pointer -> SOURCE node, DECISION cites SOURCE.
        if mem.source_uri:
            src_node = graph.add_node(
                NodeType.SOURCE,
                mem.source_uri,
                title=mem.source_uri,
                attrs={"trust": mem.source_trust.value},
                sources=[{"uri": mem.source_uri, "kind": "memory_source"}],
            )
            graph.add_edge(dec.id, src_node.id, EdgeType.CITES, sources=[mem_ref])
        # supersedes edges (this decision supersedes prior ones).
        for prior in mem.supersedes:
            prior_id = node_id(NodeType.DECISION, _decision_key(prior))
            if prior_id in graph.nodes:
                graph.add_edge(dec.id, prior_id, EdgeType.SUPERSEDES, sources=[mem_ref])

    # CONTRADICTS edges from contradiction reports.
    for report in store.contradictions.values():
        a = node_id(NodeType.DECISION, _decision_key(report.node_a_id))
        b = node_id(NodeType.DECISION, _decision_key(report.node_b_id))
        ref = {"uri": report.id, "kind": "contradiction"}
        if a in graph.nodes and b in graph.nodes:
            graph.add_edge(
                a, b, EdgeType.CONTRADICTS,
                attrs={"status": report.status.value, "reason": report.reason},
                sources=[ref],
            )
    return graph
