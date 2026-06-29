"""Tests for the cockpit API cross-origin (CORS) support.

Hermetic: each test starts the real stdlib cockpit server on a random loopback
port with a tmp HERMES_HOME, then drives it with ``urllib`` — exercising the
opt-in CORS allowlist, the OPTIONS preflight (including Chrome Private Network
Access), and the default-on first-party allowlist that lets the public cockpit
reach a locally-running gateway. No network, no third-party deps.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit.server import _resolve_cors_origins, serve


TOKEN = "test-cockpit-token-123"
ALLOWED = "https://musehq.io"
DENIED = "https://evil.example"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # Default CORS allowlist unless a test overrides it.
    monkeypatch.delenv("HERMES_COCKPIT_CORS_ORIGINS", raising=False)
    return tmp_path


def _url(server, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _request(server, path: str, *, method: str = "GET", origin: str | None = None,
             extra: dict[str, str] | None = None):
    req = urllib.request.Request(_url(server, path), method=method)
    if origin:
        req.add_header("Origin", origin)
    for k, v in (extra or {}).items():
        req.add_header(k, v)
    return urllib.request.urlopen(req, timeout=10)


# ---------------------------------------------------------------------------
# _resolve_cors_origins (pure)
# ---------------------------------------------------------------------------


def test_resolve_defaults_to_first_party(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_COCKPIT_CORS_ORIGINS", raising=False)
    origins = _resolve_cors_origins()
    assert "https://musehq.io" in origins
    assert "https://www.musehq.io" in origins


def test_resolve_env_extends_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_COCKPIT_CORS_ORIGINS", "https://a.example, https://b.example/")
    origins = _resolve_cors_origins()
    assert "https://musehq.io" in origins  # defaults preserved
    assert "https://a.example" in origins
    assert "https://b.example" in origins  # trailing slash normalized off


def test_resolve_env_off_clears_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_COCKPIT_CORS_ORIGINS", "off")
    assert _resolve_cors_origins() == frozenset()


def test_resolve_explicit_added_even_when_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_COCKPIT_CORS_ORIGINS", "none")
    origins = _resolve_cors_origins(["https://tunnel.example/"])
    assert origins == frozenset({"https://tunnel.example"})


# ---------------------------------------------------------------------------
# HTTP behavior
# ---------------------------------------------------------------------------


def test_cors_header_for_allowed_origin(home: Path) -> None:
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    try:
        resp = _request(srv, "/v1/health", origin=ALLOWED)
        assert resp.headers.get("Access-Control-Allow-Origin") == ALLOWED
        assert "Origin" in (resp.headers.get("Vary") or "")
    finally:
        srv.shutdown()


def test_no_cors_header_for_unknown_origin(home: Path) -> None:
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    try:
        resp = _request(srv, "/v1/health", origin=DENIED)
        assert resp.headers.get("Access-Control-Allow-Origin") is None
    finally:
        srv.shutdown()


def test_no_cors_header_when_disabled(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_COCKPIT_CORS_ORIGINS", "off")
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    try:
        resp = _request(srv, "/v1/health", origin=ALLOWED)
        assert resp.headers.get("Access-Control-Allow-Origin") is None
    finally:
        srv.shutdown()


def test_preflight_allows_origin_and_private_network(home: Path) -> None:
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    try:
        resp = _request(
            srv,
            "/v1/cockpit/pair/start",
            method="OPTIONS",
            origin=ALLOWED,
            extra={
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
                "Access-Control-Request-Private-Network": "true",
            },
        )
        assert resp.status == 204
        assert resp.headers.get("Access-Control-Allow-Origin") == ALLOWED
        methods = resp.headers.get("Access-Control-Allow-Methods") or ""
        assert "POST" in methods and "OPTIONS" in methods
        allow_headers = (resp.headers.get("Access-Control-Allow-Headers") or "").lower()
        assert "authorization" in allow_headers
        assert resp.headers.get("Access-Control-Allow-Private-Network") == "true"
    finally:
        srv.shutdown()


def test_preflight_unknown_origin_is_501(home: Path) -> None:
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            _request(srv, "/v1/health", method="OPTIONS", origin=DENIED)
        assert exc.value.code == 501
    finally:
        srv.shutdown()
