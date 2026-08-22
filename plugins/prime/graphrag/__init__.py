"""GraphRAG — a typed knowledge graph over the repo, memory and evidence.

GraphRAG *supplements* (never replaces) the Memory Tree, Research Vault, and
repo-navigation substrates. It unifies them into one inspectable,
source-backed graph with three retrieval modes (local / global / coding) so
coding tasks reuse existing implementations instead of duplicating them.

Public surface::

    from plugins.prime.graphrag import (
        KnowledgeGraph, NodeType, EdgeType,
        GraphStore, build_graph, load_or_build,
        local_query, global_query, coding_query, related_items,
    )
"""

from plugins.prime.graphrag.builder import (
    ALL_INDEXERS,
    build_and_save,
    build_graph,
    load_or_build,
)
from plugins.prime.graphrag.graph import (
    Edge,
    EdgeType,
    KnowledgeGraph,
    Node,
    NodeType,
    node_id,
)
from plugins.prime.graphrag.query import (
    GraphAnswer,
    coding_query,
    find_entity_node,
    global_query,
    local_query,
    related_items,
    seed_nodes,
)
from plugins.prime.graphrag.store import GraphStore, default_graph_path

__all__ = [
    "KnowledgeGraph",
    "Node",
    "Edge",
    "NodeType",
    "EdgeType",
    "node_id",
    "GraphStore",
    "default_graph_path",
    "build_graph",
    "build_and_save",
    "load_or_build",
    "ALL_INDEXERS",
    "GraphAnswer",
    "local_query",
    "global_query",
    "coding_query",
    "related_items",
    "find_entity_node",
    "seed_nodes",
]
