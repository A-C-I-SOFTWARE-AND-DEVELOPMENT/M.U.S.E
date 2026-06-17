"""Tests for ``hermes gateway ensure`` — non-interactive, idempotent establish.

``gateway_ensure`` picks the right "establish" path per platform with no
prompts. These tests stub the platform predicates and the install/start
helpers so the dispatch logic is exercised on any host.
"""

import hermes_cli.gateway as gateway_cli


def _stub_platform(monkeypatch):
    """Default every platform predicate to False / no running gateway.

    Individual tests flip exactly the predicate they care about, so the
    dispatch order in ``gateway_ensure`` is asserted in isolation. Returns
    the same ``monkeypatch`` so callers can chain further overrides.
    """
    monkeypatch.setattr(gateway_cli, "is_managed", lambda: False)
    monkeypatch.setattr(gateway_cli, "is_termux", lambda: False)
    monkeypatch.setattr(gateway_cli, "is_container", lambda: False)
    monkeypatch.setattr(gateway_cli, "supports_systemd_services", lambda: False)
    monkeypatch.setattr(gateway_cli, "is_macos", lambda: False)
    monkeypatch.setattr(gateway_cli, "is_windows", lambda: False)
    monkeypatch.setattr(gateway_cli, "is_wsl", lambda: False)
    monkeypatch.setattr(gateway_cli, "find_gateway_pids", lambda *a, **k: [])
    return monkeypatch


def test_already_running_is_noop(monkeypatch):
    """A live gateway short-circuits: no install / start / background launch."""
    mp = _stub_platform(monkeypatch)
    mp.setattr(gateway_cli, "find_gateway_pids", lambda *a, **k: [4321])
    calls = []
    mp.setattr(gateway_cli, "supports_systemd_services", lambda: True)
    mp.setattr(gateway_cli, "systemd_install", lambda **k: calls.append("install"))
    mp.setattr(gateway_cli, "_report_background_launch", lambda: calls.append("bg") or 0)
    assert gateway_cli.gateway_ensure() == 0
    assert calls == []


def test_managed_is_noop(monkeypatch):
    """NixOS-managed installs defer to the system manager — establish nothing."""
    mp = _stub_platform(monkeypatch)
    mp.setattr(gateway_cli, "is_managed", lambda: True)
    mp.setattr(gateway_cli, "managed_error", lambda msg: None)
    calls = []
    mp.setattr(gateway_cli, "_report_background_launch", lambda: calls.append("bg") or 0)
    assert gateway_cli.gateway_ensure() == 0
    assert calls == []


def test_systemd_installs_enables_and_starts(monkeypatch):
    mp = _stub_platform(monkeypatch)
    mp.setattr(gateway_cli, "supports_systemd_services", lambda: True)
    seen = {}

    def fake_install(force=False, system=False, enable_on_startup=True, **k):
        seen["install"] = {"force": force, "system": system, "enable": enable_on_startup}

    def fake_start(system=False):
        seen["start"] = {"system": system}

    mp.setattr(gateway_cli, "systemd_install", fake_install)
    mp.setattr(gateway_cli, "systemd_start", fake_start)

    assert gateway_cli.gateway_ensure() == 0
    # Enabled on boot (auto-start on login) and started immediately.
    assert seen["install"] == {"force": False, "system": False, "enable": True}
    assert seen["start"] == {"system": False}


def test_systemd_unavailable_falls_back_to_background(monkeypatch):
    mp = _stub_platform(monkeypatch)
    mp.setattr(gateway_cli, "supports_systemd_services", lambda: True)

    def boom(**k):
        raise gateway_cli.UserSystemdUnavailableError("no user bus")

    mp.setattr(gateway_cli, "systemd_install", boom)
    fallback = []
    mp.setattr(gateway_cli, "_report_background_launch", lambda: fallback.append(1) or 0)

    assert gateway_cli.gateway_ensure() == 0
    assert fallback == [1]


def test_termux_uses_background(monkeypatch):
    mp = _stub_platform(monkeypatch)
    mp.setattr(gateway_cli, "is_termux", lambda: True)
    fallback = []
    mp.setattr(gateway_cli, "_report_background_launch", lambda: fallback.append(1) or 0)
    assert gateway_cli.gateway_ensure() == 0
    assert fallback == [1]


def test_macos_installs_and_starts(monkeypatch):
    mp = _stub_platform(monkeypatch)
    mp.setattr(gateway_cli, "is_macos", lambda: True)
    seen = []
    mp.setattr(gateway_cli, "launchd_install", lambda force=False: seen.append(("install", force)))
    mp.setattr(gateway_cli, "launchd_start", lambda: seen.append(("start",)))
    assert gateway_cli.gateway_ensure() == 0
    assert ("install", False) in seen
    assert ("start",) in seen


def test_unknown_platform_uses_background(monkeypatch):
    mp = _stub_platform(monkeypatch)
    fallback = []
    mp.setattr(gateway_cli, "_report_background_launch", lambda: fallback.append(1) or 0)
    assert gateway_cli.gateway_ensure() == 0
    assert fallback == [1]


def test_ensure_background_gateway_spawns_detached(monkeypatch, tmp_path):
    """The background escape hatch launches the run argv and logs to HERMES_HOME."""
    import hermes_cli.profiles as profiles

    monkeypatch.setattr(gateway_cli, "get_hermes_home", lambda: tmp_path)
    monkeypatch.setattr(gateway_cli, "_gateway_run_args_for_profile", lambda profile: ["echo", profile])
    monkeypatch.setattr(profiles, "get_active_profile_name", lambda: "default")

    captured = {}

    class FakeProc:
        pid = 9999

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(gateway_cli.subprocess, "Popen", fake_popen)

    pid = gateway_cli._ensure_background_gateway()
    assert pid == 9999
    assert captured["args"] == ["echo", "default"]
    # Log file created under $HERMES_HOME/logs/.
    assert (tmp_path / "logs" / "gateway.log").exists()
