"""Tests for `_ensure_uv_for_termux` — must never compile uv from source.

Regression for the Termux/Android hang where `pip install uv` fell back to
building the uv (Rust) sdist for 30+ minutes ("Building wheel for uv ...").
"""

from __future__ import annotations

import hermes_cli.main as main


def test_non_termux_returns_existing_uv_without_install(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "_is_termux_env", lambda *a, **k: False)
    monkeypatch.setattr(main.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(main.subprocess, "run", lambda *a, **k: calls.append((a, k)))

    assert main._ensure_uv_for_termux([main.sys.executable, "-m", "pip"]) == "/usr/bin/uv"
    assert calls == []  # never attempts an install off Termux


def test_termux_install_uses_only_binary_and_timeout(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "_is_termux_env", lambda *a, **k: True)
    monkeypatch.delenv("HERMES_SKIP_UV", raising=False)
    # No uv before; still no uv after the (mocked, no-op) install.
    monkeypatch.setattr(main.shutil, "which", lambda _: None)

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs

    monkeypatch.setattr(main.subprocess, "run", _fake_run)

    result = main._ensure_uv_for_termux(["py", "-m", "pip"])

    # Never builds from source, always bounded.
    assert "--only-binary=:all:" in captured["cmd"]
    assert captured["cmd"][-1] == "uv"
    assert captured["kwargs"].get("timeout") is not None
    assert captured["kwargs"].get("check") is False
    # No wheel installed → returns None so the caller falls back to pip.
    assert result is None


def test_termux_skip_env_short_circuits(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "_is_termux_env", lambda *a, **k: True)
    monkeypatch.setattr(main.shutil, "which", lambda _: None)
    monkeypatch.setattr(main.subprocess, "run", lambda *a, **k: calls.append(1))
    monkeypatch.setenv("HERMES_SKIP_UV", "1")

    assert main._ensure_uv_for_termux(["py", "-m", "pip"]) is None
    assert calls == []  # never attempts an install when skipped


def test_termux_returns_uv_when_wheel_installs(monkeypatch):
    monkeypatch.setattr(main, "_is_termux_env", lambda *a, **k: True)
    monkeypatch.delenv("HERMES_SKIP_UV", raising=False)
    # Simulate: no uv before install, uv present after.
    seen = {"n": 0}

    def _which(_):
        seen["n"] += 1
        return None if seen["n"] == 1 else "/data/data/com.termux/files/usr/bin/uv"

    monkeypatch.setattr(main.shutil, "which", _which)
    monkeypatch.setattr(main.subprocess, "run", lambda *a, **k: None)

    assert main._ensure_uv_for_termux(["py", "-m", "pip"]).endswith("/bin/uv")


def test_termux_install_timeout_falls_back_to_pip(monkeypatch):
    monkeypatch.setattr(main, "_is_termux_env", lambda *a, **k: True)
    monkeypatch.delenv("HERMES_SKIP_UV", raising=False)
    monkeypatch.setattr(main.shutil, "which", lambda _: None)

    def _timeout(*a, **k):
        raise main.subprocess.TimeoutExpired(cmd="uv", timeout=180)

    monkeypatch.setattr(main.subprocess, "run", _timeout)

    # A stalled download must not propagate — return None → pip fallback.
    assert main._ensure_uv_for_termux(["py", "-m", "pip"]) is None
