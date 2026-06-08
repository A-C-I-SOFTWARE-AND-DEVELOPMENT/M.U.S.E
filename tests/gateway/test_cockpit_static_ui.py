"""The browser cockpit's static UI shell, served by the cockpit HTTP server.

Boots the real server on an ephemeral loopback port and hits it with
http.client. Confirms: the shell is served (unauthenticated), assets resolve,
path traversal can't leak source, and the `/v1/*` API still takes precedence
over the static handler.
"""

from __future__ import annotations

import http.client
import json

import pytest

from gateway.cockpit import server as srv


def _get(port: int, path: str, token: str | None = None) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        conn.request("GET", path, headers=headers)
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()


@pytest.fixture()
def cockpit(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    httpd = srv.serve(
        "127.0.0.1", 0, token="testtoken",
        responder=lambda prompt, history: iter(()),
    )
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()


def test_serves_cockpit_index_unauthenticated(cockpit):
    # The shell is plain HTML/CSS/JS; it must load without a token (its API
    # calls carry the bearer token afterward).
    for path in ("/cockpit/", "/cockpit", "/"):
        status, body = _get(cockpit, path)
        assert status == 200, path
        assert b"M.U.S.E." in body, path
        assert b"Multi-Use Synaptic Entity" in body


def test_serves_tokens_css(cockpit):
    status, body = _get(cockpit, "/cockpit/tokens.css")
    assert status == 200
    assert b"--void" in body and b"--ring-1" in body


def test_traversal_cannot_leak_source(cockpit):
    status, body = _get(cockpit, "/cockpit/../../gateway/cockpit/server.py")
    # Never serve the python source; either 404 or the SPA index fallback.
    assert b"_make_handler" not in body
    assert b"def _serve_static" not in body
    assert status in (200, 404)


def test_api_takes_precedence_over_static(cockpit):
    # /v1/health is unauthenticated and must hit the API, not the static handler.
    status, body = _get(cockpit, "/v1/health")
    assert status == 200
    assert json.loads(body)["ok"] is True


def test_api_route_still_requires_auth(cockpit):
    # A /v1/* route under the static prefix space must still reach the API and
    # enforce auth (proves the static hook didn't shadow the route table).
    status, _ = _get(cockpit, "/v1/cockpit/jobs")
    assert status == 401
