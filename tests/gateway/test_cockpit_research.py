"""End-to-end tests for the cockpit Research Mode routes.

Hermetic: starts the real stdlib server on a loopback port with a tmp
HERMES_HOME, drives it with ``urllib``. Source gathering is forced to the
manual-source path (no network, no provider configured in the test env), so
every assertion is about *real* engine output, never a fabricated answer.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit.server import serve


TOKEN = "test-cockpit-token-research"


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


def _req(server, path: str, method: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(_url(server, path), data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _run_research(server):
    return _req(
        server,
        "/v1/cockpit/research",
        "POST",
        {
            "query": "What transport does the referenced protocol use?",
            "manual_sources": [
                {
                    "title": "Official spec",
                    "url": "https://docs.example.gov/spec",
                    "excerpt": "The referenced protocol uses QUIC transport over UDP.",
                }
            ],
        },
    )


def test_research_run_is_source_backed(server):
    status, report = _run_research(server)
    assert status == 201
    assert report["cards"], "expected evidence cards"
    assert report["claims"], "expected synthesized claims"
    card_uris = {c["source_uri"] for c in report["cards"]}
    assert set(report["citations"]).issubset(card_uris)


def test_research_run_requires_query(server):
    status, body = _req(server, "/v1/cockpit/research", "POST", {"query": ""})
    assert status == 400


def test_research_list_and_get(server):
    status, report = _run_research(server)
    assert status == 201
    rid = report["id"]

    status, listing = _req(server, "/v1/cockpit/research", "GET")
    assert status == 200
    assert any(r["id"] == rid for r in listing["reports"])

    status, fetched = _req(server, f"/v1/cockpit/research/{rid}", "GET")
    assert status == 200
    assert fetched["id"] == rid

    status, missing = _req(server, "/v1/cockpit/research/rr_missing", "GET")
    assert status == 404


def test_research_promote_goes_through_memory_gate(server):
    _, report = _run_research(server)
    rid = report["id"]
    card_id = report["cards"][0]["id"]

    status, body = _req(
        server, f"/v1/cockpit/research/{rid}/promote", "POST", {"card_id": card_id}
    )
    assert status == 201, body
    assert body["stored"] is True

    # The promoted finding is visible in the real memory list.
    status, mem = _req(server, "/v1/cockpit/memory", "GET")
    assert status == 200
    assert any(
        "https://docs.example.gov/spec" in (i.get("provenance", {}).get("note") or "")
        or i.get("content", "").lower().find("quic") >= 0
        for i in mem["items"]
    )


def test_research_promote_rejects_secret_like_card(server):
    # A card whose claim looks like a secret must be rejected (422), honestly.
    _, report = _req(
        server,
        "/v1/cockpit/research",
        "POST",
        {
            "query": "leaked token value",
            "manual_sources": [
                {
                    "title": "leak",
                    "url": "https://docs.example.gov/leak",
                    "excerpt": "api_key=supersecretvalue1234567890",
                }
            ],
        },
    )
    rid = report["id"]
    card_id = report["cards"][0]["id"]
    status, body = _req(
        server, f"/v1/cockpit/research/{rid}/promote", "POST", {"card_id": card_id}
    )
    assert status == 422
    assert body["stored"] is False


def test_research_create_task_enqueues_only(server):
    _, report = _run_research(server)
    rid = report["id"]
    status, job = _req(
        server, f"/v1/cockpit/research/{rid}/task", "POST", {"title": "Implement it"}
    )
    assert status == 201, job
    assert job["status"].upper() in {"QUEUED", "DRAFT"}
    # Nothing executed — it shows up queued in the jobs list.
    status, jobs = _req(server, "/v1/cockpit/jobs", "GET")
    assert status == 200
    assert any(j["id"] == job["id"] for j in jobs["jobs"])
