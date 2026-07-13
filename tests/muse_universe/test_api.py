from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from gateway.cockpit import plugin_routes
from gateway.cockpit import server as cockpit_server_module
from plugins.muse_universe import api
from plugins.muse_universe import reconcile as reconcile_module


TOKEN = "muse-universe-test-token"
BASE_PATH = "/v1/plugins/muse-universe"


@pytest.fixture(autouse=True)
def _isolate_api_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    api.reset_services_for_tests()
    plugin_routes.clear_routes_for_tests()
    yield
    plugin_routes.clear_routes_for_tests()
    api.reset_services_for_tests()


@pytest.fixture
def cockpit_server():
    for method, path, handler in api.cockpit_routes():
        plugin_routes.register_route("muse-universe", method, path, handler)
    server = cockpit_server_module.serve(host="127.0.0.1", port=0, token=TOKEN)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _url(server, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _get_json(server, path: str, *, token: str | None = TOKEN) -> dict:
    request = urllib.request.Request(_url(server, path))
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(
    server,
    path: str,
    payload: dict,
    *,
    token: str | None = TOKEN,
) -> dict:
    request = urllib.request.Request(
        _url(server, path),
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _realm_command(**overrides: object) -> dict:
    command = {
        "command_id": "cmd_realm",
        "command_type": "realm.create",
        "realm_id": "rlm_local",
        "actor_id": "ply_owner",
        "expected_version": 0,
        "payload": {
            "id": "rlm_local",
            "owner_id": "ply_owner",
            "name": "Local",
            "mode": "local",
            "visibility": "private",
        },
    }
    command.update(overrides)
    return command


def test_status_requires_bearer(cockpit_server, tmp_path: Path):
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get_json(cockpit_server, f"{BASE_PATH}/status", token=None)

    assert exc.value.code == 401
    assert not (tmp_path / ".hermes" / "universe" / "universe.db").exists()


def test_command_and_reconnect_round_trip(cockpit_server):
    created = _post_json(
        cockpit_server,
        f"{BASE_PATH}/commands",
        _realm_command(),
    )

    events = _get_json(
        cockpit_server,
        f"{BASE_PATH}/events?realm_id=rlm_local&since=0",
    )

    assert created["event"]["stream_version"] == 1
    assert events["cursor"] == created["event"]["sequence"]
    assert events["realm_version"] == 1
    assert len(events["events"]) == 1
    assert events["events"][0]["event_id"] == created["event"]["event_id"]


def test_empty_reconnect_never_moves_cursor_backwards(cockpit_server):
    _post_json(cockpit_server, f"{BASE_PATH}/commands", _realm_command())

    events = _get_json(
        cockpit_server,
        f"{BASE_PATH}/events?realm_id=rlm_local&since=999",
    )

    assert events["events"] == []
    assert events["cursor"] == 999
    assert events["realm_version"] == 1


def test_conflict_response_exposes_current_version(cockpit_server):
    _post_json(cockpit_server, f"{BASE_PATH}/commands", _realm_command())
    player = {
        "command_id": "cmd_player",
        "command_type": "player.create",
        "realm_id": "rlm_local",
        "actor_id": "ply_owner",
        "expected_version": 0,
        "payload": {"id": "ply_guest", "display_name": "Guest"},
    }
    _post_json(cockpit_server, f"{BASE_PATH}/commands", player)

    with pytest.raises(urllib.error.HTTPError) as exc:
        _post_json(
            cockpit_server,
            f"{BASE_PATH}/commands",
            {**player, "command_id": "cmd_conflict"},
        )

    body = json.loads(exc.value.read().decode("utf-8"))
    assert exc.value.code == 409
    assert body["error"]["code"] == "version_conflict"
    assert body["error"]["current_version"] == 1
    assert body["error"]["expected_version"] == 0


def test_api_never_echoes_owner_authorization(cockpit_server):
    secret = "a phrase that must never be reflected"
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post_json(
            cockpit_server,
            f"{BASE_PATH}/commands",
            {
                "command_id": "cmd_sensitive",
                "command_type": "release.promote",
                "realm_id": "rlm_local",
                "actor_id": "ply_owner",
                "expected_version": 0,
                "owner_authorization": secret,
                "payload": {"release_id": "rel_1"},
            },
        )

    body = exc.value.read().decode("utf-8")
    assert exc.value.code == 400
    assert secret not in body
    assert "owner_authorization" not in body


def test_service_factory_is_shared_per_resolved_home(tmp_path: Path):
    first_home = tmp_path / "one" / ".." / "one"
    second_home = tmp_path / "two"

    first = api.service_for_home(first_home)
    again = api.service_for_home(first_home.resolve())
    second = api.service_for_home(second_home)

    assert first is again
    assert first is not second
    assert first.store.path == first_home.resolve() / "universe" / "universe.db"


def test_dashboard_plugin_api_uses_dashboard_session_auth(monkeypatch: pytest.MonkeyPatch):
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    import hermes_cli.web_server as web_server

    monkeypatch.delattr(web_server.app.state, "bound_host", raising=False)
    path = "/api/plugins/muse-universe/status"

    with TestClient(web_server.app) as client:
        assert client.get(path).status_code == 401
        response = client.get(
            path,
            headers={web_server._SESSION_HEADER_NAME: web_server._SESSION_TOKEN},
        )
        assert response.status_code == 200
        assert response.json()["service"] == "muse-universe"


def test_snapshot_and_entity_routes_share_authoritative_service(cockpit_server):
    _post_json(cockpit_server, f"{BASE_PATH}/commands", _realm_command())
    query = urllib.parse.urlencode(
        {"realm_id": "rlm_local", "actor_id": "ply_owner"}
    )

    snapshot = _get_json(cockpit_server, f"{BASE_PATH}/snapshot?{query}")
    entity = _get_json(
        cockpit_server,
        f"{BASE_PATH}/entities/realm/rlm_local?{query}",
    )

    assert snapshot["realms"][0]["id"] == "rlm_local"
    assert entity["id"] == "rlm_local"


def test_reconcile_route_uses_shared_service_and_requested_realm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    def fake_reconcile(service, adapter=None, *, realm_id="rlm_local"):
        captured.update(service=service, adapter=adapter, realm_id=realm_id)
        return {"realm_id": realm_id, "created": 2}

    monkeypatch.setattr(reconcile_module, "reconcile_agents", fake_reconcile)
    shared = api.service_for_home(tmp_path)

    result = api.reconcile_data(
        {"realm_id": "rlm_team"},
        home=tmp_path,
    )

    assert result == {"realm_id": "rlm_team", "created": 2}
    assert captured["service"] is shared
    assert captured["realm_id"] == "rlm_team"


def test_unexpected_error_is_secret_safe_and_correlated(
    monkeypatch: pytest.MonkeyPatch,
):
    secret = "credential-value-that-must-not-leak"

    def fail_status():
        raise RuntimeError(secret)

    monkeypatch.setattr(api, "status_data", fail_status)
    response = api.handle_status(api.Request(method="GET", path="/status"))
    encoded = json.dumps(response.payload)

    assert response.status == 500
    assert response.payload["error"]["code"] == "internal_error"
    assert response.payload["error"]["correlation_id"]
    assert secret not in encoded
