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
from muse_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE


TOKEN = "test-cockpit-token-123"
# Raising autonomy is owner-gated — the exact phrase travels in the POST body.
PHRASE = AUTHORIZATION_PHRASE


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    monkeypatch.delenv("HERMES_AUTONOMY", raising=False)
    monkeypatch.delenv("HERMES_COCKPIT_AUTONOMY_LOCKED", raising=False)
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
    # Past the owner gate (phrase supplied), a high-autonomy raise still needs a
    # workspace scope.
    status, payload = _post(
        server,
        "/v1/cockpit/autonomy",
        {"level": "owner_high_autonomy_coding", "authorization": PHRASE},
    )
    assert status == 400
    assert "workspace" in payload["error"]


def test_set_and_read_high_autonomy(server, tmp_path) -> None:
    ws = str(tmp_path / "project")
    status, payload = _post(
        server,
        "/v1/cockpit/autonomy",
        {
            "level": "owner_high_autonomy_coding",
            "workspace_path": ws,
            "authorization": PHRASE,
        },
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
        {
            "level": "owner_high_autonomy_coding",
            "workspace_path": str(tmp_path),
            "authorization": PHRASE,
        },
    )
    # Revoke (de-escalation) needs no phrase.
    status, payload = _post(server, "/v1/cockpit/autonomy", {"revoke": True})
    assert status == 200
    assert payload["level"] == "assisted"


# ---------------------------------------------------------------------------
# Owner gate on escalation (FU-12)
# ---------------------------------------------------------------------------


def test_raise_autonomy_requires_owner_phrase(server, tmp_path) -> None:
    # Without the phrase, a bearer-token holder cannot escalate.
    status, payload = _post(
        server,
        "/v1/cockpit/autonomy",
        {"level": "owner_high_autonomy_coding", "workspace_path": str(tmp_path)},
    )
    assert status == 403
    assert payload["authorization_required"] is True
    # The floor is unchanged — the escalation did not take effect.
    _, autonomy = _get(server, "/v1/cockpit/autonomy")
    assert autonomy["level"] == "assisted"

    # A wrong phrase is also refused (exact match required).
    status, _ = _post(
        server,
        "/v1/cockpit/autonomy",
        {"level": "yolo", "authorization": "yes with authorization"},
    )
    assert status == 403

    # With the exact phrase it succeeds.
    status, payload = _post(
        server,
        "/v1/cockpit/autonomy",
        {
            "level": "owner_high_autonomy_coding",
            "workspace_path": str(tmp_path),
            "authorization": PHRASE,
        },
    )
    assert status == 200
    assert payload["level"] == "owner_high_autonomy_coding"


def test_lower_autonomy_is_ungated(server) -> None:
    # Dropping to a safe floor never needs the phrase (de-escalation is safe).
    status, payload = _post(server, "/v1/cockpit/autonomy", {"level": "read_only"})
    assert status == 200
    assert payload["level"] == "read_only"


def test_autonomy_raises_can_be_env_locked(server, tmp_path, monkeypatch) -> None:
    # The deployment kill-switch refuses raises even with the correct phrase.
    monkeypatch.setenv("HERMES_COCKPIT_AUTONOMY_LOCKED", "1")
    status, payload = _post(
        server,
        "/v1/cockpit/autonomy",
        {
            "level": "owner_high_autonomy_coding",
            "workspace_path": str(tmp_path),
            "authorization": PHRASE,
        },
    )
    assert status == 403
    assert "disabled" in payload["error"]
    # Lowering still works while locked.
    status, payload = _post(server, "/v1/cockpit/autonomy", {"level": "read_only"})
    assert status == 200
    assert payload["level"] == "read_only"


# ---------------------------------------------------------------------------
# Decisions audit trail
# ---------------------------------------------------------------------------


def test_autonomy_change_is_audited(server, tmp_path) -> None:
    _post(
        server,
        "/v1/cockpit/autonomy",
        {
            "level": "owner_high_autonomy_coding",
            "workspace_path": str(tmp_path),
            "authorization": PHRASE,
        },
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
        {
            "level": "owner_high_autonomy_coding",
            "workspace_path": str(tmp_path),
            "authorization": PHRASE,
        },
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
