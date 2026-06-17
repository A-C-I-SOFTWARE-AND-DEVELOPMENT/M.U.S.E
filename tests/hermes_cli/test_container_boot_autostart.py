"""Tests for the opt-in ``gateway.auto_start`` flag in container_boot.

The default container behaviour (auto-restart only profiles whose last
recorded state was ``running``) is unchanged when the flag is absent. When a
profile's ``config.yaml`` sets ``gateway.auto_start: true``, the gateway also
comes up from a fresh / cleanly-stopped state on container boot — but a
``startup_failed`` state still keeps it down (crash-loop guard).
"""

import json

from hermes_cli import container_boot


class TestShouldAutostart:
    def test_running_always_starts(self):
        assert container_boot._should_autostart("running", False) is True
        assert container_boot._should_autostart("running", True) is True

    def test_fresh_state_off_by_default(self):
        assert container_boot._should_autostart(None, False) is False
        assert container_boot._should_autostart("stopped", False) is False
        assert container_boot._should_autostart("starting", False) is False

    def test_auto_start_brings_up_fresh_or_stopped(self):
        assert container_boot._should_autostart(None, True) is True
        assert container_boot._should_autostart("stopped", True) is True
        assert container_boot._should_autostart("starting", True) is True

    def test_auto_start_respects_crash_loop_guard(self):
        # startup_failed stays down even when auto_start is opted into.
        assert container_boot._should_autostart("startup_failed", True) is False
        assert container_boot._should_autostart("startup_failed", False) is False


class TestReadAutoStart:
    def test_missing_config_is_off(self, tmp_path):
        assert container_boot._read_auto_start(tmp_path) is False

    def test_true_flag(self, tmp_path):
        (tmp_path / "config.yaml").write_text("gateway:\n  auto_start: true\n")
        assert container_boot._read_auto_start(tmp_path) is True

    def test_false_flag(self, tmp_path):
        (tmp_path / "config.yaml").write_text("gateway:\n  auto_start: false\n")
        assert container_boot._read_auto_start(tmp_path) is False

    def test_absent_key_is_off(self, tmp_path):
        (tmp_path / "config.yaml").write_text("gateway:\n  proxy_url: http://x\n")
        assert container_boot._read_auto_start(tmp_path) is False

    def test_no_gateway_section_is_off(self, tmp_path):
        (tmp_path / "config.yaml").write_text("model: foo\n")
        assert container_boot._read_auto_start(tmp_path) is False

    def test_unparseable_is_off(self, tmp_path):
        (tmp_path / "config.yaml").write_text("gateway: [unbalanced\n  : bad\n")
        assert container_boot._read_auto_start(tmp_path) is False


class TestReconcileAutoStart:
    def _default_action(self, actions):
        return next(a for a in actions if a.profile == "default")

    def test_default_profile_registered_without_flag(self, tmp_path):
        actions = container_boot.reconcile_profile_gateways(
            hermes_home=tmp_path, scandir=tmp_path / "service", dry_run=True,
        )
        assert self._default_action(actions).action == "registered"

    def test_default_profile_starts_when_auto_start_set(self, tmp_path):
        (tmp_path / "config.yaml").write_text("gateway:\n  auto_start: true\n")
        actions = container_boot.reconcile_profile_gateways(
            hermes_home=tmp_path, scandir=tmp_path / "service", dry_run=True,
        )
        assert self._default_action(actions).action == "started"

    def test_named_profile_honors_auto_start(self, tmp_path):
        prof = tmp_path / "profiles" / "work"
        prof.mkdir(parents=True)
        (prof / "SOUL.md").write_text("soul\n")
        (prof / "config.yaml").write_text("gateway:\n  auto_start: true\n")
        actions = container_boot.reconcile_profile_gateways(
            hermes_home=tmp_path, scandir=tmp_path / "service", dry_run=True,
        )
        work = next(a for a in actions if a.profile == "work")
        assert work.action == "started"

    def test_startup_failed_stays_down_even_with_auto_start(self, tmp_path):
        (tmp_path / "config.yaml").write_text("gateway:\n  auto_start: true\n")
        (tmp_path / "gateway_state.json").write_text(
            json.dumps({"gateway_state": "startup_failed"})
        )
        actions = container_boot.reconcile_profile_gateways(
            hermes_home=tmp_path, scandir=tmp_path / "service", dry_run=True,
        )
        # Crash-loop guard wins over the opt-in flag.
        assert self._default_action(actions).action == "registered"
