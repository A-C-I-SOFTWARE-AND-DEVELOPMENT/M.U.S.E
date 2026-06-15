"""Tests for the fused action stream ``GET /v1/observatory/actions``.

Unit tests cover ``gateway.cockpit.action_fusion`` (the read-only multiplexer +
its mappers); hermetic integration tests open the live SSE and assert that an
event recorded into *each* real source (collector, flywheel, cockpit event log,
axiom chain) is delivered exactly once with the right fused ``kind`` — and that
the stream is dormant (503) when the observatory collector is opt-out.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import gateway.cockpit.server as server_mod
from gateway.cockpit import action_fusion as af
from gateway.cockpit import event_log
from gateway.cockpit import observatory_metrics as om

TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    om.reset_collector()
    yield tmp_path
    om.reset_collector()


@pytest.fixture()
def server(home: Path):
    srv = server_mod.serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _open_stream(server, path: str, *, last_event_id: str | None = None):
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}{path}", method="GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    if last_event_id is not None:
        req.add_header("Last-Event-ID", last_event_id)
    return urllib.request.urlopen(req, timeout=5)


def _read_until(resp, predicate, max_lines: int = 400):
    """Return ``(event, data, last_id)`` for the first frame matching predicate."""
    event = None
    last_id = None
    for _ in range(max_lines):
        raw = resp.readline()
        if not raw:
            return None
        line = raw.decode("utf-8").rstrip("\r\n")
        if line.startswith("id: "):
            last_id = line[len("id: "):]
        elif line.startswith("event: "):
            event = line[len("event: "):]
        elif line.startswith("data: "):
            data = json.loads(line[len("data: "):])
            if event is not None and predicate(event, data):
                return event, data, last_id
            event = None
    return None


def _fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server_mod, "_SSE_POLL_S", 0.05)
    monkeypatch.setattr(server_mod, "_SSE_HEARTBEAT_S", 0.2)


# ── unit: multiplexer ───────────────────────────────────────────────────────


def test_kinds_vocabulary_is_frozen() -> None:
    # Native renderers (Android GL, UE5) pin this closed set — drift is a
    # deliberate, reviewed change, not an accident.
    assert af.KINDS == (
        "cluster.spark", "pipeline.packet", "gate.flare", "ladder.streak",
        "owner.pulse", "agent.pulse", "skill.pulse", "system.pulse",
        "audit.flare", "meta.resync",
    )


def test_tail_jsonl_consumes_only_complete_lines(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    path.write_text('{"a":1}\n{"a":2}\n{"a":3', encoding="utf-8")  # last line partial
    recs, off = af._tail_jsonl(path, 0)
    assert [r["a"] for r in recs] == [1, 2]
    # The partial line is left for next time; appending its newline completes it.
    path.write_text('{"a":1}\n{"a":2}\n{"a":3}\n', encoding="utf-8")
    recs2, _ = af._tail_jsonl(path, off)
    assert [r["a"] for r in recs2] == [3]


def test_mappers_drop_unknown_and_map_known() -> None:
    assert af._map_collector("queue.depth", {"depth": 3}) is None  # unmapped → dropped
    spark = af._map_collector("node.activate", {"cluster_id": "c1", "weight": 0.5})
    assert spark["kind"] == "cluster.spark" and spark["target"] == {"cluster_id": "c1"}
    assert spark["weight"] == 0.5
    flare = af._map_collector("gate.verdict", {"job_id": "j1", "gate": "build", "verdict": "fail"})
    assert flare["kind"] == "gate.flare" and flare["severity"] == "error"
    assert af._map_flywheel({"kind": "nope", "payload": {}}) is None
    pulse = af._map_flywheel({"kind": "agent.action", "payload": {}, "outcome": "failure"})
    assert pulse["kind"] == "agent.pulse" and pulse["severity"] == "error"


# ── integration: auth + dormant honesty ─────────────────────────────────────


def test_actions_stream_requires_auth(server) -> None:
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}/v1/observatory/actions")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 401


def test_actions_stream_dormant_when_collector_disabled(
    server, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No MUSE_OBSERVATORY and no .enabled file ⇒ collector opt-out ⇒ 503, and
    # the stream touches no source files (no fabricated feed).
    monkeypatch.delenv("MUSE_OBSERVATORY", raising=False)
    with pytest.raises(urllib.error.HTTPError) as exc:
        _open_stream(server, "/v1/observatory/actions")
    assert exc.value.code == 503
    assert not (home / "observatory").exists()


# ── integration: every source fuses, exactly once ───────────────────────────


def test_actions_stream_fuses_each_source(
    server, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fast(monkeypatch)
    monkeypatch.setenv("MUSE_OBSERVATORY", "1")
    monkeypatch.setenv("MUSE_AXIOM_GATES", "1")

    resp = _open_stream(server, "/v1/observatory/actions")
    try:
        # cockpit event log → system.pulse
        event_log.emit("error", "worker", "boom", job_id="job_42")
        got = _read_until(resp, lambda e, d: e == "system.pulse" and d["label"] == "boom")
        assert got is not None
        assert got[1]["severity"] == "error" and got[1]["target"]["job_id"] == "job_42"
        assert got[1]["source"] == "cockpit"

        # flywheel skill use → skill.pulse
        from hermes_cli.jarvis_prime import flywheel

        flywheel.record("skill.used", {"skill": "deep-research"})
        got = _read_until(resp, lambda e, d: e == "skill.pulse")
        assert got is not None and got[1]["label"] == "deep-research"
        assert got[1]["source"] == "flywheel"

        # flywheel failed agent action → agent.pulse, severity error
        flywheel.record("agent.action", {"summary": "ran tool"}, outcome="failure")
        got = _read_until(resp, lambda e, d: e == "agent.pulse")
        assert got is not None and got[1]["severity"] == "error"

        # collector node activation → cluster.spark
        om.get_collector().record_node_activate("c-test", weight=0.75)
        got = _read_until(resp, lambda e, d: e == "cluster.spark")
        assert got is not None and got[1]["target"]["cluster_id"] == "c-test"
        assert got[1]["weight"] == 0.75 and got[1]["source"] == "collector"

        # collector gate verdict (fail) → gate.flare, severity error
        om.get_collector().record_gate_verdict("job_1", "build", "fail")
        got = _read_until(resp, lambda e, d: e == "gate.flare")
        assert got is not None and got[1]["severity"] == "error"

        # axiom chain decision → audit.flare
        from hermes_cli.jarvis_prime.axiom_bridge import AxiomBridge

        AxiomBridge().record_event("ue5.action", {"op": "render"})
        got = _read_until(resp, lambda e, d: e == "audit.flare")
        assert got is not None and got[1]["source"] == "axiom"
    finally:
        resp.close()


def test_actions_stream_resume_with_cursor(
    server, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fast(monkeypatch)
    monkeypatch.setenv("MUSE_OBSERVATORY", "1")

    resp = _open_stream(server, "/v1/observatory/actions")
    try:
        event_log.emit("info", "gateway", "first")
        got = _read_until(resp, lambda e, d: e == "system.pulse" and d["label"] == "first")
        assert got is not None
        cursor = got[2]  # the SSE id: line = opaque resume cursor
        assert cursor
    finally:
        resp.close()

    # Emit while disconnected, then resume from the cursor: only "second" arrives.
    event_log.emit("info", "gateway", "second")
    resp2 = _open_stream(server, "/v1/observatory/actions", last_event_id=cursor)
    try:
        got = _read_until(resp2, lambda e, d: e == "system.pulse")
        assert got is not None
        assert got[1]["label"] == "second"  # "first" is not replayed
    finally:
        resp2.close()
