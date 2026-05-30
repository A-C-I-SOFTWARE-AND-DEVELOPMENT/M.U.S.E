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
    # Legacy flat key/value still accepted (backward compatible)...
    status, raw = _post(
        server, "/v1/cockpit/memory", {"key": "fav_editor", "value": "neovim"}
    )
    assert status == 201
    created = json.loads(raw)
    assert created["stored"] is True
    # ...and the response is the canonical enriched MemoryItem, not flat.
    item = created["item"]
    assert item["title"] == "fav_editor"
    assert item["content"] == "neovim"
    assert item["id"] == "fav_editor"
    assert item["category"] == "UNCATEGORIZED"  # honest, not guessed
    assert item["confidence"] in {"LOW", "MEDIUM", "HIGH", "CONFIRMED"}
    assert item["durability"] in {
        "EPHEMERAL",
        "SESSION",
        "SHORT_TERM",
        "LONG_TERM",
        "PERMANENT",
    }
    assert item["provenance"]["source"]
    assert item["redacted"] is False

    _, listing = _get(server, "/v1/cockpit/memory")
    assert any(i["title"] == "fav_editor" for i in listing["items"])


def test_memory_create_canonical_fields(server) -> None:
    status, raw = _post(
        server,
        "/v1/cockpit/memory",
        {
            "title": "deploy_window",
            "content": "Owner prefers deploys after 6pm ET",
            "category": "OWNER_PREFERENCE",
            "durability": "PERMANENT",
            "confidence": "HIGH",
            "tags": ["ops", "scheduling"],
        },
    )
    assert status == 201
    item = json.loads(raw)["item"]
    assert item["category"] == "OWNER_PREFERENCE"  # persisted, round-trips
    assert item["durability"] == "PERMANENT"
    assert item["confidence"] == "HIGH"
    assert "ops" in item["tags"]


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


# ---------------------------------------------------------------------------
# approvals — persistent proposal queue, owner phrase preserved
# ---------------------------------------------------------------------------


def _seed_proposal(home: Path) -> str:
    import hashlib
    import json as _json

    path = home / "jarvis_prime" / "proposals.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    prop = {
        "kind": "skill_update",
        "target_path": "skills/foo/SKILL.md",
        "rationale": "improve",
        "risk_class": "RC2",
        "requires_owner_approval": True,
        "status": "proposed",
        "created_at": "2026-05-30T00:00:00+00:00",
    }
    path.write_text(_json.dumps(prop) + "\n", encoding="utf-8")
    raw = f"{prop['kind']}|{prop['target_path']}|{prop['created_at']}"
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def test_approvals_list_real_queue(server, home: Path) -> None:
    pid = _seed_proposal(home)
    _, payload = _get(server, "/v1/cockpit/approvals")
    ids = {a["id"] for a in payload["approvals"]}
    assert pid in ids
    item = next(a for a in payload["approvals"] if a["id"] == pid)
    assert item["risk_level"] == "medium"


def test_approve_requires_exact_owner_phrase(server, home: Path) -> None:
    pid = _seed_proposal(home)
    # Wrong phrase → 403, never bypasses the owner gate.
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server,
            f"/v1/cockpit/approvals/{pid}",
            {"decision": "approve", "authorization": "yes go ahead"},
        )
    assert exc.value.code == 403
    # Exact phrase → approved.
    status, raw = _post(
        server,
        f"/v1/cockpit/approvals/{pid}",
        {"decision": "approve", "authorization": "Yes, with authorization."},
    )
    assert status == 200
    assert json.loads(raw)["status"] == "approve"


def test_reject_needs_no_phrase(server, home: Path) -> None:
    pid = _seed_proposal(home)
    status, raw = _post(
        server, f"/v1/cockpit/approvals/{pid}", {"decision": "reject"}
    )
    assert status == 200


def test_sessions_list_real_or_empty(server) -> None:
    _, payload = _get(server, "/v1/cockpit/sessions")
    assert "sessions" in payload and isinstance(payload["sessions"], list)


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
