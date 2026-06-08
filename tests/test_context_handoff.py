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
from hermes_cli.jarvis_prime.graphrag.graph import (
    EdgeType,
    KnowledgeGraph,
    NodeType,
)
from hermes_cli.jarvis_prime.graphrag.indexers import index_code, index_docs
from hermes_cli.jarvis_prime.graphrag.store import GraphStore

# A secret-shaped token that ``secrets_policy.redact`` reliably replaces with a
# ``<redacted:github_pat>`` sentinel (``ghp_`` + 36 chars). Used to prove that
# graph-derived strings are screened on the way into the handoff packet.
_PLANTED_SECRET = "ghp_" + "a" * 36


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


# --- FU-24: graph-derived content is secret-screened on the way in ----------


def _poisoned_store(tmp_path: Path) -> GraphStore:
    """A graph whose node titles/refs and provenance URIs carry a planted
    secret, so we can prove they're redacted before entering the packet.

    Nodes also share the query term ``calculator`` so they surface in both the
    coding answer and a global-query community (whose ``top_titles`` feed the
    architecture summary).
    """
    # The secret sits as its own path segment / token (after a ``/`` or space),
    # i.e. exactly where a real leaked credential would be — and where the
    # redactor's word-boundary detection actually fires.
    g = KnowledgeGraph()
    code = g.add_node(
        NodeType.FILE,
        # ref/key carries the secret …
        f"src/calculator/{_PLANTED_SECRET}.py",
        # … and so does the human title …
        title=f"calculator helper {_PLANTED_SECRET}",
        # … and the provenance URI rendered under "## sources".
        sources=[{"kind": "repo", "uri": f"src/calculator/{_PLANTED_SECRET}.py"}],
    )
    decision = g.add_node(
        NodeType.DECISION,
        f"decision/calculator/{_PLANTED_SECRET}",
        title=f"adopt calculator approach {_PLANTED_SECRET}",
        sources=[{"kind": "ledger", "uri": f"ledger/calculator/{_PLANTED_SECRET}.jsonl"}],
    )
    # An edge makes the two nodes a community for global_query.
    g.add_edge(code.id, decision.id, EdgeType.DEPENDS_ON)
    store = GraphStore(tmp_path / "poisoned.json")
    store.save(g)
    return store


def test_graph_derived_titles_and_refs_are_redacted(tmp_path, monkeypatch):
    """A secret planted in node titles/refs never reaches the rendered packet
    or its dict form — only the ``<redacted:…>`` sentinel does."""
    _clean_home(tmp_path, monkeypatch)
    store = _poisoned_store(tmp_path)
    h = build_context_handoff("calculator", store=store, token_budget=4096)
    assert h.graph_built is True

    rendered = h.render()
    payload = json.dumps(h.to_dict())
    # The raw secret is gone from every surface; the sentinel is present.
    assert _PLANTED_SECRET not in rendered
    assert _PLANTED_SECRET not in payload
    assert "<redacted:github_pat>" in rendered
    # Specifically the node-view fields (relevant_files / graph_nodes) are clean.
    for view in h.relevant_files + h.graph_nodes + h.prior_decisions:
        assert _PLANTED_SECRET not in view["title"]
        assert _PLANTED_SECRET not in view["ref"]


def test_graph_citation_uri_is_redacted(tmp_path, monkeypatch):
    """A secret planted in a citation's provenance URI is screened before the
    citation enters the packet (citations are graph-derived dicts)."""
    _clean_home(tmp_path, monkeypatch)
    store = _poisoned_store(tmp_path)
    h = build_context_handoff("calculator", store=store, token_budget=4096)
    assert h.citations  # the poisoned node is source-backed
    for c in h.citations:
        assert _PLANTED_SECRET not in c.get("uri", "")
        assert _PLANTED_SECRET not in c.get("kind", "")
    # And in the rendered "## sources" block.
    assert _PLANTED_SECRET not in h.render()


def test_architecture_summary_is_redacted(tmp_path, monkeypatch):
    """A secret in a community's top node title is screened in the rendered
    architecture summary (global_query feeds ``architecture_summary``)."""
    _clean_home(tmp_path, monkeypatch)
    store = _poisoned_store(tmp_path)
    h = build_context_handoff("calculator", store=store, token_budget=4096)
    # The summary should actually be populated (community surfaced) …
    assert h.architecture_summary
    # … and carry no raw secret.
    for line in h.architecture_summary:
        assert _PLANTED_SECRET not in line


def test_redaction_does_not_change_round_trip_for_clean_graph(tmp_path, monkeypatch):
    """Screening is a no-op for secret-free graph content: the existing
    built-graph behavior (refs/tests buckets, citations) is unchanged."""
    _clean_home(tmp_path, monkeypatch)
    store = _built_store(tmp_path)
    h = build_context_handoff("add function in calculator", store=store)
    refs = {f["ref"] for f in h.relevant_files}
    assert any("calculator.py" in r for r in refs)
    assert any("test_calculator.py" in t["ref"] for t in h.related_tests)
    assert all("test_calculator.py" not in r for r in refs)
    assert h.citations
    # No sentinel appears when there's nothing to redact.
    assert "<redacted:" not in h.render()


def test_node_view_never_raises_on_malformed_node():
    """``_node_view`` redacts but never raises, even on non-string title/key."""
    from hermes_cli.jarvis_prime.context_handoff import _node_view

    class _FakeType:
        value = "file"

    class _BadNode:
        type = _FakeType()
        title = None  # not a string
        key = 12345  # not a string
        sources: list = []

    view = _node_view(_BadNode())
    assert view["type"] == "file"
    # Malformed values pass through untouched rather than blowing up.
    assert view["title"] is None
    assert view["ref"] == 12345


def test_redact_citation_never_raises_on_malformed_input():
    """``_redact_citation`` tolerates non-dict / non-string fields."""
    from hermes_cli.jarvis_prime.context_handoff import _redact_citation

    # Non-dict input is returned unchanged.
    assert _redact_citation("not-a-dict") == "not-a-dict"
    assert _redact_citation(None) is None
    # Dict with a mix of string and non-string values: strings screened,
    # others preserved, shape intact.
    out = _redact_citation(
        {"uri": f"x/{_PLANTED_SECRET}", "kind": "repo", "line": 7, "tags": ["a"]}
    )
    assert _PLANTED_SECRET not in out["uri"]
    assert out["kind"] == "repo"
    assert out["line"] == 7
    assert out["tags"] == ["a"]


def test_build_context_handoff_never_raises_on_broken_graph(tmp_path, monkeypatch):
    """If the graph query path explodes mid-flight, the packet still builds —
    the failure is a note, not an exception (never-raises preserved)."""
    _clean_home(tmp_path, monkeypatch)
    store = _built_store(tmp_path)
    import hermes_cli.jarvis_prime.graphrag as graphrag

    def _boom(*_args, **_kwargs):
        raise RuntimeError("graph query exploded")

    # Patch where context_handoff imports it from (the package namespace).
    monkeypatch.setattr(graphrag, "coding_query", _boom)
    h = build_context_handoff("calculator add", store=store)
    assert isinstance(h, ContextHandoff)
    assert any("graph context unavailable" in n for n in h.notes)
