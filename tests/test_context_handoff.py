"""Tests for the local-first context handoff packet.

Hermetic: a tiny on-disk repo fixture is indexed into a tmp GraphStore; no
network, no real providers. ``HERMES_HOME`` is pointed at a tmpdir so the lane
recommendation reads the default policy, not the host's.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

from hermes_cli.jarvis_prime.context_handoff import (
    ContextHandoff,
    build_context_handoff,
)
from hermes_cli.jarvis_prime.graphrag.graph import KnowledgeGraph
from hermes_cli.jarvis_prime.graphrag.indexers import index_code, index_docs
from hermes_cli.jarvis_prime.graphrag.store import GraphStore


def _clean_home(tmp_path, monkeypatch) -> None:
    """Point HERMES_HOME at a clean tmpdir so routing reads the default policy."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))


def _built_store(tmp_path: Path) -> GraphStore:
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "calculator.py").write_text(
        "def add(a, b):\n    return a + b\n\n\nclass Calculator:\n    pass\n"
    )
    (repo / "tests").mkdir()
    (repo / "tests" / "test_calculator.py").write_text(
        "from pkg.calculator import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    (repo / "docs").mkdir()
    (repo / "docs" / "calc.md").write_text(
        "# Calc\n\nThe add function lives in pkg/calculator.py.\n"
    )
    g = KnowledgeGraph()
    index_code(g, repo)
    index_docs(g, repo)
    store = GraphStore(tmp_path / "graph.json")
    store.save(g)
    return store


def test_context_packet_builds_offline_without_graph(tmp_path, monkeypatch):
    """No graph + build_if_missing=False → honest-empty, non-crashing, lane present."""
    _clean_home(tmp_path, monkeypatch)
    store = GraphStore(tmp_path / "missing.json")  # nothing saved
    h = build_context_handoff("add a retry helper", store=store, build_if_missing=False)
    assert isinstance(h, ContextHandoff)
    assert h.graph_built is False
    assert h.relevant_files == [] and h.graph_nodes == []
    # The lane recommendation + verification plan still resolve (degraded-safe).
    assert h.model_lane.get("route_tier")
    assert h.verification_plan
    assert any("graph not built" in n for n in h.notes)


def test_context_packet_with_built_graph(tmp_path, monkeypatch):
    _clean_home(tmp_path, monkeypatch)
    store = _built_store(tmp_path)
    h = build_context_handoff("add function in calculator", store=store)
    assert h.graph_built is True
    refs = {f["ref"] for f in h.relevant_files}
    assert any("calculator.py" in r for r in refs)
    # Its test is surfaced in the tests bucket, not the files bucket.
    assert any("test_calculator.py" in t["ref"] for t in h.related_tests)
    assert all("test_calculator.py" not in r for r in refs)
    # Source-backed citations.
    assert h.citations


def test_context_render_and_to_dict(tmp_path, monkeypatch):
    _clean_home(tmp_path, monkeypatch)
    store = _built_store(tmp_path)
    h = build_context_handoff("calculator add", store=store)
    text = h.render()
    assert isinstance(text, str) and "Context handoff" in text
    d = h.to_dict()
    assert set(d) >= {
        "request",
        "model_lane",
        "verification_plan",
        "graph_nodes",
        "graph_built",
    }


def test_context_unknown_task_class_is_noted(tmp_path, monkeypatch):
    _clean_home(tmp_path, monkeypatch)
    store = GraphStore(tmp_path / "missing.json")
    h = build_context_handoff("x", store=store, task_class="not_a_lane")
    assert any("unknown task class" in n for n in h.notes)
    assert h.model_lane == {}


def test_context_token_budget_clamps_render(tmp_path, monkeypatch):
    _clean_home(tmp_path, monkeypatch)
    store = _built_store(tmp_path)
    h = build_context_handoff("calculator add", store=store, token_budget=1)
    # Clamp invariant: render never exceeds max(256, budget*4) + a short marker.
    assert len(h.render()) <= max(256, h.token_budget * 4) + 64


def test_cli_context_json_returns_zero(tmp_path, monkeypatch):
    _clean_home(tmp_path, monkeypatch)
    from hermes_cli.jarvis_prime.__main__ import main

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["context", "add a retry helper", "--json"])
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert "model_lane" in payload and "verification_plan" in payload
    assert payload["graph_built"] is False  # no graph in a clean HERMES_HOME


def test_is_test_path_aware_avoids_false_positives():
    from hermes_cli.jarvis_prime.context_handoff import _is_test

    assert _is_test("tests/test_x.py", "test_x")
    assert _is_test("pkg/foo_test.py", "foo_test")
    assert _is_test("conftest.py", "conftest")
    # Path-aware: these contain the substring "test" but are not tests.
    assert not _is_test("pkg/latest.py", "latest")
    assert not _is_test("docs/attestation.md", "attestation")
    assert not _is_test("pkg/contest.py", "contest")
