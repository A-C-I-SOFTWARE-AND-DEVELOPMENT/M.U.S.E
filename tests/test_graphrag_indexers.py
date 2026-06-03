"""Tests for the GraphRAG indexers and builder against a small repo fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.graphrag.builder import build_graph
from hermes_cli.jarvis_prime.graphrag.graph import EdgeType, KnowledgeGraph, NodeType, node_id
from hermes_cli.jarvis_prime.graphrag.indexers import (
    index_code,
    index_docs,
    index_evidence,
    index_ledger,
    index_memory,
)


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "calculator.py").write_text(
        "from pkg.helpers import clamp\n\n\n"
        "def add(a, b):\n    return clamp(a + b)\n\n\n"
        "class Calculator:\n    def total(self, items):\n        return sum(items)\n"
    )
    (tmp_path / "pkg" / "helpers.py").write_text(
        "def clamp(x):\n    return max(0, x)\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calculator.py").write_text(
        "from pkg.calculator import add, Calculator\n\n"
        "def test_add():\n    assert add(1, 2) == 3\n"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text(
        "# Guide\n\nThe adder lives in pkg/calculator.py and clamps via pkg/helpers.py.\n"
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    return tmp_path


def test_code_indexer_builds_files_symbols_and_edges(sample_repo: Path):
    g = KnowledgeGraph()
    index_code(g, sample_repo)

    # FILE nodes exist for source + test files.
    assert node_id(NodeType.FILE, "pkg/calculator.py") in g.nodes
    assert node_id(NodeType.FILE, "tests/test_calculator.py") in g.nodes

    # FUNCTION / CLASS nodes from the python AST.
    add_fn = node_id(NodeType.FUNCTION, "pkg/calculator.py::add")
    calc_cls = node_id(NodeType.CLASS, "pkg/calculator.py::Calculator")
    assert add_fn in g.nodes
    assert calc_cls in g.nodes

    # OWNS edge: file owns its defs.
    file_id = node_id(NodeType.FILE, "pkg/calculator.py")
    owns = [e for e in g.out_edges(file_id) if e.type == EdgeType.OWNS]
    assert {e.dst for e in owns} >= {add_fn, calc_cls}

    # IMPORTS / DEPENDS_ON: calculator imports helpers.
    helpers_id = node_id(NodeType.FILE, "pkg/helpers.py")
    dep_edges = [e for e in g.in_edges(helpers_id) if e.type == EdgeType.DEPENDS_ON]
    assert any(e.src == file_id for e in dep_edges)

    # TESTS edge: the test file tests calculator.py.
    test_id = node_id(NodeType.FILE, "tests/test_calculator.py")
    tests_edges = [e for e in g.out_edges(test_id) if e.type == EdgeType.TESTS]
    assert any(e.dst == file_id for e in tests_edges)

    # CALLS edge: add() calls clamp() defined in helpers.
    clamp_fn = node_id(NodeType.FUNCTION, "pkg/helpers.py::clamp")
    calls = [e for e in g.out_edges(add_fn) if e.type == EdgeType.CALLS]
    assert any(e.dst == clamp_fn for e in calls)

    # Every node/edge is source-backed (provenance present).
    assert all(n.sources for n in g.nodes.values())
    assert all(e.sources for e in g.edges.values())


def test_docs_indexer_cites_referenced_files(sample_repo: Path):
    g = KnowledgeGraph()
    index_code(g, sample_repo)
    index_docs(g, sample_repo)
    doc_id = node_id(NodeType.DOCUMENT, "docs/guide.md")
    assert doc_id in g.nodes
    cites = [e for e in g.out_edges(doc_id) if e.type == EdgeType.CITES]
    cited_keys = {g.nodes[e.dst].key for e in cites}
    assert "pkg/calculator.py" in cited_keys
    assert "pkg/helpers.py" in cited_keys


def test_evidence_indexer_links_repo_files(sample_repo: Path, tmp_path: Path):
    from hermes_cli.jarvis_prime.research_vault import (
        EvidenceStrength,
        ResearchVault,
        SourceType,
    )

    vault = ResearchVault(path=tmp_path / "vault.jsonl")
    vault.add(
        "Clamp design note",
        "pkg/helpers.py",
        source_type=SourceType.REPO,
        evidence_strength=EvidenceStrength.PRIMARY,
        excerpt="clamp keeps values non-negative",
        persist=False,
    )
    g = KnowledgeGraph()
    index_code(g, sample_repo)
    index_evidence(g, vault=vault)

    source_nodes = [n for n in g.nodes.values() if n.type == NodeType.SOURCE]
    assert source_nodes
    # The source cites the helpers file.
    helpers_id = node_id(NodeType.FILE, "pkg/helpers.py")
    cites = [e for e in g.in_edges(helpers_id) if e.type == EdgeType.CITES]
    assert cites


def test_memory_indexer_makes_decisions_and_contradictions(tmp_path: Path):
    from hermes_cli.jarvis_prime.memory_tree import (
        MemoryLayer,
        MemorySource,
        MemoryTreeStore,
        SourceTrust,
    )

    store = MemoryTreeStore(path=tmp_path / "mem.jsonl")
    res = store.write(
        "We chose deterministic localization over LLM guessing.",
        namespace="project",
        title="Localization approach",
        layer=MemoryLayer.DURABLE,
        sources=[MemorySource(uri="docs/guide.md", trust=SourceTrust.PRIMARY)],
        source_uri="docs/guide.md",
        confidence=0.9,
        owner_approved=True,
        persist=False,
    )
    assert res.ok, res.reasons

    g = KnowledgeGraph()
    index_memory(g, store=store)
    decisions = [n for n in g.nodes.values() if n.type == NodeType.DECISION]
    assert decisions
    # The decision cites its source.
    dec = decisions[0]
    cites = [e for e in g.out_edges(dec.id) if e.type == EdgeType.CITES]
    assert cites


def test_ledger_indexer_links_task_to_files(sample_repo: Path):
    g = KnowledgeGraph()
    index_code(g, sample_repo)
    injected = {
        "orc-test01": [
            {"kind": "submit", "prompt": "fix the adder"},
            {
                "kind": "navigation_decision",
                "ranked_files": [{"path": "pkg/calculator.py", "rank": 1}],
                "verify_with": ["tests/test_calculator.py"],
            },
            {"kind": "worker_dispatch", "worker_id": "hermes-local-planner", "model": "test-model"},
        ]
    }
    index_ledger(g, ledger=injected)
    task_id = node_id(NodeType.TASK, "orc-test01")
    assert task_id in g.nodes
    deps = [e for e in g.out_edges(task_id) if e.type == EdgeType.DEPENDS_ON]
    file_id = node_id(NodeType.FILE, "pkg/calculator.py")
    assert any(e.dst == file_id for e in deps)
    # Worker + model nodes wired.
    assert node_id(NodeType.WORKER, "hermes-local-planner") in g.nodes
    assert node_id(NodeType.MODEL, "test-model") in g.nodes


def test_builder_runs_selected_indexers(sample_repo: Path, monkeypatch):
    # Only the code + docs indexers (no local stores needed).
    g = build_graph(sample_repo, indexers=["code", "docs"])
    s = g.stats()
    assert s["nodes"] > 0
    assert "file" in s["by_node_type"]
    assert "document" in s["by_node_type"]
