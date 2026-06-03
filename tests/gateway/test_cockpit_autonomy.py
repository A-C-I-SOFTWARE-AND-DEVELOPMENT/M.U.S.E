"""End-to-end tests for the cockpit autonomy + emergency-stop endpoints.

Hermetic: starts the real stdlib cockpit server on a random loopback port
with a tmp HERMES_HOME and known token, then drives it with ``urllib``.
Mirrors the harness in ``test_cockpit_api.py``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit.server import serve


TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    monkeypatch.delenv("HERMES_AUTONOMY", raising=False)
    return tmp_path


@pytest.fixture()
def server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _url(server, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _get(server, path: str):
    req = urllib.request.Request(_url(server, path), method="GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def _post(server, path: str, body: dict):
    data = json.dumps(body).encode()
    req = urllib.request.Request(_url(server, path), data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ---------------------------------------------------------------------------
# GET /v1/cockpit/autonomy
# ---------------------------------------------------------------------------


def test_autonomy_default_is_assisted(server) -> None:
    status, payload = _get(server, "/v1/cockpit/autonomy")
    assert status == 200
    assert payload["level"] == "assisted"
    assert payload["revocable"] is True
    assert payload["capabilities"]["auto_approved"] == ["safe_read"]


def test_set_high_autonomy_requires_workspace(server) -> None:
    status, payload = _post(
        server, "/v1/cockpit/autonomy", {"level": "owner_high_autonomy_coding"}
    )
    assert status == 400
    assert "workspace" in payload["error"]


def test_set_and_read_high_autonomy(server, tmp_path) -> None:
    ws = str(tmp_path / "project")
    status, payload = _post(
        server,
        "/v1/cockpit/autonomy",
        {"level": "owner_high_autonomy_coding", "workspace_path": ws},
    )
    assert status == 200
    assert payload["level"] == "owner_high_autonomy_coding"
    assert payload["display_name"] == "High-Autonomy Coding"
    assert payload["workspace_root"] == ws
    caps = payload["capabilities"]
    assert "local_command" in caps["auto_approved"]
    assert "vercel_deploy" in caps["requires_approval"]
    assert "github_force_push" in caps["always_deny"]

    # Persisted across a fresh GET.
    status, payload = _get(server, "/v1/cockpit/autonomy")
    assert payload["level"] == "owner_high_autonomy_coding"


def test_unknown_level_rejected(server) -> None:
    status, payload = _post(server, "/v1/cockpit/autonomy", {"level": "wishful"})
    assert status == 400


def test_revoke_returns_to_assisted(server, tmp_path) -> None:
    _post(
        server,
        "/v1/cockpit/autonomy",
        {"level": "owner_high_autonomy_coding", "workspace_path": str(tmp_path)},
    )
    status, payload = _post(server, "/v1/cockpit/autonomy", {"revoke": True})
    assert status == 200
    assert payload["level"] == "assisted"


# ---------------------------------------------------------------------------
# Decisions audit trail
# ---------------------------------------------------------------------------


def test_autonomy_change_is_audited(server, tmp_path) -> None:
    _post(
        server,
        "/v1/cockpit/autonomy",
        {"level": "owner_high_autonomy_coding", "workspace_path": str(tmp_path)},
    )
    status, payload = _get(server, "/v1/cockpit/autonomy/decisions")
    assert status == 200
    decisions = payload["decisions"]
    assert any(
        d.get("details", {}).get("event") == "autonomy_change" for d in decisions
    )


# ---------------------------------------------------------------------------
# Emergency stop
# ---------------------------------------------------------------------------


def test_emergency_stop_cancels_jobs_and_drops_autonomy(server, tmp_path) -> None:
    # Raise autonomy, enqueue a job, then emergency-stop.
    _post(
        server,
        "/v1/cockpit/autonomy",
        {"level": "owner_high_autonomy_coding", "workspace_path": str(tmp_path)},
    )
    status, job = _post(
        server,
        "/v1/cockpit/jobs",
        {"title": "demo", "prompt": "do a thing", "worker_id": "code"},
    )
    assert status == 201
    job_id = job["id"]

    status, payload = _post(server, "/v1/cockpit/emergency-stop", {})
    assert status == 200
    assert payload["engaged"] is True
    assert job_id in payload["cancelled_jobs"]
    assert payload["autonomy_level"] == "read_only"

    # Autonomy dropped to the safe floor.
    _, autonomy = _get(server, "/v1/cockpit/autonomy")
    assert autonomy["level"] == "read_only"

    # The cancelled job reflects its terminal state.
    _, job_after = _get(server, f"/v1/cockpit/jobs/{job_id}")
    assert job_after["status"] in {"CANCELLED", "CANCELED"}
