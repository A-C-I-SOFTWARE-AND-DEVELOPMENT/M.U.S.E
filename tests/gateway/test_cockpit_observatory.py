"""Neural Observatory route family (``/v1/observatory/*``) + metrics collector.

Unit tests cover :mod:`gateway.cockpit.observatory_metrics` (recording,
JSONL ring persistence, measured-only rollups, the n-below-threshold
``heat: null`` honesty rule) and the handlers' empty-state honesty; one
hermetic integration block exercises bearer auth and the SSE stream
handshake against a live loopback server.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

import gateway.cockpit.server as server_mod
from gateway.cockpit import handlers as h
from gateway.cockpit import observatory_metrics as om

TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    om.reset_collector()
    yield tmp_path
    om.reset_collector()


# ── unit: the collector ──────────────────────────────────────────────────────


def test_collector_records_and_persists_jsonl(home: Path) -> None:
    collector = om.get_collector()
    collector.record_job_stage("jb1", "worker", task_class="code", stage_latency_ms=120)
    collector.record_gate_verdict("jb1", "test", "pass", task_class="code")

    files = list((home / "observatory").glob("events-*.jsonl"))
    assert len(files) == 1
    records = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
    assert [r["kind"] for r in records] == ["job.stage", "gate.verdict"]
    assert records[0]["job_id"] == "jb1"
    assert all("ts" in r for r in records)

    # A fresh collector re-seeds its in-memory rollups from the JSONL ring.
    om.reset_collector()
    reloaded = om.get_collector()
    rollup = reloaded.rollup("1h")
    assert rollup["stages"][0]["count"] == 1
    assert rollup["gates"][0]["passes"] == 1


def test_collector_emit_never_raises_on_io_failure(home: Path) -> None:
    # Point the ring at a path that cannot be a directory (a file) — emits
    # must degrade to counted io errors, never an exception into the caller.
    blocker = home / "observatory"
    blocker.write_text("not a directory", encoding="utf-8")
    collector = om.ObservatoryCollector(blocker)
    collector.record_queue_depth(3)
    assert collector.io_errors >= 1
    # The in-memory rollup still saw the event (degrade, don't drop reads).
    assert collector.rollup("1h")["collector"]["events_in_window"] == 1


def test_rollup_empty_state_is_honest(home: Path) -> None:
    rollup = om.get_collector().rollup("1h")
    assert rollup["stages"] == []
    assert rollup["gates"] == []
    assert rollup["models"] == []
    assert rollup["heat"] == []
    assert rollup["collector"]["events_in_window"] == 0


def test_heat_is_null_below_min_n_and_measured_above(home: Path) -> None:
    collector = om.get_collector()
    # One gate verdict: n=1 < MIN_HEAT_N -> heat must be null, n reported.
    collector.record_gate_verdict("jb1", "test", "fail", task_class="code")
    # MIN_HEAT_N stage events -> heat must be a measured number in [0, 1].
    for i in range(om.MIN_HEAT_N):
        collector.record_job_stage(
            "jb2", "worker", task_class="code", stage_latency_ms=1000 + i
        )
    heat = {entry["key"]: entry for entry in collector.rollup("1h")["heat"]}
    gate = heat["gate:test:code"]
    assert gate["score"] is None
    assert gate["n"] == 1
    stage = heat["stage:worker:code"]
    assert stage["score"] is not None
    assert 0.0 <= stage["score"] <= 1.0
    assert stage["n"] == om.MIN_HEAT_N
    assert stage["evidence_ref"].startswith("/v1/cockpit/ledger?")


def test_events_since_supports_replay_and_gap(home: Path) -> None:
    collector = om.get_collector()
    collector.record_route_decision("t1", "local", "qwen", latency_ms=10)
    collector.record_route_decision("t2", "hosted", "claude", latency_ms=20)
    events, latest, gap = collector.events_since(0)
    assert [e[1] for e in events] == ["route.decision", "route.decision"]
    assert latest == 2
    assert gap is False
    # Resuming from the latest seq yields nothing new.
    more, _, gap = collector.events_since(latest)
    assert more == []
    assert gap is False


# ── handlers: empty-state honesty ────────────────────────────────────────────


def test_snapshot_empty_state(home: Path) -> None:
    res = h.observatory_snapshot(h.Request(method="GET", path="x"))
    assert res.status == 200
    body = res.payload
    assert body["v"] == 1
    # No graph cache built -> the documented unavailable shape, no fake clusters.
    assert body["graph"]["status"] == "unavailable"
    assert body["stations"]["nodes"] == ["job", "navigator", "worker", "gate", "ledger"]
    assert body["stations"]["active_jobs"] == []
    assert body["ladder"]["tiers"] == []
    assert body["metrics_rollup"]["stages"] == []


def test_metrics_happy_path_uses_recorded_events(home: Path) -> None:
    collector = om.get_collector()
    collector.record_model_call(
        "local", "qwen", 800, tokens_in=10, tokens_out=4, task_class="code"
    )
    res = h.observatory_metrics(h.Request(method="GET", path="x", query={"window": "1h"}))
    assert res.status == 200
    assert res.payload["window"] == "1h"
    models = res.payload["models"]
    assert len(models) == 1
    assert models[0]["calls"] == 1
    assert models[0]["tokens_in"] == 10
    assert res.payload["heat_weights"] == om.HEAT_WEIGHTS


def test_metrics_rejects_bad_window(home: Path) -> None:
    res = h.observatory_metrics(h.Request(method="GET", path="x", query={"window": "2h"}))
    assert res.status == 400
    assert res.payload["error"] == "bad_request"
    assert "window" in res.payload["detail"]


def test_layout_requires_cluster_param(home: Path) -> None:
    res = h.observatory_layout(h.Request(method="GET", path="x"))
    assert res.status == 400
    assert res.payload["error"] == "bad_request"


def test_layout_unavailable_without_graph_cache(home: Path) -> None:
    res = h.observatory_layout(
        h.Request(method="GET", path="x", query={"cluster": "c-12345678"})
    )
    assert res.status == 200
    assert res.payload["status"] == "unavailable"


# ── handlers: graph-backed snapshot + layout over a real (small) graph ───────


def _seed_graph(home: Path) -> None:
    from hermes_cli.jarvis_prime.graphrag import GraphStore
    from hermes_cli.jarvis_prime.graphrag.graph import (
        EdgeType,
        KnowledgeGraph,
        NodeType,
    )

    g = KnowledgeGraph()
    a = g.add_node(
        NodeType.FILE,
        "gateway/cockpit/handlers.py",
        title="handlers.py",
        sources=[{"uri": "gateway/cockpit/handlers.py", "kind": "repo"}],
    )
    b = g.add_node(
        NodeType.FILE,
        "gateway/cockpit/server.py",
        title="server.py",
        sources=[{"uri": "gateway/cockpit/server.py", "kind": "repo"}],
    )
    c = g.add_node(NodeType.DOCUMENT, "docs/a.md", title="a.md")
    d = g.add_node(NodeType.DOCUMENT, "docs/b.md", title="b.md")
    g.add_edge(a.id, b.id, EdgeType.IMPORTS)
    g.add_edge(c.id, d.id, EdgeType.CITES)
    GraphStore().save(g)


def test_snapshot_and_layout_over_real_graph(home: Path) -> None:
    _seed_graph(home)
    res = h.observatory_snapshot(h.Request(method="GET", path="x"))
    assert res.status == 200
    graph = res.payload["graph"]
    assert graph["node_count"] == 4
    assert graph["edge_count"] == 2
    assert len(graph["clusters"]) == 2
    for cluster in graph["clusters"]:
        assert cluster["members"] == 2
        # Layout engine wired in: real computed positions, in-box, with radius.
        assert isinstance(cluster["pos"], list) and len(cluster["pos"]) == 3
        assert all(abs(c) <= 100.0 for c in cluster["pos"])
        assert cluster["radius"] > 0
        assert cluster["heat"] is None  # no measured activations yet
        assert sum(cluster["type_mix"].values()) == pytest.approx(1.0)
    assert graph["layout_status"] == "computed"
    assert graph["layout_algo"] in {"fr3d", "nx-spring"}

    cid = graph["clusters"][0]["id"]
    res = h.observatory_layout(
        h.Request(method="GET", path="x", query={"cluster": cid})
    )
    assert res.status == 200
    assert res.payload["cluster"] == cid
    assert res.payload["truncated"] is False
    assert res.payload["layout_status"] == "computed"
    assert res.payload["layout_algo"] == "radial-refined"
    assert len(res.payload["nodes"]) == 2
    assert all(
        isinstance(n["pos"], list) and len(n["pos"]) == 3
        for n in res.payload["nodes"]
    )
    assert len(res.payload["edges"]) == 1

    # limit caps members (top-degree first) and reports truncation honestly.
    res = h.observatory_layout(
        h.Request(method="GET", path="x", query={"cluster": cid, "limit": "1"})
    )
    assert res.payload["truncated"] is True
    assert len(res.payload["nodes"]) == 1


def test_layout_unknown_cluster_404(home: Path) -> None:
    _seed_graph(home)
    res = h.observatory_layout(
        h.Request(method="GET", path="x", query={"cluster": "c-ffffffff"})
    )
    assert res.status == 404
    assert res.payload["error"] == "unknown_cluster"


def test_cluster_heat_from_measured_activations_only(home: Path) -> None:
    _seed_graph(home)
    first = h.observatory_snapshot(h.Request(method="GET", path="x"))
    cid = first.payload["graph"]["clusters"][0]["id"]
    om.get_collector().record_node_activate(cid, kind="query", weight=2.0)
    res = h.observatory_snapshot(h.Request(method="GET", path="x"))
    heats = {c["id"]: c["heat"] for c in res.payload["graph"]["clusters"]}
    assert heats[cid] == 1.0  # normalized share of measured activation weight
    other = next(k for k in heats if k != cid)
    assert heats[other] is None  # untouched cluster stays honestly null


# ── integration: live server (auth + SSE handshake) ─────────────────────────


@pytest.fixture()
def server(home: Path):
    srv = server_mod.serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _get(server, path: str, *, token: str | None = TOKEN):
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}{path}", method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


@pytest.mark.parametrize(
    "path",
    [
        "/v1/observatory/snapshot",
        "/v1/observatory/metrics",
        "/v1/observatory/layout?cluster=c-1",
        "/v1/observatory/stream",
    ],
)
def test_observatory_routes_require_bearer(server, path: str) -> None:
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}{path}", method="GET")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 401


def test_snapshot_and_metrics_over_http(server, home: Path) -> None:
    status, body = _get(server, "/v1/observatory/snapshot")
    assert status == 200
    assert body["v"] == 1
    assert "stations" in body and "ladder" in body

    status, body = _get(server, "/v1/observatory/metrics?window=15m")
    assert status == 200
    assert body["window"] == "15m"
    assert body["stages"] == []  # nothing recorded -> honestly empty


def test_observatory_stream_handshake_and_delivery(
    server, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server_mod, "_SSE_POLL_S", 0.05)
    monkeypatch.setattr(server_mod, "_SSE_HEARTBEAT_S", 0.2)

    host, port = server.server_address
    req = urllib.request.Request(
        f"http://{host}:{port}/v1/observatory/stream", method="GET"
    )
    req.add_header("Authorization", f"Bearer {TOKEN}")
    resp = urllib.request.urlopen(req, timeout=5)
    try:
        assert resp.headers.get("Content-Type", "").startswith("text/event-stream")
        # Emit AFTER connecting — the stream tails from "now" forward.
        om.get_collector().record_job_stage("jb-sse", "worker", task_class="code")
        event = None
        event_id = None
        for _ in range(200):
            raw = resp.readline()
            if not raw:
                break
            line = raw.decode("utf-8").rstrip("\r\n")
            if line.startswith("id: "):
                event_id = line[len("id: "):]
            elif line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: ") and event == "job.stage":
                data = json.loads(line[len("data: "):])
                if data.get("job_id") == "jb-sse":
                    assert data["stage"] == "worker"
                    assert "ts" in data
                    assert event_id is not None and int(event_id) >= 1
                    return
        pytest.fail("job.stage event was not delivered on the observatory stream")
    finally:
        resp.close()
