"""Cockpit GraphRAG endpoints — contract adapters + handlers.

The handlers build a knowledge graph from a small fixture repo (pointed at via
``HERMES_REPO_ROOT``) and persist the cache under a tmp ``HERMES_HOME``, so the
test is hermetic and does not touch the developer's real graph.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.cockpit import contract, handlers
from gateway.cockpit.handlers import Request


# ── contract adapters (pure) ───────────────────────────────────────────


def test_graph_related_item_normalizes_kind_and_sources():
    item = {
        "kind": "decision",
        "node_type": "decision",
        "title": "Localization approach",
        "ref": "memory:abc",
        "relation": "cites",
        "source_backed": True,
        "sources": [{"uri": "docs/guide.md", "kind": "memory_source", "extra": "x"}],
    }
    out = contract.graph_related_item(item)
    assert out["kind"] == "DECISION"  # upper-cased enum constant
    assert out["sources"] == [{"uri": "docs/guide.md", "kind": "memory_source"}]
    assert out["relation"] == "cites"


def test_graph_related_item_defaults_unknown_kind_to_file():
    out = contract.graph_related_item({"kind": "mystery", "title": "x"})
    assert out["kind"] == "FILE"


def test_graph_answer_view_clamps_to_wire_fields():
    answer = {
        "mode": "coding",
        "question": "add function",
        "nodes": [{"id": "file:1", "type": "file", "title": "a.py", "key": "a.py", "attrs": {}}],
        "edges": [{"src": "file:1", "dst": "function:2", "type": "owns", "weight": 1}],
        "citations": [{"uri": "a.py", "kind": "repo"}],
        "communities": [],
    }
    out = contract.graph_answer_view(answer)
    assert out["mode"] == "coding"
    assert out["nodes"][0] == {"id": "file:1", "type": "file", "title": "a.py", "key": "a.py"}
    assert out["edges"][0] == {"src": "file:1", "dst": "function:2", "type": "owns"}
    assert out["citations"] == [{"uri": "a.py", "kind": "repo"}]


# ── handlers (build over a fixture repo) ────────────────────────────────


@pytest.fixture()
def fixture_env(tmp_path: Path, monkeypatch) -> Path:
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "calculator.py").write_text(
        "from pkg.helpers import clamp\n\n\ndef add(a, b):\n    return clamp(a + b)\n"
    )
    (repo / "pkg" / "helpers.py").write_text("def clamp(x):\n    return max(0, x)\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_calculator.py").write_text(
        "from pkg.calculator import add\n\ndef test_add():\n    assert add(1,2)==3\n"
    )
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("HERMES_REPO_ROOT", str(repo))
    return repo


def test_graph_build_then_query_and_related(fixture_env: Path):
    built = handlers.graph_build(Request("POST", "/v1/cockpit/graph/build"))
    assert built.status == 200
    assert built.payload["nodes"] > 0
    assert "saved" in built.payload

    # coding query returns a typed answer with citations.
    ans = handlers.graph_query(
        Request("GET", "/v1/cockpit/graph/query", query={"mode": "coding", "q": "add function"})
    )
    assert ans.status == 200
    assert ans.payload["mode"] == "coding"
    assert ans.payload["nodes"]
    assert ans.payload["citations"]

    # related for a file resolves and buckets items.
    rel = handlers.graph_related(
        Request("GET", "/v1/cockpit/graph/related", query={"node": "pkg/calculator.py"})
    )
    assert rel.status == 200
    assert rel.payload["related"]
    assert all(i["kind"] in contract.RELATED_KINDS for i in rel.payload["related"])


def test_graph_related_honest_empty_for_unknown_entity(fixture_env: Path):
    handlers.graph_build(Request("POST", "/v1/cockpit/graph/build"))
    rel = handlers.graph_related(
        Request("GET", "/v1/cockpit/graph/related", query={"job_id": "orc-nope"})
    )
    assert rel.status == 200
    assert rel.payload["related"] == []
