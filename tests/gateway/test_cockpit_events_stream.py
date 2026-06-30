"""Tests for the cockpit event log + ``GET /v1/cockpit/events/stream`` SSE.

Unit tests cover ``gateway.cockpit.event_log`` (append + offset-tail); one
hermetic integration test opens the live stream and asserts an emitted event is
delivered as an SSE ``log`` event.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import gateway.cockpit.server as server_mod
from gateway.cockpit import event_log
from gateway.cockpit.server import serve

TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    return tmp_path


# ── unit: event_log ────────────────────────────────────────────────────────


def test_event_log_emit_and_offset_tail(home: Path) -> None:
    assert event_log.current_offset() == 0
    event_log.emit("warn", "gateway", "hello", job_id="job_1", attributes={"k": 1})

    records, offset = event_log.read_since_offset(0)
    assert len(records) == 1
    rec = records[0]
    assert rec["level"] == "warn"
    assert rec["source"] == "gateway"
    assert rec["message"] == "hello"
    assert rec["job_id"] == "job_1"
    assert rec["attributes"] == {"k": 1}
    assert offset > 0

    # A second read from the new offset yields nothing until another emit.
    more, offset2 = event_log.read_since_offset(offset)
    assert more == []
    assert offset2 == offset
    event_log.emit("info", "worker", "again")
    more2, _ = event_log.read_since_offset(offset)
    assert [r["message"] for r in more2] == ["again"]


def test_event_log_normalizes_unknown_level_and_source(home: Path) -> None:
    event_log.emit("LOUD", "martians", "x")
    records, _ = event_log.read_since_offset(0)
    assert records[0]["level"] == "info"
    assert records[0]["source"] == "gateway"


# ── integration: the live stream ───────────────────────────────────────────


@pytest.fixture()
def server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _open_stream(server, path: str):
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}{path}", method="GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    return urllib.request.urlopen(req, timeout=5)


def _read_until(resp, predicate, max_events: int = 200):
    event = None
    seen = 0
    while seen < max_events:
        raw = resp.readline()
        if not raw:
            return None
        line = raw.decode("utf-8").rstrip("\r\n")
        if line.startswith("event: "):
            event = line[len("event: "):]
        elif line.startswith("data: "):
            data = json.loads(line[len("data: "):])
            seen += 1
            if event is not None and predicate(event, data):
                return event, data
            event = None
    return None


def test_events_stream_requires_auth(server) -> None:
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}/v1/cockpit/events/stream")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 401


def test_events_stream_delivers_emitted_event(
    server, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server_mod, "_SSE_POLL_S", 0.05)
    monkeypatch.setattr(server_mod, "_SSE_HEARTBEAT_S", 0.2)

    resp = _open_stream(server, "/v1/cockpit/events/stream")
    try:
        # Emit AFTER connecting — the stream tails from the current end forward.
        event_log.emit("error", "worker", "boom", job_id="job_42")
        got = _read_until(resp, lambda e, d: e == "log" and d.get("message") == "boom")
        assert got is not None
        assert got[1]["level"] == "error"
        assert got[1]["job_id"] == "job_42"
    finally:
        resp.close()


def test_events_stream_level_filter(
    server, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server_mod, "_SSE_POLL_S", 0.05)
    monkeypatch.setattr(server_mod, "_SSE_HEARTBEAT_S", 0.2)

    resp = _open_stream(server, "/v1/cockpit/events/stream?level=error")
    try:
        event_log.emit("info", "gateway", "ignored-info")
        event_log.emit("error", "gateway", "kept-error")
        # The info event is filtered out; the first log we see is the error.
        got = _read_until(resp, lambda e, d: e == "log")
        assert got is not None
        assert got[1]["message"] == "kept-error"
    finally:
        resp.close()


# ── buffered GET /events (leveled list) ────────────────────────────────────


def _get(server, path: str):
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}{path}", method="GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def test_events_list_returns_leveled_events(server, home: Path) -> None:
    event_log.emit("warn", "gateway", "hello-list", job_id="j1")
    status, body = _get(server, "/v1/cockpit/events")
    assert status == 200
    assert isinstance(body["events"], list)
    assert body["next_cursor"] is None
    rec = next(e for e in body["events"] if e["message"] == "hello-list")
    assert rec["level"] == "warn"
    assert rec["job_id"] == "j1"


def test_events_list_level_filter(server, home: Path) -> None:
    event_log.emit("info", "gateway", "i1")
    event_log.emit("error", "gateway", "e1")
    status, body = _get(server, "/v1/cockpit/events?level=error")
    assert status == 200
    msgs = [e["message"] for e in body["events"]]
    assert "e1" in msgs
    assert "i1" not in msgs


# ── GET /v1/cockpit/trace (request-trace summary) ──────────────────────────


def test_trace_summary_requires_auth(server) -> None:
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}/v1/cockpit/trace")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 401


def test_trace_summary_honest_empty(server, home: Path) -> None:
    status, body = _get(server, "/v1/cockpit/trace")
    assert status == 200
    assert body["request_count"] == 0
    assert "generated_at" in body


def test_trace_summary_aggregates_emitted_traces(server, home: Path) -> None:
    event_log.emit(
        "info", "hook", "request_trace",
        attributes={
            "endpoint": "openai_v1_chat_completions", "model": "qwen",
            "is_remote": False, "first_token_ms": 120, "total_latency_ms": 900,
            "tool_calls": 3, "tool_parse_errors": 0, "tool_exec_failures": 1,
            "fallback_used": False,
        },
    )
    event_log.emit(
        "info", "hook", "model_lifecycle",
        attributes={"event": "unload", "model": "qwen", "ok": True},
    )
    status, body = _get(server, "/v1/cockpit/trace")
    assert status == 200
    assert body["request_count"] == 1
    assert body["endpoints"] == {"openai_v1_chat_completions": 1}
    assert body["tool_calls"]["failure_rate"] == round(1 / 3, 4)
    assert body["lifecycle"]["unload_count"] == 1
