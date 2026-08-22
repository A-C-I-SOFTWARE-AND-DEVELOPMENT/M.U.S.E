"""Evidence indexer — bring the Research Vault into the graph.

Each :class:`ResearchArtifact` becomes a SOURCE node (a cited, evidence-graded
artifact). When the artifact's ``source_uri`` is a repo-relative path we also
add a CITES edge to that FILE/DOCUMENT node, so coding/global queries can reach
the evidence backing a file. Evidence strength maps to edge weight.

Read-only: it loads the vault via :meth:`ResearchVault.load`. It never writes
back and never fabricates summaries (the vault already enforces that).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from plugins.prime.graphrag.graph import EdgeType, KnowledgeGraph, NodeType, node_id

# Evidence strength -> edge weight (primary evidence ranks above anecdotes).
_STRENGTH_WEIGHT = {
    "primary": 4.0,
    "strong": 3.0,
    "moderate": 2.0,
    "weak": 1.0,
    "vendor_reported": 1.5,
}


def index_evidence(
    graph: KnowledgeGraph, *, vault=None, vault_path: Optional[Path] = None
) -> KnowledgeGraph:
    if vault is None:
        from plugins.prime.research_vault import ResearchVault

        vault = ResearchVault.load(vault_path)

    for art in vault.entries():
        src_ref = {"uri": art.source_uri, "kind": "research_vault", "id": art.id}
        node = graph.add_node(
            NodeType.SOURCE,
            f"research:{art.id}",
            title=art.title or art.source_uri,
            attrs={
                "source_uri": art.source_uri,
                "source_type": art.source_type.value,
                "evidence_strength": art.evidence_strength.value,
                "summary": art.summary,
            },
            sources=[src_ref],
        )
        weight = _STRENGTH_WEIGHT.get(art.evidence_strength.value, 2.0)
        # If the evidence points at a repo file/doc already in the graph,
        # connect the source to it (source cites file).
        target_id = _repo_target(graph, art.source_uri)
        if target_id is not None:
            graph.add_edge(
                node.id, target_id, EdgeType.CITES, weight=weight, sources=[src_ref]
            )
    return graph


def _repo_target(graph: KnowledgeGraph, uri: str) -> Optional[str]:
    if not uri or "://" in uri:
        return None
    rel = uri.lstrip("./")
    for nt in (NodeType.DOCUMENT, NodeType.FILE):
        candidate = node_id(nt, rel)
        if candidate in graph.nodes:
            return candidate
    return None
