"""Observatory wiring seams — opt-in (``muse_OBSERVATORY`` / marker file).

Covers :func:`gateway.cockpit.observatory_metrics.enabled`, the module-level
seam helpers (``record_route_decision`` / ``record_query_activations``), the
chat-path seam in :mod:`gateway.cockpit.agent`, the GraphRAG query seam, and
the spec §3.2 ``node.activate`` coalescing. The binding rules under test:
disabled (the default) means **zero filesystem writes**, and the seams never
raise into their callers — even with a misconfigured collector.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from gateway.cockpit import observatory_metrics as om
from gateway.cockpit.agent import _record_route_decision


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("muse_OBSERVATORY", raising=False)
    om.reset_collector()
    yield tmp_path
    om.reset_collector()


HINT = {"kind": "chat", "escalate": False, "target": "direct_answer"}


def _observatory_files(home: Path) -> list[Path]:
    root = home / "observatory"
    return sorted(p for p in root.rglob("*") if p.is_file()) if root.exists() else []


def _tiny_graph():
    from hermes_cli.jarvis_prime.graphrag.graph import (
        EdgeType,
        KnowledgeGraph,
        NodeType,
    )

    g = KnowledgeGraph()
    a = g.add_node(NodeType.FILE, "gateway/cockpit/handlers.py", title="handlers.py")
    b = g.add_node(NodeType.FILE, "gateway/cockpit/server.py", title="server.py")
    g.add_edge(a.id, b.id, EdgeType.IMPORTS)
    return g


# ── disabled (the default): zero filesystem writes ───────────────────────────


def test_disabled_seam_helpers_write_nothing(home: Path) -> None:
    assert om.enabled() is False
    om.record_route_decision("t1", "local", "qwen", latency_ms=5)
    om.record_query_activations([("label-1", "key-1")])
    _record_route_decision(dict(HINT), "generator", 12)
    assert _observatory_files(home) == []


def test_disabled_graphrag_query_seam_writes_nothing(home: Path) -> None:
    from hermes_cli.jarvis_prime.graphrag import query as q

    graph = _tiny_graph()
    for answer in (
        q.local_query(graph, "handlers cockpit"),
        q.global_query(graph, "handlers cockpit"),
        q.coding_query(graph, "handlers cockpit"),
    ):
        assert answer.nodes  # the queries really hit — the seam was reachable
    assert not (home / "observatory").exists()


# ── enabled(): env flag and marker file ──────────────────────────────────────


@pytest.mark.parametrize("flag", ["1", "true", "TRUE", "yes", "Yes"])
def test_enabled_via_env_values(home: Path, monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
    monkeypatch.setenv("muse_OBSERVATORY", flag)
    assert om.enabled() is True


@pytest.mark.parametrize("flag", ["", "0", "no", "false", "off"])
def test_disabled_env_values(home: Path, monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
    monkeypatch.setenv("muse_OBSERVATORY", flag)
    assert om.enabled() is False


def test_enabled_via_marker_file_no_restart_needed(home: Path) -> None:
    assert om.enabled() is False
    marker = home / "observatory" / ".enabled"
    marker.parent.mkdir(parents=True)
    marker.write_text("", encoding="utf-8")
    assert om.enabled() is True  # re-statted per call, never cached forever
    marker.unlink()
    assert om.enabled() is False


# ── enabled: events recorded, rollups/ladder reflect them, ring advances ─────


def test_route_decision_seam_records_and_ladder_reflects(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("muse_OBSERVATORY", "1")
    before = om.get_collector().latest_seq()
    _record_route_decision(
        {"kind": "reasoning", "escalate": True, "target": "aos_council"},
        "generator",
        42,
    )
    collector = om.get_collector()
    assert collector.latest_seq() == before + 1  # stream ring advanced
    tiers = collector.ladder_rollup("1h")
    assert len(tiers) == 1
    assert tiers[0]["tier"] == "hosted"  # escalation → hosted preference
    assert tiers[0]["n"] == 1
    assert tiers[0]["p50_latency_ms"] == 42
    events, _, gap = collector.events_since(before)
    assert gap is False
    assert events[0][1] == "route.decision"
    assert "served=generator" in events[0][2]["reason"]


def test_route_decision_fallback_is_recorded_as_local(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("muse_OBSERVATORY", "1")
    _record_route_decision(dict(HINT), "turn_summary_fallback", 7)
    tiers = om.get_collector().ladder_rollup("1h")
    assert tiers[0]["tier"] == "local"  # fallback replies are served in-process


def test_query_activations_recorded_when_enabled_via_marker(home: Path) -> None:
    marker = home / "observatory" / ".enabled"
    marker.parent.mkdir(parents=True)
    marker.write_text("", encoding="utf-8")

    from hermes_cli.jarvis_prime.graphrag import query as q

    answer = q.local_query(_tiny_graph(), "handlers cockpit")
    assert answer.nodes

    collector = om.get_collector()
    weights = collector.activation_weights("1h")
    assert weights  # measured activations only — and now there are some
    assert all(k.startswith("c-") for k in weights)
    # Cluster ids come from the shared sha1 helper over the hit's node id.
    assert om.cluster_id(answer.nodes[0].id) in weights
    events, latest, gap = collector.events_since(0)
    assert latest >= 1 and gap is False  # stream ring advanced
    assert {e[1] for e in events} == {"node.activate"}
    assert all(e[2]["activation"] == "query" for e in events)
    # And the events were persisted to the JSONL day-ring.
    assert list((home / "observatory").glob("events-*.jsonl"))


def test_cluster_id_matches_handlers_observatory_hash(home: Path) -> None:
    # The hash is deliberately replicated (import cycle risk) — keep in sync.
    from gateway.cockpit.handlers_observatory import _cluster_id

    assert om.cluster_id("node-id-123") == _cluster_id("node-id-123")


# ── spec §3.2: node.activate coalesced to ≤ 10 events/s ─────────────────────


def test_node_activate_coalesces_to_ten_per_second(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed = om._now()
    monkeypatch.setattr(om, "_now", lambda: fixed)
    collector = om.get_collector()
    for i in range(25):
        collector.record_node_activate("label", node_id=f"n{i}", kind="query")
    _, latest, _ = collector.events_since(0)
    assert latest == 10  # the budget, not 25

    # Rolling into the next second flushes coalesced overflow (still ≤ 10/s).
    monkeypatch.setattr(om, "_now", lambda: fixed + timedelta(seconds=1))
    collector.record_node_activate("label", node_id="n-next", kind="query")
    _, latest, _ = collector.events_since(0)
    assert latest == 20  # 9 flushed overflow events + the new one


def test_node_activate_overflow_weight_is_coalesced_not_lost(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed = om._now()
    monkeypatch.setattr(om, "_now", lambda: fixed)
    collector = om.get_collector()
    # Same key throughout: overflow folds its weight into one pending event.
    for _ in range(12):
        collector.record_node_activate("c-hot", node_id="n1", weight=1.0)
    assert collector.activation_weights("1h") == {"c-hot": 10.0}
    monkeypatch.setattr(om, "_now", lambda: fixed + timedelta(seconds=1))
    collector.record_node_activate("c-hot", node_id="n1", weight=1.0)
    # 10 + (2 coalesced into one flushed event) + 1 = 13: nothing was dropped.
    assert collector.activation_weights("1h") == {"c-hot": 13.0}


# ── misconfigured collector: seams still never raise ─────────────────────────


def test_seams_never_raise_when_collector_misconfigured(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("muse_OBSERVATORY", "yes")
    # The observatory root is a *file*: every JSONL append must fail.
    (home / "observatory").write_text("not a directory", encoding="utf-8")
    om.reset_collector()
    om.record_route_decision("t1", "local", "qwen", latency_ms=5)
    om.record_query_activations([("label", "key")])
    _record_route_decision(dict(HINT), "generator", 3)

    from hermes_cli.jarvis_prime.graphrag import query as q

    answer = q.coding_query(_tiny_graph(), "handlers cockpit")
    assert answer.nodes  # the query itself is unharmed

    collector = om.get_collector()
    assert collector.io_errors >= 1  # writes degraded, counted honestly
    # In-memory recording still worked (degrade, don't drop reads).
    assert collector.rollup("1h")["collector"]["events_in_window"] >= 1
