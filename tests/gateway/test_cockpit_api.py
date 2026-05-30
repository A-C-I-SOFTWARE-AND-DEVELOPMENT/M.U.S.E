"""End-to-end tests for the Hermes cockpit API (gateway/cockpit).

Hermetic: each test starts the real stdlib server on a random loopback
port with a tmp HERMES_HOME and a known token, then drives it with
``urllib``. No network, no third-party deps. The chat test exercises the
REAL JARVIS agent responder (not an echo).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit import auth as cockpit_auth
from gateway.cockpit.server import serve


TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _url(server, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _get(server, path: str, token: str | None = TOKEN):
    req = urllib.request.Request(_url(server, path), method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def _post(server, path: str, body: dict, token: str | None = TOKEN):
    data = json.dumps(body).encode()
    req = urllib.request.Request(_url(server, path), data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read()


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------


def test_health_needs_no_auth(server) -> None:
    status, payload = _get(server, "/v1/health", token=None)
    assert status == 200
    assert payload["ok"] is True
    assert payload["service"] == "hermes-cockpit"
    assert payload["api_version"]


def test_protected_route_rejects_missing_token(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/runtime/status", token=None)
    assert exc.value.code == 401


def test_protected_route_rejects_wrong_token(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/runtime/status", token="wrong")
    assert exc.value.code == 401


def test_protected_route_accepts_token(server) -> None:
    status, payload = _get(server, "/v1/cockpit/runtime/status")
    assert status == 200
    assert "gateway" in payload and "host" in payload and "queue" in payload


# ---------------------------------------------------------------------------
# real subsystem-backed routes
# ---------------------------------------------------------------------------


def test_runtime_status_has_live_queue_snapshot(server) -> None:
    _, payload = _get(server, "/v1/cockpit/runtime/status")
    queue = payload["queue"]
    assert set(queue) >= {"running", "queued", "waiting_approval"}
    assert all(isinstance(v, int) for v in queue.values())


def test_workers_detection_is_keyless(server) -> None:
    _, payload = _get(server, "/v1/cockpit/runtime/workers")
    assert "workers" in payload
    # detection-only: no token/key fields leak
    blob = json.dumps(payload)
    assert "api_key" not in blob and "token" not in blob.lower()


def test_diagnostics_runs_launch_doctor(server) -> None:
    _, payload = _get(server, "/v1/cockpit/diagnostics")
    assert "checks" in payload
    names = {c["name"] for c in payload["checks"]}
    assert "owner_gate" in names and "emergency_stop" in names


def test_models_is_read_only_policy(server) -> None:
    _, payload = _get(server, "/v1/cockpit/models")
    assert "routes" in payload
    assert payload["routes"]["local_oss"]["rank"] == 1


def test_jobs_and_events_have_real_or_empty(server) -> None:
    _, jobs = _get(server, "/v1/cockpit/jobs")
    assert "jobs" in jobs and isinstance(jobs["jobs"], list)
    _, events = _get(server, "/v1/cockpit/events")
    assert "events" in events and isinstance(events["events"], list)


# ---------------------------------------------------------------------------
# memory CRUD — real store, secret-rejection preserved
# ---------------------------------------------------------------------------


def test_memory_create_and_list(server) -> None:
    status, raw = _post(
        server, "/v1/cockpit/memory", {"key": "fav_editor", "value": "neovim"}
    )
    assert status == 201
    created = json.loads(raw)
    assert created["stored"] is True
    _, listing = _get(server, "/v1/cockpit/memory")
    assert any(i["key"] == "fav_editor" for i in listing["items"])


def test_memory_rejects_secret(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server,
            "/v1/cockpit/memory",
            {"key": "leak", "value": "api_key=sk-secret-value-1234567890"},
        )
    assert exc.value.code == 422  # rejected, not stored, not faked


# ---------------------------------------------------------------------------
# real-agent chat stream (NDJSON, not an echo)
# ---------------------------------------------------------------------------


def test_chat_streams_real_agent_turn(server) -> None:
    status, raw = _post(
        server, "/v1/jarvis/chat", {"prompt": "audit this repo", "history": []}
    )
    assert status == 200
    lines = [json.loads(ln) for ln in raw.decode().splitlines() if ln.strip()]
    types = [c["type"] for c in lines]
    assert types[0] == "thinking"
    assert "body" in types and types[-1] == "done"
    # Real classification, not an echo of the prompt.
    body_text = next(c["text"] for c in lines if c["type"] == "body")
    assert "JARVIS Prime" in body_text
    assert "You said:" not in body_text


def test_chat_requires_auth(server) -> None:
    data = json.dumps({"prompt": "hi"}).encode()
    req = urllib.request.Request(_url(server, "/v1/jarvis/chat"), data=data, method="POST")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=10)
    assert exc.value.code == 401


# ---------------------------------------------------------------------------
# loopback gate + token persistence
# ---------------------------------------------------------------------------


def test_refuses_non_loopback_bind(home: Path) -> None:
    with pytest.raises(ValueError):
        serve(host="0.0.0.0", port=0, token=TOKEN)


def test_token_persisted_owner_only(home: Path) -> None:
    token = cockpit_auth.load_or_create_token()
    assert token and cockpit_auth.read_token() == token
    import os
    import stat

    if os.name == "posix":
        mode = stat.S_IMODE(os.stat(cockpit_auth.token_path()).st_mode)
        assert mode == 0o600
