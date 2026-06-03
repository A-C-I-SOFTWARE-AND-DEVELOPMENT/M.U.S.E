"""Tests for the GraphRAG query modes and related-items projection."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.graphrag.builder import build_graph
from hermes_cli.jarvis_prime.graphrag.graph import KnowledgeGraph, NodeType, node_id
from hermes_cli.jarvis_prime.graphrag.indexers import index_code, index_docs
from hermes_cli.jarvis_prime.graphrag.query import (
    coding_query,
    find_entity_node,
    global_query,
    local_query,
    related_items,
)


@pytest.fixture()
def graph(tmp_path: Path) -> KnowledgeGraph:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "calculator.py").write_text(
        "from pkg.helpers import clamp\n\n\n"
        "def add(a, b):\n    return clamp(a + b)\n\n\n"
        "class Calculator:\n    pass\n"
    )
    (tmp_path / "pkg" / "helpers.py").write_text("def clamp(x):\n    return max(0, x)\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calculator.py").write_text(
        "from pkg.calculator import add\n\ndef test_add():\n    assert add(1,2)==3\n"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "calculator-guide.md").write_text(
        "# Calculator guide\n\nThe calculator add function lives in pkg/calculator.py.\n"
    )
    g = KnowledgeGraph()
    index_code(g, tmp_path)
    index_docs(g, tmp_path)
    return g


def test_local_query_finds_nearest_nodes(graph: KnowledgeGraph):
    ans = local_query(graph, "calculator add function")
    assert ans.mode == "local"
    titles = {n.title for n in ans.nodes}
    assert "add" in titles or "calculator.py" in titles
    # Source-backed.
    assert ans.citations


def test_global_query_summarizes_communities(graph: KnowledgeGraph):
    ans = global_query(graph, "calculator")
    assert ans.mode == "global"
    assert ans.communities
    # Each community summary names its top nodes and edge types.
    first = ans.communities[0]
    assert "top_titles" in first and "edge_types" in first


def test_coding_query_returns_code_tests_and_docs(graph: KnowledgeGraph):
    ans = coding_query(graph, "add function in calculator")
    kinds = {n.type for n in ans.nodes}
    # Seeds are code; expansion pulls in the test file and the doc.
    assert NodeType.FILE in kinds
    refs = {n.key for n in ans.nodes}
    assert "tests/test_calculator.py" in refs  # its test was retrieved
    assert any(n.type == NodeType.DOCUMENT for n in ans.nodes)


def test_related_items_buckets_and_labels(graph: KnowledgeGraph):
    calc_id = node_id(NodeType.FILE, "pkg/calculator.py")
    items = related_items(graph, calc_id)
    assert items
    buckets = {i["kind"] for i in items}
    assert "file" in buckets  # symbols + helpers/test files
    # Each item carries a relationship and source-backed flag.
    assert all("relation" in i and "source_backed" in i for i in items)


def test_find_entity_node_resolves_key(graph: KnowledgeGraph):
    resolved = find_entity_node(graph, key="pkg/calculator.py")
    assert resolved == node_id(NodeType.FILE, "pkg/calculator.py")
    assert find_entity_node(graph, key="does/not/exist") is None


def test_find_entity_node_resolves_audit_id_via_attr(graph: KnowledgeGraph):
    # Decision-ledger nodes are keyed by the full path but the cockpit audit
    # screen passes the slug/stem; resolution must match via the audit_id attr.
    dec = graph.add_node(
        NodeType.DECISION,
        "ledger:/home/u/.hermes/decisions/s1/0001-add-oauth.md",
        title="Add OAuth",
        attrs={"audit_id": "add-oauth"},
    )
    assert find_entity_node(graph, key="add-oauth") == dec.id
    # The full ledger: key also resolves directly.
    assert (
        find_entity_node(graph, key="/home/u/.hermes/decisions/s1/0001-add-oauth.md")
        == dec.id
    )


def test_render_is_inspectable(graph: KnowledgeGraph):
    ans = coding_query(graph, "calculator")
    text = ans.render()
    assert "GraphRAG (coding)" in text
    assert "sources" in text
