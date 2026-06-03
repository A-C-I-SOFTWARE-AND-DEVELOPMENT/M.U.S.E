"""Tests for the cockpit ledger timeline (gateway/cockpit) — the mobile
"Activity" surface over the orchestrator event ledger.

Hermetic: each test seeds a tmp ``HERMES_HOME`` with real
``jobs/<id>/ledger.jsonl`` files, starts the real stdlib cockpit server on
a random loopback port, and drives it with ``urllib``. Covers the three
acceptance checks: redaction, timeline ordering, job filtering — plus the
owner-gated rollback request.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit import redaction
from gateway.cockpit.server import serve

TOKEN = "test-cockpit-token-123"

# A planted secret that must never appear in any response.
PLANTED_SECRET = "sk-live-abcdef0123456789abcdef0123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    return tmp_path


def _seed_ledger(home: Path, job_id: str, entries: list[dict]) -> None:
    d = home / "jobs" / job_id
    d.mkdir(parents=True, exist_ok=True)
    with (d / "ledger.jsonl").open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")


@pytest.fixture()
def seeded(home: Path) -> Path:
    _seed_ledger(home, "job_alpha", [
        {"ts": "2026-06-01T09:00:00+00:00", "kind": "submit", "prompt": "do a thing"},
        {
            "ts": "2026-06-01T09:01:00+00:00",
            "kind": "worker_dispatch",
            "worker_id": "codex-execute",
            "candidate_files": [{"path": "src/app.py"}],
        },
        {
            "ts": "2026-06-01T09:02:00+00:00",
            "kind": "worker_result",
            "worker_id": "codex-execute",
            # A worker accidentally echoed a credential into its output.
            "output": f"export OPENAI_API_KEY={PLANTED_SECRET}",
        },
        {"ts": "2026-06-01T09:03:00+00:00", "kind": "publish"},
    ])
    _seed_ledger(home, "job_beta", [
        {"ts": "2026-06-02T12:00:00+00:00", "kind": "submit", "prompt": "another"},
        {
            "ts": "2026-06-02T12:05:00+00:00",
            "kind": "approve",
            "phase": "execute",
            "worker_id": "claude-execute",
        },
    ])
    return home


@pytest.fixture()
def server(seeded: Path):
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
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ---------------------------------------------------------------------------
# redaction (unit) — single source of truth, no leaks
# ---------------------------------------------------------------------------


def test_redact_text_scrubs_known_secret_shapes() -> None:
    assert redaction.redact_text(f"key={PLANTED_SECRET}") == "key=[REDACTED]"
    assert "[REDACTED]" in redaction.redact_text("Authorization: Bearer abcdef0123456789")
    assert redaction.redact_text("ghp_" + "a" * 24).strip() == "[REDACTED]"
    assert redaction.contains_secret(f"API_KEY={PLANTED_SECRET}") is True
    assert redaction.contains_secret("just a normal sentence") is False


def test_redact_value_recurses() -> None:
    out = redaction.redact_value({"a": [f"token={PLANTED_SECRET}"], "b": {"c": "fine"}})
    assert PLANTED_SECRET not in json.dumps(out)
    assert out["b"]["c"] == "fine"


# ---------------------------------------------------------------------------
# timeline endpoint
# ---------------------------------------------------------------------------


def test_timeline_requires_auth(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as ei:
        _get(server, "/v1/cockpit/ledger", token=None)
    assert ei.value.code == 401


def test_timeline_never_leaks_secret(server) -> None:
    status, body = _get(server, "/v1/cockpit/ledger")
    assert status == 200
    assert PLANTED_SECRET not in json.dumps(body), "secret leaked in timeline list"
    # And the detail view of the offending event must also be clean.
    status, detail = _get(server, "/v1/cockpit/ledger/job_alpha/2")
    assert status == 200
    assert PLANTED_SECRET not in json.dumps(detail), "secret leaked in event detail"
    assert "[REDACTED]" in json.dumps(detail)


def test_timeline_ordering(server) -> None:
    _, desc = _get(server, "/v1/cockpit/ledger?order=desc")
    ts_desc = [e["timestamp"] for e in desc["events"]]
    assert ts_desc == sorted(ts_desc, reverse=True)

    _, asc = _get(server, "/v1/cockpit/ledger?order=asc")
    ts_asc = [e["timestamp"] for e in asc["events"]]
    assert ts_asc == sorted(ts_asc)


def test_timeline_job_filter(server) -> None:
    _, body = _get(server, "/v1/cockpit/ledger?job=job_beta")
    assert body["events"], "expected job_beta events"
    assert {e["job_id"] for e in body["events"]} == {"job_beta"}


def test_timeline_category_and_worker_and_file_filters(server) -> None:
    _, pub = _get(server, "/v1/cockpit/ledger?category=DEPLOY_PUBLISH")
    assert all(e["category"] == "DEPLOY_PUBLISH" for e in pub["events"])
    assert pub["events"], "expected a publish event"

    _, codex = _get(server, "/v1/cockpit/ledger?worker=codex-execute")
    assert all(e["worker"] == "codex-execute" for e in codex["events"])

    _, files = _get(server, "/v1/cockpit/ledger?file=app.py")
    assert files["events"]
    assert all(any("app.py" in f for f in e["files"]) for e in files["events"])


def test_timeline_date_filter(server) -> None:
    _, body = _get(server, "/v1/cockpit/ledger?since=2026-06-02")
    assert body["events"]
    assert all(e["timestamp"] >= "2026-06-02" for e in body["events"])


def test_date_only_until_is_inclusive_of_the_whole_day(server) -> None:
    # Regression: a date-only `until` must keep same-day events whose full
    # ISO timestamp (…T12:05:00+00:00) lexically sorts after the bare date.
    _, body = _get(server, "/v1/cockpit/ledger?until=2026-06-02")
    days = {e["timestamp"][:10] for e in body["events"]}
    assert "2026-06-02" in days, "date-only until dropped same-day events"
    assert all(e["timestamp"][:10] <= "2026-06-02" for e in body["events"])
    # job_beta's events are all on 2026-06-02 — they must survive the filter.
    assert any(e["job_id"] == "job_beta" for e in body["events"])


def test_date_only_since_is_inclusive_of_the_whole_day(server) -> None:
    _, body = _get(server, "/v1/cockpit/ledger?since=2026-06-01")
    assert body["events"]
    assert all(e["timestamp"][:10] >= "2026-06-01" for e in body["events"])


def test_event_detail_404_for_missing(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as ei:
        _get(server, "/v1/cockpit/ledger/job_alpha/999")
    assert ei.value.code == 404


# ---------------------------------------------------------------------------
# gated rollback request — reuses the owner-approval queue
# ---------------------------------------------------------------------------


def test_rollback_request_enqueues_owner_gated_proposal(server) -> None:
    status, card = _post(
        server,
        "/v1/cockpit/ledger/job_alpha/3/rollback",
        {"reason": "publish was premature"},
    )
    assert status == 201
    assert card["status"] == "PENDING"
    proposal_id = card["id"]

    # It shows up in the existing Approvals queue.
    _, approvals = _get(server, "/v1/cockpit/approvals")
    assert any(a["id"] == proposal_id for a in approvals["approvals"])

    # Approving it still requires the exact owner phrase (gate preserved).
    status, denied = _post(
        server,
        f"/v1/cockpit/approvals/{proposal_id}",
        {"decision": "approve", "authorization": "please"},
    )
    assert status == 403
