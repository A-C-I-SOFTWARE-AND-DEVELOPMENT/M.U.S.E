"""Regression tests for the Nexus static-shell alias and /nexus/health probe
on the cockpit gateway.

Grain B (per the swarm-decompose plan): the cockpit serves the same SPA
shell under both /cockpit/ and /nexus/, and exposes an unauthenticated
liveness probe at /nexus/health that mirrors /v1/health. These tests pin
that contract so a future refactor can't quietly regress it.

Hermetic: starts the real stdlib server on a random loopback port with a
tmp HERMES_HOME and a known token, then drives it with ``urllib``. Same
pattern as tests/gateway/test_cockpit_api.py.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit.server import serve


TOKEN = "test-cockpit-token-nexus"


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


def _get_raw(server, path: str, token: str | None = None):
    """GET that returns (status, content_type, body_bytes) without parsing."""
    req = urllib.request.Request(_url(server, path), method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()


def test_nexus_root_serves_spa(server) -> None:
    """GET /nexus/ â†’ 200, text/html, body starts with '<!doctype html>'."""
    status, ctype, body = _get_raw(server, "/nexus/")
    assert status == 200
    assert ctype.startswith("text/html")
    # Body is bytes; the bundled SPA shell begins with the HTML5 doctype.
    assert body[:15].lower().startswith(b"<!doctype html>")


def test_nexus_subpath_serves_spa(server) -> None:
    """GET /nexus/anything â†’ 200, html (SPA fallback so the SPA can route)."""
    status, ctype, body = _get_raw(server, "/nexus/anything")
    assert status == 200
    assert ctype.startswith("text/html")
    assert body[:15].lower().startswith(b"<!doctype html>")


def test_nexus_health_unauthed(server) -> None:
    """GET /nexus/health â†’ 200, JSON {ok: true, ...} with NO bearer token."""
    status, ctype, body = _get_raw(server, "/nexus/health", token=None)
    assert status == 200
    assert "application/json" in ctype
    payload = json.loads(body)
    assert payload["ok"] is True
    # Mirrors /v1/health so the rest of the envelope must also be present.
    assert payload["service"] == "muse-cockpit"
    assert payload["api_version"]


def test_cockpit_root_still_works(server) -> None:
    """GET /cockpit/ â†’ 200, html â€” no regression from adding /nexus routes."""
    status, ctype, body = _get_raw(server, "/cockpit/")
    assert status == 200
    assert ctype.startswith("text/html")
    assert body[:15].lower().startswith(b"<!doctype html>")
