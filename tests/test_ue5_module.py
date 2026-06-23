"""Tests for hermes_cli.jarvis_prime.research_fabric.ue5 — no network, no UE.

All Remote Control traffic goes through the single ``_http`` seam,
which these tests monkeypatch; spawning is proven gated by failing the
test if ``subprocess.Popen`` is ever reached without the owner grant.
"""

from __future__ import annotations

import json

import pytest

from hermes_cli.jarvis_prime.axiom_bridge import get_bridge, reset_bridge
from hermes_cli.jarvis_prime.research_fabric import ue5, ue5_bridge


@pytest.fixture(autouse=True)
def _fresh_bridge(monkeypatch: pytest.MonkeyPatch):
    # CI exports muse_AXIOM_GATES=0 for hermeticity; these tests assert
    # chain events against the per-test HERMES_HOME, so re-enable it.
    monkeypatch.delenv("muse_AXIOM_GATES", raising=False)
    reset_bridge()
    yield
    reset_bridge()


def test_ping_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ue5, "_http", lambda method, url, body, timeout: {"EngineVersion": "5.4"}
    )
    result = ue5.ping()
    assert result["ok"] is True
    assert result["info"] == {"EngineVersion": "5.4"}
    events = [e for e in get_bridge().tail(5) if e["kind"] == "ue5.ping"]
    assert events and events[-1]["payload"]["ok"] is True


def test_ping_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(method, url, body, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(ue5, "_http", boom)
    result = ue5.ping()
    assert result["ok"] is False
    assert "connection refused" in result["error"]


def test_discover_node_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ue5, "_http", lambda method, url, body, timeout: {"InstanceId": "node-42"}
    )
    assert ue5.discover()["node_id"] == "node-42"

    # No identity in the payload -> stable host:port fallback.
    monkeypatch.setattr(ue5, "_http", lambda method, url, body, timeout: {})
    first = ue5.discover()["node_id"]
    second = ue5.discover()["node_id"]
    assert first == second
    assert len(first) == 12


def test_console_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    def capture(method, url, body, timeout):
        seen.update(method=method, url=url, body=body)
        return {}

    monkeypatch.setattr(ue5, "_http", capture)
    assert ue5.console("stat fps")["ok"] is True
    assert seen["method"] == "PUT"
    assert seen["url"].endswith("/remote/object/call")
    assert seen["body"]["objectPath"] == "/Script/Engine.Default__KismetSystemLibrary"
    assert seen["body"]["functionName"] == "ExecuteConsoleCommand"
    assert seen["body"]["parameters"] == {"Command": "stat fps"}


def test_py_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    def capture(method, url, body, timeout):
        seen.update(body=body)
        return {}

    monkeypatch.setattr(ue5, "_http", capture)
    script = "import unreal; unreal.log('muse')"
    assert ue5.py(script)["ok"] is True
    assert seen["body"]["objectPath"] == "/Engine/PythonTypes.Default__PythonScriptLibrary"
    assert seen["body"]["functionName"] == "ExecutePythonCommand"
    assert seen["body"]["parameters"] == {"PythonCommand": script}

    # Chain carries a fingerprint, never the script body.
    event = [e for e in get_bridge().tail(5) if e["kind"] == "ue5.py"][-1]
    assert event["payload"]["script_len"] == len(script)
    assert "script" not in event["payload"]
    assert len(event["payload"]["script_sha256"]) == 64


def test_render_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ue5.SPAWN_ENV, raising=False)
    monkeypatch.setattr(
        ue5.subprocess,
        "Popen",
        lambda *a, **k: pytest.fail("Popen reached without owner grant"),
    )
    result = ue5.launch_offscreen_render("/p.uproject", "/Game/Map", "/Game/Seq")
    assert result["spawned"] is False
    assert result["allowed"] is False
    assert "-RenderOffscreen" in result["command"]
    assert ue5.SPAWN_ENV in result["reason"]
    event = [e for e in get_bridge().tail(5) if e["kind"] == "ue5.render"][-1]
    assert event["payload"]["spawned"] is False


def test_render_spawns_when_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProc:
        pid = 4242

    monkeypatch.setenv(ue5.SPAWN_ENV, "1")
    monkeypatch.setattr(ue5.subprocess, "Popen", lambda *a, **k: FakeProc())
    result = ue5.launch_offscreen_render("/p.uproject", "/Game/Map", "/Game/Seq")
    assert result["spawned"] is True
    assert result["pid"] == 4242
    assert result["log"]
    event = [e for e in get_bridge().tail(5) if e["kind"] == "ue5.render"][-1]
    assert event["payload"]["spawned"] is True
    assert event["payload"]["pid"] == 4242


def test_shim_reexports() -> None:
    assert ue5_bridge.build_offscreen_render_command is ue5.build_offscreen_render_command
    assert ue5_bridge.remote_control_websocket is ue5.remote_control_websocket
    assert ue5_bridge.build_prompt_packet is ue5.build_prompt_packet
    # Pre-shim output, byte for byte.
    command = ue5_bridge.build_offscreen_render_command(
        "/p.uproject", "/Game/Map", "/Game/Seq", output_dir="/out"
    )
    assert command == (
        "UnrealEditor-Cmd /p.uproject /Game/Map -game "
        "'-LevelSequence=\"/Game/Seq\"' '-OutputDirectory=\"/out\"' -RenderOffscreen"
    )


def test_cli_ping(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    monkeypatch.setattr(ue5, "_http", lambda method, url, body, timeout: {})
    assert ue5.main(["ping"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
