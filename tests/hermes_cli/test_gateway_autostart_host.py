"""Tests for host-side ``gateway.auto_start`` honoring + non-interactive install.

Covers:
* ``gateway_auto_start_enabled`` — the host config read.
* ``maybe_auto_establish_gateway`` — opt-in, idempotent, best-effort wiring
  called from the interactive CLI launch.
* ``systemd_install(assume_yes=...)`` — the legacy-unit prompt is skipped when
  the non-interactive ``gateway ensure`` path drives the install.
"""

import hermes_cli.gateway as gateway_cli


# ---------------------------------------------------------------------------
# gateway_auto_start_enabled
# ---------------------------------------------------------------------------

def test_auto_start_enabled_true(monkeypatch):
    monkeypatch.setattr(gateway_cli, "read_raw_config", lambda: {"gateway": {"auto_start": True}})
    assert gateway_cli.gateway_auto_start_enabled() is True


def test_auto_start_enabled_false(monkeypatch):
    monkeypatch.setattr(gateway_cli, "read_raw_config", lambda: {"gateway": {"auto_start": False}})
    assert gateway_cli.gateway_auto_start_enabled() is False


def test_auto_start_enabled_missing_key(monkeypatch):
    monkeypatch.setattr(gateway_cli, "read_raw_config", lambda: {"gateway": {"proxy_url": "x"}})
    assert gateway_cli.gateway_auto_start_enabled() is False


def test_auto_start_enabled_no_section(monkeypatch):
    monkeypatch.setattr(gateway_cli, "read_raw_config", lambda: {"model": "foo"})
    assert gateway_cli.gateway_auto_start_enabled() is False


def test_auto_start_enabled_config_error(monkeypatch):
    def boom():
        raise RuntimeError("bad config")

    monkeypatch.setattr(gateway_cli, "read_raw_config", boom)
    assert gateway_cli.gateway_auto_start_enabled() is False


# ---------------------------------------------------------------------------
# maybe_auto_establish_gateway
# ---------------------------------------------------------------------------

def _wire(monkeypatch, *, enabled, container=False, managed=False, running=False, installed=False):
    """Stub the establish preconditions and reset the once-per-process guard."""
    monkeypatch.setattr(gateway_cli, "_AUTO_ESTABLISH_ATTEMPTED", False)
    monkeypatch.setattr(gateway_cli, "gateway_auto_start_enabled", lambda: enabled)
    monkeypatch.setattr(gateway_cli, "is_container", lambda: container)
    monkeypatch.setattr(gateway_cli, "is_managed", lambda: managed)
    monkeypatch.setattr(gateway_cli, "find_gateway_pids", lambda *a, **k: ([1234] if running else []))
    monkeypatch.setattr(gateway_cli, "_is_service_installed", lambda: installed)
    calls = []
    monkeypatch.setattr(gateway_cli, "gateway_ensure", lambda *a, **k: calls.append(1) or 0)
    return calls


def test_maybe_establish_noop_when_flag_off(monkeypatch):
    calls = _wire(monkeypatch, enabled=False)
    gateway_cli.maybe_auto_establish_gateway()
    assert calls == []


def test_maybe_establish_noop_in_container(monkeypatch):
    calls = _wire(monkeypatch, enabled=True, container=True)
    gateway_cli.maybe_auto_establish_gateway()
    assert calls == []


def test_maybe_establish_noop_when_managed(monkeypatch):
    calls = _wire(monkeypatch, enabled=True, managed=True)
    gateway_cli.maybe_auto_establish_gateway()
    assert calls == []


def test_maybe_establish_noop_when_running(monkeypatch):
    calls = _wire(monkeypatch, enabled=True, running=True)
    gateway_cli.maybe_auto_establish_gateway()
    assert calls == []


def test_maybe_establish_noop_when_service_installed(monkeypatch):
    calls = _wire(monkeypatch, enabled=True, installed=True)
    gateway_cli.maybe_auto_establish_gateway()
    assert calls == []


def test_maybe_establish_runs_when_enabled_and_not_established(monkeypatch):
    calls = _wire(monkeypatch, enabled=True)
    gateway_cli.maybe_auto_establish_gateway()
    assert calls == [1]


def test_maybe_establish_runs_at_most_once_per_process(monkeypatch):
    calls = _wire(monkeypatch, enabled=True)
    gateway_cli.maybe_auto_establish_gateway()
    gateway_cli.maybe_auto_establish_gateway()  # guard should block the second
    assert calls == [1]


