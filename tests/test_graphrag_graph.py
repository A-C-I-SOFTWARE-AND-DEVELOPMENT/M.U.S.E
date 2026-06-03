"""Tests for the GraphRAG core graph: nodes, edges, traversal, communities,
store round-trip."""

from __future__ import annotations

import pytest

from hermes_cli.jarvis_prime.graphrag.graph import (
    Edge,
    EdgeType,
    KnowledgeGraph,
    Node,
    NodeType,
    node_id,
)
from hermes_cli.jarvis_prime.graphrag.store import GraphStore


def test_node_id_is_stable_and_typed():
    a = node_id(NodeType.FILE, "pkg/foo.py")
    b = node_id(NodeType.FILE, "pkg/foo.py")
    c = node_id(NodeType.FUNCTION, "pkg/foo.py")
    assert a == b
    assert a != c
    assert a.startswith("file:")
    assert c.startswith("function:")


def test_add_node_is_idempotent_and_merges_provenance():
    g = KnowledgeGraph()
    g.add_node(NodeType.FILE, "a.py", title="a.py", sources=[{"uri": "a.py", "kind": "repo"}])
    g.add_node(NodeType.FILE, "a.py", attrs={"language": "python"}, sources=[{"uri": "a.py", "kind": "doc"}])
    assert len(g.nodes) == 1
    node = next(iter(g.nodes.values()))
    assert node.attrs["language"] == "python"
    # Two distinct provenance kinds accumulate.
    assert len(node.sources) == 2


def test_add_edge_requires_known_endpoints():
    g = KnowledgeGraph()
    g.add_node(NodeType.FILE, "a.py")
    # dst missing -> ignored, never raises.
    assert g.add_edge(node_id(NodeType.FILE, "a.py"), node_id(NodeType.FILE, "missing.py"), EdgeType.IMPORTS) is None
    g.add_node(NodeType.FILE, "b.py")
    e = g.add_edge(node_id(NodeType.FILE, "a.py"), node_id(NodeType.FILE, "b.py"), EdgeType.IMPORTS)
    assert e is not None and e.type == EdgeType.IMPORTS


def test_add_edge_merge_bumps_weight():
    g = KnowledgeGraph()
    a = g.add_node(NodeType.FILE, "a.py")
    b = g.add_node(NodeType.FILE, "b.py")
    g.add_edge(a.id, b.id, EdgeType.DEPENDS_ON, weight=1.0)
    g.add_edge(a.id, b.id, EdgeType.DEPENDS_ON, weight=1.0)
    assert len(g.edges) == 1
    assert next(iter(g.edges.values())).weight == 2.0


def test_neighbors_respects_depth_and_edge_type():
    g = KnowledgeGraph()
    a = g.add_node(NodeType.FILE, "a.py")
    b = g.add_node(NodeType.FILE, "b.py")
    c = g.add_node(NodeType.FILE, "c.py")
    g.add_edge(a.id, b.id, EdgeType.IMPORTS)
    g.add_edge(b.id, c.id, EdgeType.TESTS)
    assert g.neighbors(a.id, depth=1) == [b.id]
    assert set(g.neighbors(a.id, depth=2)) == {b.id, c.id}
    # Filter to IMPORTS only -> can't cross the TESTS edge.
    assert g.neighbors(a.id, depth=2, edge_types=[EdgeType.IMPORTS]) == [b.id]


def test_communities_groups_connected_clusters():
    g = KnowledgeGraph()
    # Cluster 1: a-b-c
    for name in ("a", "b", "c"):
        g.add_node(NodeType.FILE, f"{name}.py")
    g.add_edge(node_id(NodeType.FILE, "a.py"), node_id(NodeType.FILE, "b.py"), EdgeType.IMPORTS)
    g.add_edge(node_id(NodeType.FILE, "b.py"), node_id(NodeType.FILE, "c.py"), EdgeType.IMPORTS)
    # Cluster 2: x-y
    for name in ("x", "y"):
        g.add_node(NodeType.FILE, f"{name}.py")
    g.add_edge(node_id(NodeType.FILE, "x.py"), node_id(NodeType.FILE, "y.py"), EdgeType.IMPORTS)
    comms = g.communities()
    # Two disconnected clusters -> at least two communities.
    assert len(comms) >= 2
    sizes = sorted(len(m) for m in comms.values())
    assert sizes[-1] == 3  # a,b,c stay together


def test_store_round_trip(tmp_path):
    g = KnowledgeGraph()
    a = g.add_node(NodeType.FILE, "a.py", title="a.py", sources=[{"uri": "a.py", "kind": "repo"}])
    b = g.add_node(NodeType.FUNCTION, "a.py::foo", title="foo")
    g.add_edge(a.id, b.id, EdgeType.OWNS, sources=[{"uri": "a.py", "kind": "repo"}])
    store = GraphStore(tmp_path / "graph.json")
    store.save(g)
    loaded = store.load()
    assert loaded.stats()["nodes"] == 2
    assert loaded.stats()["edges"] == 1
    # Provenance survives the round trip.
    assert any(n.sources for n in loaded.nodes.values())


def test_from_dict_drops_dangling_edges():
    payload = {
        "nodes": [Node.make(NodeType.FILE, "a.py").to_dict()],
        "edges": [Edge(src=node_id(NodeType.FILE, "a.py"), dst="file:deadbeef", type=EdgeType.IMPORTS).to_dict()],
    }
    g = KnowledgeGraph.from_dict(payload)
    assert len(g.nodes) == 1
    assert len(g.edges) == 0  # dangling edge dropped
