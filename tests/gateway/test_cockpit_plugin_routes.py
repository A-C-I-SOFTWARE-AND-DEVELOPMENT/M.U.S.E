"""Tests for the authenticated cockpit plugin-route registry."""

from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from gateway.cockpit import handlers as h
from gateway.cockpit import plugin_routes
from gateway.cockpit import server as cockpit_server
from hermes_cli import plugins as cockpit_plugins


TOKEN = "test-cockpit-token-123"


def _health(_request: h.Request) -> h.JsonResponse:
    return h.JsonResponse(200, {"ok": True})


@pytest.fixture(autouse=True)
def _clear_plugin_routes():
    plugin_routes.clear_routes_for_tests()
    yield
    plugin_routes.clear_routes_for_tests()


def test_plugin_route_is_matched_with_path_params():
    plugin_routes.register_route(
        "muse-universe",
        "GET",
        "/v1/plugins/muse-universe/entities/{entity_id}",
        _health,
    )

    matched = plugin_routes.match(
        "GET", "/v1/plugins/muse-universe/entities/vsl_1"
    )

    assert matched is not None
    handler, requires_auth, params = matched
    assert handler is _health
    assert requires_auth is True
    assert params == {"entity_id": "vsl_1"}


def test_plugin_route_rejects_cross_plugin_prefix():
    with pytest.raises(ValueError, match="plugin prefix"):
        plugin_routes.register_route(
            "muse-universe", "GET", "/v1/plugins/other/status", _health
        )


def test_plugin_route_rejects_duplicate_method_and_path():
    path = "/v1/plugins/muse-universe/status"
    plugin_routes.register_route("muse-universe", "GET", path, _health)

    with pytest.raises(ValueError, match="already registered"):
        plugin_routes.register_route("muse-universe", "GET", path, _health)


def test_plugin_route_escapes_static_path_text():
    plugin_routes.register_route(
        "muse-universe",
        "GET",
        "/v1/plugins/muse-universe/entities.v1/{entity_id}",
        _health,
    )

    assert plugin_routes.match(
        "GET", "/v1/plugins/muse-universe/entitiesXv1/vsl_1"
    ) is None
    assert plugin_routes.match(
        "GET", "/v1/plugins/muse-universe/entities.v1/vsl_1"
    ) is not None


@pytest.mark.parametrize("plugin_id", ["", "muse.universe", "muse/universe"])
def test_plugin_route_rejects_malformed_plugin_id(plugin_id):
    with pytest.raises(ValueError, match="plugin id"):
        plugin_routes.register_route(
            plugin_id,
            "GET",
            "/v1/plugins/muse-universe/status",
            _health,
        )


@pytest.mark.parametrize(
    "path",
    [
        "/v1/plugins/muse-universe/entities/{entity-id}",
        "/v1/plugins/muse-universe/entities/{entity_id",
        "/v1/plugins/muse-universe/entities/entity_id}",
    ],
)
def test_plugin_route_rejects_malformed_path_template(path):
    with pytest.raises(ValueError, match="path template"):
        plugin_routes.register_route("muse-universe", "GET", path, _health)


def test_plugin_route_cannot_disable_authentication():
    with pytest.raises(ValueError, match="require authentication"):
        plugin_routes.register_route(
            "muse-universe",
            "GET",
            "/v1/plugins/muse-universe/status",
            _health,
            requires_auth=False,
        )


def test_server_lazily_discovers_and_matches_plugin_routes(monkeypatch):
    path = "/v1/plugins/muse-universe/status"
    discovered = []

    def discover_plugins():
        discovered.append(True)
        plugin_routes.register_route("muse-universe", "GET", path, _health)

    monkeypatch.setattr(cockpit_plugins, "discover_plugins", discover_plugins)
    monkeypatch.setattr(cockpit_server, "_PLUGIN_ROUTES_DISCOVERED", False)

    matched = cockpit_server._match("GET", path)

    assert discovered == [True]
    assert matched is not None
    handler, requires_auth, params = matched
    assert handler is _health
    assert requires_auth is True
    assert params == {}


def test_server_keeps_core_routes_ahead_of_plugin_fallback():
    matched = cockpit_server._match("GET", "/v1/health")

    assert matched is not None
    handler, requires_auth, params = matched
    assert handler is h.health
    assert requires_auth is False
    assert params == {}


def test_server_plugin_route_requires_authentication(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    plugin_routes.register_route(
        "muse-universe", "GET", "/v1/plugins/muse-universe/status", _health
    )
    server = cockpit_server.serve(host="127.0.0.1", port=0, token=TOKEN)
    host, port = server.server_address
    url = f"http://{host}:{port}/v1/plugins/muse-universe/status"
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(url, timeout=10)
        assert exc.value.code == 401

        request = urllib.request.Request(url)
        request.add_header("Authorization", f"Bearer {TOKEN}")
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 200
            assert response.read() == b'{"ok": true}'
    finally:
        server.shutdown()


def test_server_dispatches_patch_plugin_route(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    plugin_routes.register_route(
        "muse-universe", "PATCH", "/v1/plugins/muse-universe/status", _health
    )
    server = cockpit_server.serve(host="127.0.0.1", port=0, token=TOKEN)
    host, port = server.server_address
    request = urllib.request.Request(
        f"http://{host}:{port}/v1/plugins/muse-universe/status",
        data=b"{}",
        method="PATCH",
    )
    request.add_header("Authorization", f"Bearer {TOKEN}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 200
            assert response.read() == b'{"ok": true}'
    finally:
        server.shutdown()


def test_cors_preflight_advertises_patch_for_plugin_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    server = cockpit_server.serve(host="127.0.0.1", port=0, token=TOKEN)
    host, port = server.server_address
    request = urllib.request.Request(
        f"http://{host}:{port}/v1/plugins/muse-universe/status", method="OPTIONS"
    )
    request.add_header("Origin", "https://musehq.io")
    request.add_header("Access-Control-Request-Method", "PATCH")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 204
            assert "PATCH" in response.headers["Access-Control-Allow-Methods"]
    finally:
        server.shutdown()
