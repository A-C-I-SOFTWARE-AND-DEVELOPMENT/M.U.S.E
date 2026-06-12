"""Tests for POST /v1/cockpit/jobs/{id}/publish (owner-gated PR open).

Only the gated/refused/staged paths are exercised — the real PR open is a
network action behind the owner phrase + a configured PAT (absent in CI), so it
is intentionally not unit-tested.
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


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
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


def _dispatch(server, workspace_path: str) -> str:
    status, job = _post(server, "/v1/cockpit/jobs", {
        "title": "Ship it", "worker_id": "codex_cli",
        "prompt": "## Goal\nDo it", "workspace_path": workspace_path,
    })
    assert status == 201
    return job["id"]


def test_publish_unknown_job_is_404(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/jobs/nope/publish", {})
    assert exc.value.code == 404


def test_publish_no_workspace_is_409(server) -> None:
    from muse_cli import orchestrator as orch

    jid = orch.submit_job("Add a /healthz endpoint").id
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/jobs/{jid}/publish",
              {"authorization": AUTHORIZATION_PHRASE})
    assert exc.value.code == 409


def test_publish_without_phrase_stages_approval_required(server, home: Path) -> None:
    ws = home / "ws"
    ws.mkdir()
    jid = _dispatch(server, str(ws))
    status, body = _post(server, f"/v1/cockpit/jobs/{jid}/publish", {})
    assert status == 200
    assert body["status"] == "approval_required"
    assert body["authorization_required"] is True
    assert "preview" in body  # no GitHub call was made


def test_publish_disabled_on_non_loopback_cockpit(server, home: Path) -> None:
    from gateway.cockpit import handlers

    ws = home / "ws2"
    ws.mkdir()
    jid = _dispatch(server, str(ws))
    handlers.configure_runtime(allow_remote_execute=True)
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post(server, f"/v1/cockpit/jobs/{jid}/publish",
                  {"authorization": AUTHORIZATION_PHRASE})
        assert exc.value.code == 403
    finally:
        handlers.configure_runtime(allow_remote_execute=False)


def test_publish_with_phrase_but_no_token_is_github_not_configured(
    server, home: Path
) -> None:
    ws = home / "ws3"
    ws.mkdir()
    jid = _dispatch(server, str(ws))
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/jobs/{jid}/publish",
              {"authorization": AUTHORIZATION_PHRASE})
    assert exc.value.code == 403
    body = json.loads(exc.value.read())
    assert body["error"] == "github_not_configured"
