"""Tests for the cockpit ``GET /v1/cockpit/jobs/stream`` SSE endpoint.

Unit tests cover the pure ``_job_deltas`` diff; one hermetic integration test
opens the real stream on a loopback port (with shortened intervals), asserts the
initial ``job.upsert`` for a seeded job, then a delta after a state change.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import gateway.cockpit.server as server_mod
from gateway.cockpit.server import serve

TOKEN = "test-cockpit-token-123"


# ── unit: _job_deltas (pure, deterministic) ────────────────────────────────


def test_job_deltas_initial_snapshot_is_all_upserts() -> None:
    curr = {"a": {"id": "a", "updated_at": "1"}, "b": {"id": "b", "updated_at": "1"}}
    out = list(server_mod._job_deltas({}, curr))
    assert out == [("job.upsert", curr["a"]), ("job.upsert", curr["b"])]


def test_job_deltas_change_and_removal() -> None:
    prev = {"a": {"id": "a", "updated_at": "1"}, "b": {"id": "b", "updated_at": "1"}}
    curr = {"a": {"id": "a", "updated_at": "2"}}  # a changed, b removed
    out = list(server_mod._job_deltas(prev, curr))
    assert ("job.upsert", curr["a"]) in out
    assert ("job.removed", {"id": "b"}) in out
    assert len(out) == 2


def test_job_deltas_no_change_is_empty() -> None:
    snap = {"a": {"id": "a", "updated_at": "1"}}
    assert list(server_mod._job_deltas(snap, dict(snap))) == []


# ── integration: the live stream ───────────────────────────────────────────


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    return tmp_path


@pytest.fixture()
def server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _post(server, path: str, body: dict):
    host, port = server.server_address
    req = urllib.request.Request(
        f"http://{host}:{port}{path}", data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, json.loads(resp.read())


def _dispatch(server) -> str:
    status, job = _post(server, "/v1/cockpit/jobs", {
        "title": "Stream me", "worker_id": "codex_cli",
        "prompt": "## Goal\nDo it", "workspace_path": "/tmp/proj",
    })
    assert status == 201
    return job["id"]


def _open_stream(server):
    host, port = server.server_address
    req = urllib.request.Request(
        f"http://{host}:{port}/v1/cockpit/jobs/stream", method="GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    return urllib.request.urlopen(req, timeout=5)


def _read_until(resp, predicate, max_events: int = 200):
    """Return the first ``(event, data)`` SSE message matching ``predicate``."""
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


def test_jobs_stream_requires_auth(server) -> None:
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}/v1/cockpit/jobs/stream")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 401


def test_jobs_stream_initial_upsert_then_delta(
    server, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Shorten the loop so the test is fast and deterministic.
    monkeypatch.setattr(server_mod, "_SSE_POLL_S", 0.05)
    monkeypatch.setattr(server_mod, "_SSE_HEARTBEAT_S", 0.2)

    jid = _dispatch(server)
    resp = _open_stream(server)
    try:
        # Initial state: the seeded job arrives as an upsert.
        got = _read_until(resp, lambda e, d: e == "job.upsert" and d.get("id") == jid)
        assert got is not None
        assert got[1]["status"] == "QUEUED"

        # A state change emits a fresh upsert on the next tick.
        _post(server, f"/v1/cockpit/jobs/{jid}/cancel", {})
        got2 = _read_until(
            resp,
            lambda e, d: e == "job.upsert"
            and d.get("id") == jid
            and d.get("status") == "CANCELLED",
        )
        assert got2 is not None
    finally:
        resp.close()
