"""Tests for the ``muse doctor`` gateway-establishment nudge."""

import hermes_cli.doctor as doctor
import hermes_cli.gateway as gateway_cli


def _wire(monkeypatch, *, installed, running, auto_start, container=False, termux=False):
    monkeypatch.setattr(gateway_cli, "_is_service_installed", lambda: installed)
    monkeypatch.setattr(gateway_cli, "find_gateway_pids", lambda *a, **k: ([1] if running else []))
    monkeypatch.setattr(gateway_cli, "gateway_auto_start_enabled", lambda: auto_start)
    monkeypatch.setattr("hermes_constants.is_container", lambda: container)
    monkeypatch.setattr("hermes_constants.is_termux", lambda: termux)


def test_established_service_installed_is_quiet(monkeypatch):
    _wire(monkeypatch, installed=True, running=False, auto_start=False)
    issues: list[str] = []
    doctor._check_gateway_established(issues)
    assert issues == []  # established — no nudge, no issue


def test_established_running_is_quiet(monkeypatch):
    _wire(monkeypatch, installed=False, running=True, auto_start=True)
    issues: list[str] = []
    doctor._check_gateway_established(issues)
    assert issues == []


def test_container_is_skipped(monkeypatch):
    _wire(monkeypatch, installed=False, running=False, auto_start=True, container=True)
    issues: list[str] = []
    doctor._check_gateway_established(issues)
    assert issues == []  # reconciler owns the container path


def test_not_established_without_flag_is_info_only(monkeypatch, capsys):
    _wire(monkeypatch, installed=False, running=False, auto_start=False)
    issues: list[str] = []
    doctor._check_gateway_established(issues)
    # Informational nudge, but not a flagged issue when not opted in.
    assert issues == []
    out = capsys.readouterr().out
    assert "muse gateway ensure" in out


def test_not_established_with_flag_is_flagged_issue(monkeypatch, capsys):
    _wire(monkeypatch, installed=False, running=False, auto_start=True)
    issues: list[str] = []
    doctor._check_gateway_established(issues)
    assert len(issues) == 1
    assert "gateway ensure" in issues[0]
    assert "auto_start" in issues[0]
