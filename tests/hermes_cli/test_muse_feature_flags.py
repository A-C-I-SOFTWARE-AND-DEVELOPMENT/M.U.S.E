"""Tests for the MUSE opt-in feature-flag registry (audit batch B6).

Covers the control-surface coherence guarantees:

- The opt-in gate keys that actually gate something are registered in
  ``DEFAULT_CONFIG`` with default ``False`` (self-audit footer + tool broker).
- Keys for the deleted dead gates (challenge-contract / style-validator) are
  NOT registered — a config key exists only when it truly gates something.
- Each real gate resolves to ``False`` with empty/absent config (default
  runtime behavior unchanged), and the discoverability helper
  ``muse_feature_flags`` enumerates every flag with its resolved on/off state.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from hermes_cli.config import DEFAULT_CONFIG, muse_feature_flags
from hermes_cli.jarvis_prime.self_audit.footer import self_audit_footer_enabled
from hermes_cli.jarvis_prime.tool_broker import tool_broker_enabled


class TestDefaultConfigRegistration:
    def test_self_audit_footer_registered_default_false(self):
        assert (
            DEFAULT_CONFIG["display"]["self_audit_footer"]["enabled"] is False
        )

    def test_tool_broker_registered_default_false(self):
        assert DEFAULT_CONFIG["security"]["tool_broker"]["enabled"] is False

    def test_dead_gate_keys_not_registered(self):
        # #20 Option B: the challenge-contract / style-validator "gates" were
        # dead (zero runtime consumers) and were removed. We must NOT register a
        # config key for a gate that no longer exists.
        assert "challenge_contract" not in DEFAULT_CONFIG["display"]
        assert "style_validator" not in DEFAULT_CONFIG["display"]


class TestGateResolutionDefaultsOff:
    def test_self_audit_footer_off_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MUSE_SELF_AUDIT_FOOTER", None)
            assert self_audit_footer_enabled(None) is False
            assert self_audit_footer_enabled({}) is False
            assert self_audit_footer_enabled(DEFAULT_CONFIG) is False

    def test_tool_broker_off_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MUSE_TOOL_BROKER", None)
            assert tool_broker_enabled(None) is False
            assert tool_broker_enabled({}) is False
            assert tool_broker_enabled(DEFAULT_CONFIG) is False


class TestMuseFeatureFlagsHelper:
    def _clear_env(self):
        for var in ("MUSE_SELF_AUDIT_FOOTER", "MUSE_TOOL_BROKER", "MUSE_EFFORT_CAP"):
            os.environ.pop(var, None)

    def test_enumerates_all_flags(self):
        with patch.dict(os.environ, {}, clear=False):
            self._clear_env()
            flags = muse_feature_flags()
        features = {f["feature"] for f in flags}
        assert features == {"self_audit_footer", "tool_broker", "effort_cap"}
        for flag in flags:
            assert set(flag) >= {
                "feature",
                "config_key",
                "env_var",
                "default",
                "summary",
                "enabled",
            }

    def test_all_off_with_no_config_and_no_env(self):
        with patch.dict(os.environ, {}, clear=False):
            self._clear_env()
            flags = muse_feature_flags()
        assert all(f["enabled"] is False for f in flags)
        assert all(f["default"] is False for f in flags)

    def test_config_enables_footer(self):
        cfg = {"display": {"self_audit_footer": {"enabled": True}}}
        with patch.dict(os.environ, {}, clear=False):
            self._clear_env()
            flags = {f["feature"]: f for f in muse_feature_flags(cfg)}
        assert flags["self_audit_footer"]["enabled"] is True
        # Untouched flags stay off.
        assert flags["tool_broker"]["enabled"] is False

    def test_env_var_wins_over_config(self):
        cfg = {"security": {"tool_broker": {"enabled": False}}}
        with patch.dict(os.environ, {"MUSE_TOOL_BROKER": "1"}, clear=False):
            os.environ.pop("MUSE_SELF_AUDIT_FOOTER", None)
            os.environ.pop("MUSE_EFFORT_CAP", None)
            flags = {f["feature"]: f for f in muse_feature_flags(cfg)}
        assert flags["tool_broker"]["enabled"] is True

    def test_effort_cap_is_registry_gated_not_config(self):
        # The effort cap has no config.yaml key — its config_key carries the
        # registry: marker and it is never read from the passed config dict.
        cfg = {"policies": {"effort_cap": {"enabled": True}}}
        with patch.dict(os.environ, {}, clear=False):
            self._clear_env()
            flags = {f["feature"]: f for f in muse_feature_flags(cfg)}
        assert flags["effort_cap"]["config_key"].startswith("registry:")
        # A config.yaml policies block does NOT flip it (registry-only path).
        assert flags["effort_cap"]["enabled"] is False

    def test_effort_cap_env_var_flips_it(self):
        with patch.dict(os.environ, {"MUSE_EFFORT_CAP": "yes"}, clear=False):
            os.environ.pop("MUSE_SELF_AUDIT_FOOTER", None)
            os.environ.pop("MUSE_TOOL_BROKER", None)
            flags = {f["feature"]: f for f in muse_feature_flags()}
        assert flags["effort_cap"]["enabled"] is True
