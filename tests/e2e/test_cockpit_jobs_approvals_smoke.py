"""End-to-end "client journey" smoke for the cockpit jobs + approvals path.

This complements ``test_full_app_smoke.py`` (which covers the chat stream and
cross-surface memory) by exercising the *other* two surfaces a real owner drives
from the Android cockpit, over real HTTP, with no network and no model:

1. **Jobs** — the app dispatches a job (``POST /v1/cockpit/jobs``), sees it land
   in the queue (``GET /v1/cockpit/jobs``), and then hits the **owner gate**
   when it tries to run an execute lane without the authorization phrase
   (``POST /v1/cockpit/jobs/{id}/run`` → 403). This proves the double gate that
   protects irreversible/agentic actions is wired end to end, not just at the
   handler level.
2. **Approvals** — the owner-approval queue round-trips: a pending proposal
   surfaces as an ``ApprovalCard`` (``GET /v1/cockpit/approvals``), an approve
   with the wrong phrase is refused (403), and the exact owner phrase resolves
   it (200).

These run without API keys and never shell out: the gated run is refused
*before* any worker dispatch, and the approval queue is file-backed.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit.server import serve
from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE


TOKEN = "test-cockpit-token-e2e"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Isolate every state root the cockpit touches so the smoke is hermetic.
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
        return resp.status, json.loads(resp.read())


def _seed_proposal(home: Path) -> str:
    """Drop one pending self-update proposal and return its cockpit id."""
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
    path.write_text(json.dumps(prop) + "\n", encoding="utf-8")
    raw = f"{prop['kind']}|{prop['target_path']}|{prop['created_at']}"
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def test_jobs_journey_dispatch_list_and_owner_gated_run(server) -> None:
    """The app dispatches a job, sees it queued, and is owner-gated on run."""
    from hermes_cli import orchestrator as orch

    # Health is the app's first probe — no auth, reports the service.
    status, payload = _get(server, "/v1/health", token=None)
    assert status == 200 and payload["ok"] is True

    # Dispatch a job (the "Tasks" screen submitting work). This lands in the
    # JobQueue store that a worker runner advances.
    status, job = _post(
        server,
        "/v1/cockpit/jobs",
        {"title": "Edit the uploader", "prompt": "tidy the upload path"},
    )
    assert status == 201
    queue_job_id = job["id"]
    assert queue_job_id

    # It shows up in the aggregated queue the app polls (jobs_list surfaces both
    # the JobQueue and the orchestrator store).
    status, listing = _get(server, "/v1/cockpit/jobs")
    assert status == 200
    assert any(j["id"] == queue_job_id for j in listing["jobs"])

    # The gated execute lane runs against an orchestrator job. Submit one the
    # way ``/orchestrate`` does, then prove the run endpoint refuses an execute
    # lane WITHOUT the owner phrase — the gate that protects irreversible /
    # agentic actions, exercised over the wire.
    orch_job = orch.submit_job("edit the uploader")
    status, run_listing = _get(server, "/v1/cockpit/jobs")
    assert any(j["id"] == orch_job.id for j in run_listing["jobs"])

    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server,
            f"/v1/cockpit/jobs/{orch_job.id}/run",
            {"worker_id": "codex-execute"},
        )
    assert exc.value.code == 403
    body = json.loads(exc.value.read())
    assert "owner approval" in body["error"]
    assert AUTHORIZATION_PHRASE in body["hint"]


def test_approvals_journey_card_surfaces_and_owner_phrase_resolves(
    server, home: Path
) -> None:
    """A pending proposal surfaces as a card and round-trips through the gate."""
    pid = _seed_proposal(home)

    # The Approvals screen sees the pending card.
    status, payload = _get(server, "/v1/cockpit/approvals")
    assert status == 200
    card = next(a for a in payload["approvals"] if a["id"] == pid)
    assert card["status"] == "PENDING"

    # Approving with the wrong phrase is refused — never bypass the owner gate.
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server,
            f"/v1/cockpit/approvals/{pid}",
            {"decision": "approve", "authorization": "sure go ahead"},
        )
    assert exc.value.code == 403

    # The exact owner phrase resolves it.
    status, resolved = _post(
        server,
        f"/v1/cockpit/approvals/{pid}",
        {"decision": "approve", "authorization": AUTHORIZATION_PHRASE},
    )
    assert status == 200
    assert resolved["status"] == "approve"


def test_unauthenticated_cockpit_call_is_rejected(server) -> None:
    """Every cockpit route except health refuses a missing bearer token."""
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/jobs", token=None)
    assert exc.value.code == 401
