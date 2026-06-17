"""The NEXUS PWA, served same-origin by the cockpit HTTP server under /nexus/.

This is what lets a phone running MUSE in Termux reach the whole app + API on a
single http loopback origin (http://127.0.0.1:8765/nexus/) with no mixed-content
barrier. Boots the real server on an ephemeral port, points it at a throwaway
"dist" via NEXUS_DIST_DIR, and confirms: the shell is served unauthenticated,
assets resolve, deep routes fall back to index.html (SPA), traversal can't leak
source, the /v1/* API still takes precedence, and the mount cleanly 404s when no
build is present.
"""

from __future__ import annotations

import http.client

import pytest

from gateway.cockpit import server as srv


def _get(port: int, path: str) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()


@pytest.fixture()
def dist(tmp_path):
    d = tmp_path / "nexus-dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<!doctype html><title>NEXUS</title><div id=root></div>")
    (d / "assets" / "app.js").write_text("console.log('nexus')")
    (d / "manifest.webmanifest").write_text('{"name":"NEXUS"}')
    return d


@pytest.fixture()
def cockpit(tmp_path, monkeypatch, dist):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("NEXUS_DIST_DIR", str(dist))
    httpd = srv.serve("127.0.0.1", 0, token="testtoken", responder=lambda prompt, history: iter(()))
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()


def test_serves_nexus_index_unauthenticated(cockpit):
    for path in ("/nexus/", "/nexus"):
        status, body = _get(cockpit, path)
        assert status == 200, path
        assert b"NEXUS" in body, path


def test_serves_nexus_asset(cockpit):
    status, body = _get(cockpit, "/nexus/assets/app.js")
    assert status == 200
    assert b"console.log('nexus')" in body


def test_deep_route_falls_back_to_index(cockpit):
    # A client-side route (no file) returns the SPA shell so HashRouter can route.
    status, body = _get(cockpit, "/nexus/repo")
    assert status == 200
    assert b"<div id=root>" in body


def test_nexus_traversal_cannot_leak_source(cockpit):
    for path in (
        "/nexus/../../gateway/cockpit/server.py",
        "/nexus/..%2f..%2fserver.py",
    ):
        status, body = _get(cockpit, path)
        assert b"_serve_nexus" not in body
        assert b"ThreadingHTTPServer" not in body
        assert status in (200, 404)


def test_api_takes_precedence_over_nexus(cockpit):
    # /v1/health must hit the API, never the static mount.
    import json

    status, body = _get(cockpit, "/v1/health")
    assert status == 200
    assert json.loads(body)["ok"] is True


def test_nexus_mount_absent_without_build(tmp_path, monkeypatch):
    # With NEXUS_DIST_DIR pointing at a build-less dir, the mount 404s and nothing
    # else changes (the cockpit's own static UI is unaffected).
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("NEXUS_DIST_DIR", str(tmp_path / "does-not-exist"))
    httpd = srv.serve("127.0.0.1", 0, token="t", responder=lambda prompt, history: iter(()))
    try:
        port = httpd.server_address[1]
        status, _ = _get(port, "/nexus/")
        assert status == 404
        # The cockpit's own shell still serves.
        status2, _ = _get(port, "/cockpit/")
        assert status2 == 200
    finally:
        httpd.shutdown()
