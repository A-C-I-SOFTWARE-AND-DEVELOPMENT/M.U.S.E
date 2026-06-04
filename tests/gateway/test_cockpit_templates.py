"""End-to-end tests for GET /v1/cockpit/templates.

Owner-defined prompt templates read from
``${HERMES_HOME}/cockpit/templates.json``; honest-empty when absent. Hermetic:
the real stdlib server on a random loopback port with a tmp HERMES_HOME.
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
    return tmp_path


@pytest.fixture()
def server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _get(server, path: str):
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}{path}", method="GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def test_templates_honest_empty_when_absent(server) -> None:
    status, body = _get(server, "/v1/cockpit/templates")
    assert status == 200
    assert body == {"templates": []}


def test_templates_requires_auth(server) -> None:
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}/v1/cockpit/templates")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=10)
    assert exc.value.code == 401


def test_templates_reads_owner_file_and_skips_malformed(server, home: Path) -> None:
    cockpit = home / "cockpit"
    cockpit.mkdir(parents=True, exist_ok=True)
    (cockpit / "templates.json").write_text(
        json.dumps({"templates": [
            {"id": "build", "title": "Build a feature", "body": "## Goal\n..."},
            {"id": "", "title": "no id", "body": "x"},   # skipped — blank id
            {"id": "bad"},                                  # skipped — no title/body
            "not-an-object",                                # skipped — not a dict
        ]}),
        encoding="utf-8",
    )
    status, body = _get(server, "/v1/cockpit/templates")
    assert status == 200
    assert [t["id"] for t in body["templates"]] == ["build"]
    assert body["templates"][0]["title"] == "Build a feature"


def test_templates_accepts_bare_list(server, home: Path) -> None:
    cockpit = home / "cockpit"
    cockpit.mkdir(parents=True, exist_ok=True)
    (cockpit / "templates.json").write_text(
        json.dumps([{"id": "fix", "title": "Fix a bug", "body": "## Bug\n..."}]),
        encoding="utf-8",
    )
    status, body = _get(server, "/v1/cockpit/templates")
    assert status == 200
    assert [t["id"] for t in body["templates"]] == ["fix"]


def test_templates_corrupt_file_is_honest_empty(server, home: Path) -> None:
    cockpit = home / "cockpit"
    cockpit.mkdir(parents=True, exist_ok=True)
    (cockpit / "templates.json").write_text("{not json", encoding="utf-8")
    status, body = _get(server, "/v1/cockpit/templates")
    assert status == 200
    assert body == {"templates": []}
