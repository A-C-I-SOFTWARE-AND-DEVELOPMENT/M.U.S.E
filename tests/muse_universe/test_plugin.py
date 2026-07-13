from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from plugins.muse_universe import (
    COMMAND_SCHEMA,
    QUERY_SCHEMA,
    handle_command,
    handle_query,
    handle_slash,
    register,
)
from plugins.muse_universe import api


class RecordingContext:
    def __init__(self) -> None:
        self.routes: list[tuple[str, str, object]] = []
        self.tools: list[dict] = []
        self.commands: list[dict] = []

    def register_cockpit_route(self, method: str, path: str, handler) -> None:
        self.routes.append((method, path, handler))

    def register_tool(self, **kwargs) -> None:
        self.tools.append(kwargs)

    def register_command(self, name: str, handler, **kwargs) -> None:
        self.commands.append({"name": name, "handler": handler, **kwargs})


def test_register_exposes_routes_tools_and_slash_command():
    ctx = RecordingContext()

    register(ctx)

    assert {(method, path) for method, path, _ in ctx.routes} == {
        ("GET", "/v1/plugins/muse-universe/status"),
        ("GET", "/v1/plugins/muse-universe/catalog"),
        ("GET", "/v1/plugins/muse-universe/snapshot"),
        ("GET", "/v1/plugins/muse-universe/events"),
        (
            "GET",
            "/v1/plugins/muse-universe/entities/{entity_type}/{entity_id}",
        ),
        ("POST", "/v1/plugins/muse-universe/commands"),
        ("POST", "/v1/plugins/muse-universe/reconcile"),
    }
    assert {tool["name"] for tool in ctx.tools} == {
        "muse_universe_query",
        "muse_universe_command",
    }
    assert all(tool["toolset"] == "muse-universe" for tool in ctx.tools)
    assert ctx.commands[0]["name"] == "universe"


def test_tool_schemas_are_closed_and_do_not_accept_owner_phrases():
    assert QUERY_SCHEMA["parameters"]["additionalProperties"] is False
    assert COMMAND_SCHEMA["parameters"]["additionalProperties"] is False
    assert "owner_authorization" not in COMMAND_SCHEMA["parameters"]["properties"]
    assert "owner_phrase" not in COMMAND_SCHEMA["parameters"]["properties"]


def test_command_tool_returns_sorted_json_and_rejects_owner_phrase(
    tmp_path: Path,
):
    api.reset_services_for_tests()
    secret = "never reflect this phrase"

    raw = handle_command(
        {
            "command_id": "cmd_1",
            "command_type": "release.promote",
            "realm_id": "rlm_local",
            "actor_id": "ply_owner",
            "expected_version": 0,
            "owner_phrase": secret,
            "payload": {"release_id": "rel_1"},
        },
        hermes_home=tmp_path,
    )

    assert raw == json.dumps(json.loads(raw), sort_keys=True)
    assert json.loads(raw)["error"]["code"] == "validation_error"
    assert secret not in raw
    assert "owner_phrase" not in raw


def test_query_tool_reuses_resumable_event_contract(tmp_path: Path):
    api.reset_services_for_tests()
    command = {
        "command_id": "cmd_realm",
        "command_type": "realm.create",
        "realm_id": "rlm_local",
        "actor_id": "ply_owner",
        "expected_version": 0,
        "payload": {
            "id": "rlm_local",
            "owner_id": "ply_owner",
            "mode": "local",
            "visibility": "private",
        },
    }
    created = json.loads(handle_command(command, hermes_home=tmp_path))

    result = json.loads(
        handle_query(
            {"query": "events", "realm_id": "rlm_local", "since": 0},
            hermes_home=tmp_path,
        )
    )

    assert result["cursor"] == created["event"]["sequence"]
    assert result["realm_version"] == 1


def test_slash_command_defaults_to_shared_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    api.reset_services_for_tests()

    result = json.loads(handle_slash(""))

    assert result["service"] == "muse-universe"
    assert result["status"] == "ready"
    assert handle_slash("unknown") == (
        "Usage: /universe [status|events [realm_id] [since]|reconcile]"
    )


def test_plugin_manifest_uses_cockpit_safe_id_and_declares_tools():
    manifest_path = Path(__file__).parents[2] / "plugins" / "muse_universe" / "plugin.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "muse-universe"
    assert manifest["provides_tools"] == [
        "muse_universe_query",
        "muse_universe_command",
    ]


def test_dashboard_manifest_is_a_supporting_panel():
    dashboard = Path(__file__).parents[2] / "plugins" / "muse_universe" / "dashboard"
    manifest = json.loads((dashboard / "manifest.json").read_text(encoding="utf-8"))
    source = (dashboard / "dist" / "index.js").read_text(encoding="utf-8")

    assert manifest["tab"]["path"] == "/universe"
    assert manifest["api"] == "plugin_api.py"
    assert "/api/plugins/muse-universe/status" in source
    assert "__HERMES_PLUGIN_SDK__" in source
    assert "prompt.submit" not in source