def test_maybe_establish_swallows_errors(monkeypatch):
    monkeypatch.setattr(gateway_cli, "_AUTO_ESTABLISH_ATTEMPTED", False)
    monkeypatch.setattr(gateway_cli, "gateway_auto_start_enabled", lambda: True)
    monkeypatch.setattr(gateway_cli, "is_container", lambda: False)
    monkeypatch.setattr(gateway_cli, "is_managed", lambda: False)
    monkeypatch.setattr(gateway_cli, "find_gateway_pids", lambda *a, **k: [])

    def boom():
        raise RuntimeError("service probe failed")

    monkeypatch.setattr(gateway_cli, "_is_service_installed", boom)
    # Must not raise — best-effort on the interactive launch path.
    gateway_cli.maybe_auto_establish_gateway()


# ---------------------------------------------------------------------------
# systemd_install(assume_yes=...) — skip the legacy-unit prompt
# ---------------------------------------------------------------------------

def _stub_systemd_install_internals(monkeypatch, tmp_path):
    """Make systemd_install reach its 'already installed' early return cheaply."""
    prompts = []
    removed = []
    monkeypatch.setattr(gateway_cli, "has_legacy_hermes_units", lambda: True)
    monkeypatch.setattr(gateway_cli, "print_legacy_unit_warning", lambda *a, **k: None)
    monkeypatch.setattr(gateway_cli, "prompt_yes_no", lambda *a, **k: prompts.append(a) or True)
    monkeypatch.setattr(
        gateway_cli, "remove_legacy_hermes_units",
        lambda *a, **k: removed.append((a, k)) or (0, []),
    )
    unit = tmp_path / "hermes-gateway.service"
    unit.write_text("unit\n")
    monkeypatch.setattr(gateway_cli, "get_systemd_unit_path", lambda system=False: unit)
    monkeypatch.setattr(gateway_cli, "systemd_unit_is_current", lambda system=False: True)
    return prompts, removed


def test_systemd_install_assume_yes_skips_legacy_prompt(monkeypatch, tmp_path, capsys):
    prompts, removed = _stub_systemd_install_internals(monkeypatch, tmp_path)
    gateway_cli.systemd_install(system=False, assume_yes=True)
    assert prompts == []          # no interactive prompt
    assert len(removed) == 1      # legacy units removed unattended


def test_systemd_install_interactive_prompts_for_legacy(monkeypatch, tmp_path, capsys):
    prompts, removed = _stub_systemd_install_internals(monkeypatch, tmp_path)
    gateway_cli.systemd_install(system=False, assume_yes=False)
    assert len(prompts) == 1      # default path still asks
    assert len(removed) == 1      # answered yes (stub returns True)


# ---------------------------------------------------------------------------
# install_linux_gateway_from_setup(assume_yes=...) — wizard unattended path
# ---------------------------------------------------------------------------

def test_install_from_setup_assume_yes_skips_scope_prompt(monkeypatch):
    """assume_yes installs a user-scope service with no scope prompt, threading
    assume_yes into systemd_install (so the legacy prompt is skipped too)."""
    calls = {}
    scope_prompts = []

    def fake_systemd_install(force=False, system=False, run_as_user=None, enable_on_startup=True, assume_yes=False):
        calls["systemd_install"] = {"system": system, "enable": enable_on_startup, "assume_yes": assume_yes}

    monkeypatch.setattr(gateway_cli, "systemd_install", fake_systemd_install)
    monkeypatch.setattr(
        gateway_cli, "prompt_linux_gateway_install_scope",
        lambda: scope_prompts.append("asked") or "user",
    )

    scope, did = gateway_cli.install_linux_gateway_from_setup(enable_on_startup=True, assume_yes=True)
    assert scope == "user"
    assert did is True
    assert scope_prompts == []  # no interactive scope prompt
    assert calls["systemd_install"] == {"system": False, "enable": True, "assume_yes": True}


def test_install_from_setup_interactive_still_prompts_scope(monkeypatch):
    """assume_yes=False keeps the interactive scope prompt (cancel → no install)."""
    called = []
    monkeypatch.setattr(gateway_cli, "systemd_install", lambda **k: called.append(k))
    monkeypatch.setattr(gateway_cli, "prompt_linux_gateway_install_scope", lambda: None)
    scope, did = gateway_cli.install_linux_gateway_from_setup(assume_yes=False)
    assert scope is None
    assert did is False
    assert called == []  # cancelled at the scope prompt — nothing installed
