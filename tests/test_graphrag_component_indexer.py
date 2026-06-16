"""Tests for the GraphRAG component indexer.

Verifies that the M.U.S.E component registry becomes typed COMPONENT nodes with
OWNS edges to owner-module FILE nodes and CITES edges to DOCUMENT nodes, and that
the builder wires the indexer into the default build.
"""

from __future__ import annotations

from pathlib import Path

from hermes_cli.jarvis_prime.component_registry import load_registry
from hermes_cli.jarvis_prime.graphrag.builder import ALL_INDEXERS
from hermes_cli.jarvis_prime.graphrag.graph import (
    EdgeType,
    KnowledgeGraph,
    NodeType,
    node_id,
)
from hermes_cli.jarvis_prime.graphrag.indexers import (
    index_code,
    index_components,
    index_docs,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_component_indexer_adds_nodes_and_owns_and_cites_edges(tmp_path):
    # A tiny repo: a file a component owns + a doc it cites.
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "thing.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "thing.md").write_text("# Thing\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    reg = tmp_path / "registry.yaml"
    reg.write_text(
        "schema: muse.component_registry.v1\n"
        "components:\n"
        "  - id: thing\n"
        "    name: Thing\n"
        "    kind: runtime\n"
        "    owner_module: pkg/thing.py\n"
        "    risk_class: RC1\n"
        "    docs: [docs/thing.md]\n",
        encoding="utf-8",
    )

    g = KnowledgeGraph()
    index_code(g, tmp_path)
    index_docs(g, tmp_path)
    index_components(g, tmp_path, registry_path=reg)

    comp_id = node_id(NodeType.COMPONENT, "thing")
    assert comp_id in g.nodes
    assert g.nodes[comp_id].attrs["kind"] == "runtime"
    assert g.nodes[comp_id].attrs["risk_class"] == "RC1"

    file_id = node_id(NodeType.FILE, "pkg/thing.py")
    assert (comp_id, file_id, EdgeType.OWNS.value) in g.edges

    doc_id = node_id(NodeType.DOCUMENT, "docs/thing.md")
    assert (comp_id, doc_id, EdgeType.CITES.value) in g.edges


def test_index_components_over_real_registry_adds_all_components():
    # Loading the shipped registry adds one COMPONENT node per entry.
    g = KnowledgeGraph()
    index_components(g, _REPO_ROOT)
    for c in load_registry():
        assert node_id(NodeType.COMPONENT, c.id) in g.nodes


def test_missing_registry_is_best_effort(tmp_path):
    # A bad registry path never aborts the build — graph is returned unchanged.
    g = KnowledgeGraph()
    index_components(g, tmp_path, registry_path=tmp_path / "nope.yaml")
    assert not any(
        n.type == NodeType.COMPONENT for n in g.nodes.values()
    )


def test_builder_registers_components_indexer():
    assert "components" in ALL_INDEXERS
    # components must run after docs so DOCUMENT endpoints exist for CITES edges.
    assert ALL_INDEXERS.index("components") > ALL_INDEXERS.index("docs")
