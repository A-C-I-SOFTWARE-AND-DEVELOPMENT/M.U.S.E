"""End-to-end tests for the cockpit job control + detail endpoints.

Covers the routes added to drive the Android Jobs cockpit:
``/jobs/{id}/ledger|pause|resume|rerun|approve|diff|validate``. Hermetic —
each test runs the real stdlib server on a random loopback port with a tmp
HERMES_HOME and a known token, driven over ``urllib``. No network, no deps.
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
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, json.loads(resp.read())


def _dispatch(server, **over) -> str:
    body = {
        "title": over.get("title", "Build feature"),
        "worker_id": over.get("worker_id", "codex_cli"),
        "prompt": over.get("prompt", "## Goal\nDo it"),
        "workspace_path": over.get("workspace_path", "/tmp/proj"),
    }
    status, job = _post(server, "/v1/cockpit/jobs", body)
    assert status == 201
    return job["id"]


# ── pause / resume (queue) ────────────────────────────────────────────────


def test_pause_then_resume_queue_job(server) -> None:
    jid = _dispatch(server)

    status, job = _post(server, f"/v1/cockpit/jobs/{jid}/pause", {"reason": "hold"})
    assert status == 200
    assert job["status"] == "PAUSED"

    status, job = _post(server, f"/v1/cockpit/jobs/{jid}/resume", {})
    assert status == 200
    assert job["status"] == "QUEUED"


def test_pause_unknown_job_is_404(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/jobs/nope/pause", {})
    assert exc.value.code == 404


def test_pause_terminal_job_is_409(server) -> None:
    jid = _dispatch(server)
    _post(server, f"/v1/cockpit/jobs/{jid}/cancel", {})
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/jobs/{jid}/pause", {})
    assert exc.value.code == 409


# ── rerun (queue, per-worker retry) ───────────────────────────────────────


def test_rerun_without_failed_worker_is_400(server) -> None:
    # A freshly queued job's worker is PENDING, not failed → nothing to rerun.
    jid = _dispatch(server)
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/jobs/{jid}/rerun", {})
    assert exc.value.code == 400


def test_rerun_unknown_worker_is_404(server) -> None:
    jid = _dispatch(server)
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/jobs/{jid}/rerun", {"worker_id": "ghost"})
    assert exc.value.code == 404


# ── ledger / detail ───────────────────────────────────────────────────────


def test_ledger_detail_shape_for_queue_job(server) -> None:
    jid = _dispatch(server, title="Wire up auth")
    status, detail = _get(server, f"/v1/cockpit/jobs/{jid}/ledger")
    assert status == 200
    assert detail["id"] == jid
    assert detail["objective"]
    assert detail["status"] == "QUEUED"
    assert isinstance(detail["workers"], list)
    assert isinstance(detail["timeline"], list)
    # commands_run is honestly empty (the queue doesn't record shell commands).
    assert detail["commands_run"] == []
    # The submit event always anchors the timeline.
    assert any(e["kind"] == "submit" for e in detail["timeline"])


def test_ledger_unknown_job_is_404(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/jobs/nope/ledger")
    assert exc.value.code == 404


# ── diff (open patch) ─────────────────────────────────────────────────────


def test_diff_honest_empty_when_no_git_workspace(server) -> None:
    # workspace_path points at a non-repo dir → empty patch, never fabricated.
    jid = _dispatch(server, workspace_path="/tmp/not-a-repo-xyz")
    status, diff = _get(server, f"/v1/cockpit/jobs/{jid}/diff")
    assert status == 200
    assert diff["files"] == []
    assert diff["diff"] == ""
    assert diff["truncated"] is False


# ── validate (run verification) ───────────────────────────────────────────


def test_validate_runs_gates_on_workspace(server, home: Path) -> None:
    ws = home / "ws"
    ws.mkdir()
    jid = _dispatch(server, workspace_path=str(ws))
    status, report = _post(server, f"/v1/cockpit/jobs/{jid}/validate", {})
    assert status == 200
    assert "gates" in report and isinstance(report["gates"], list)
    assert report["policy"]["all_must_pass"] is True


# ── approve (owner-gated orchestrator phase) ──────────────────────────────


def _orchestrator_job() -> str:
    from muse_cli import orchestrator as orch

    return orch.submit_job("Add a /healthz endpoint").id


def test_approve_requires_owner_phrase(server) -> None:
    jid = _orchestrator_job()
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/jobs/{jid}/approve", {"phase": "execute"})
    assert exc.value.code == 403


def test_approve_with_owner_phrase_grants_phase(server) -> None:
    jid = _orchestrator_job()
    status, job = _post(
        server,
        f"/v1/cockpit/jobs/{jid}/approve",
        {"phase": "execute", "authorization": AUTHORIZATION_PHRASE},
    )
    assert status == 200
    assert job["id"] == jid


def test_approve_unknown_phase_is_400(server) -> None:
    jid = _orchestrator_job()
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server,
            f"/v1/cockpit/jobs/{jid}/approve",
            {"phase": "made_up", "authorization": AUTHORIZATION_PHRASE},
        )
    assert exc.value.code == 400


def test_resume_orchestrator_job(server) -> None:
    jid = _orchestrator_job()
    status, job = _post(server, f"/v1/cockpit/jobs/{jid}/resume", {})
    assert status == 200
    assert job["id"] == jid


# ── cancel (resolves both stores) ─────────────────────────────────────────


def test_cancel_queue_job(server) -> None:
    jid = _dispatch(server)
    status, job = _post(server, f"/v1/cockpit/jobs/{jid}/cancel", {"reason": "stop"})
    assert status == 200
    assert job["id"] == jid
    assert job["status"] == "CANCELLED"


def test_cancel_orchestrator_job(server) -> None:
    # The Job Detail cockpit shows orchestrator jobs and an enabled Cancel
    # control; cancelling one must resolve the orchestrator store, not 404.
    jid = _orchestrator_job()
    status, job = _post(server, f"/v1/cockpit/jobs/{jid}/cancel", {})
    assert status == 200
    assert job["id"] == jid
    assert job["status"] == "CANCELLED"


def test_cancel_unknown_job_is_404(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/jobs/nope/cancel", {})
    assert exc.value.code == 404
