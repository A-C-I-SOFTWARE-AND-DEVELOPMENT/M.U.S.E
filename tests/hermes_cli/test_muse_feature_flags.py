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

    def test_style_enforcement_registered_default_false(self):
        assert (
            DEFAULT_CONFIG["response"]["style_enforcement"]["enabled"] is False
        )

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
        for var in (
            "MUSE_SELF_AUDIT_FOOTER",
            "MUSE_TOOL_BROKER",
            "MUSE_STYLE_ENFORCEMENT",
            "MUSE_EFFORT_CAP",
        ):
            os.environ.pop(var, None)

    def test_enumerates_all_flags(self):
        with patch.dict(os.environ, {}, clear=False):
            self._clear_env()
            flags = muse_feature_flags()
        features = {f["feature"] for f in flags}
        assert features == {
            "self_audit_footer",
            "tool_broker",
            "style_enforcement",
            "effort_cap",
        }
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

    def test_config_enables_style_enforcement(self):
        cfg = {"response": {"style_enforcement": {"enabled": True}}}
        with patch.dict(os.environ, {}, clear=False):
            self._clear_env()
            flags = {f["feature"]: f for f in muse_feature_flags(cfg)}
        assert flags["style_enforcement"]["enabled"] is True
        assert flags["style_enforcement"]["config_key"] == (
            "response.style_enforcement.enabled"
        )
        # Untouched flags stay off.
        assert flags["tool_broker"]["enabled"] is False

    def test_style_enforcement_env_wins_over_config(self):
        cfg = {"response": {"style_enforcement": {"enabled": False}}}
        with patch.dict(
            os.environ, {"MUSE_STYLE_ENFORCEMENT": "1"}, clear=False
        ):
            os.environ.pop("MUSE_SELF_AUDIT_FOOTER", None)
            os.environ.pop("MUSE_TOOL_BROKER", None)
            os.environ.pop("MUSE_EFFORT_CAP", None)
            flags = {f["feature"]: f for f in muse_feature_flags(cfg)}
        assert flags["style_enforcement"]["enabled"] is True

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


class TestEmptyEnvDefersToConfig:
    """A present-but-empty MUSE_* env means "not specified" — defer to config.

    Regression for P1-11: an exported-but-empty env var (``MUSE_...=``) used to
    be parsed as an explicit False, silently forcing a config-enabled feature
    OFF. Only a NON-empty value may override config, in either direction.
    """

    _FOOTER_ON = {"display": {"self_audit_footer": {"enabled": True}}}
    _FOOTER_OFF = {"display": {"self_audit_footer": {"enabled": False}}}
    _BROKER_ON = {"security": {"tool_broker": {"enabled": True}}}
    _BROKER_OFF = {"security": {"tool_broker": {"enabled": False}}}

    # -- self-audit footer -------------------------------------------------

    def test_footer_empty_env_defers_to_config_true(self, monkeypatch):
        monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "")
        assert self_audit_footer_enabled(self._FOOTER_ON) is True

    def test_footer_empty_env_defers_to_config_false(self, monkeypatch):
        monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "")
        assert self_audit_footer_enabled(self._FOOTER_OFF) is False

    def test_footer_nonempty_true_env_overrides_config_false(self, monkeypatch):
        monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")
        assert self_audit_footer_enabled(self._FOOTER_OFF) is True

    def test_footer_nonempty_false_env_overrides_config_true(self, monkeypatch):
        monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "0")
        assert self_audit_footer_enabled(self._FOOTER_ON) is False

    def test_footer_whitespace_only_env_defers_to_config(self, monkeypatch):
        monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "   ")
        assert self_audit_footer_enabled(self._FOOTER_ON) is True
        assert self_audit_footer_enabled(self._FOOTER_OFF) is False

    # -- tool broker -------------------------------------------------------

    def test_broker_empty_env_defers_to_config_true(self, monkeypatch):
        monkeypatch.setenv("MUSE_TOOL_BROKER", "")
        assert tool_broker_enabled(self._BROKER_ON) is True

    def test_broker_empty_env_defers_to_config_false(self, monkeypatch):
        monkeypatch.setenv("MUSE_TOOL_BROKER", "")
        assert tool_broker_enabled(self._BROKER_OFF) is False

    def test_broker_nonempty_true_env_overrides_config_false(self, monkeypatch):
        monkeypatch.setenv("MUSE_TOOL_BROKER", "1")
        assert tool_broker_enabled(self._BROKER_OFF) is True

    def test_broker_nonempty_false_env_overrides_config_true(self, monkeypatch):
        monkeypatch.setenv("MUSE_TOOL_BROKER", "0")
        assert tool_broker_enabled(self._BROKER_ON) is False

    def test_broker_whitespace_only_env_defers_to_config(self, monkeypatch):
        monkeypatch.setenv("MUSE_TOOL_BROKER", "   ")
        assert tool_broker_enabled(self._BROKER_ON) is True
        assert tool_broker_enabled(self._BROKER_OFF) is False

    # -- muse_feature_flags() rollup (config-backed footer + tool broker) ---

    def test_flags_rollup_empty_env_defers_to_config(self, monkeypatch):
        monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "")
        monkeypatch.setenv("MUSE_TOOL_BROKER", "")
        monkeypatch.delenv("MUSE_EFFORT_CAP", raising=False)
        cfg = {
            "display": {"self_audit_footer": {"enabled": True}},
            "security": {"tool_broker": {"enabled": True}},
        }
        flags = {f["feature"]: f for f in muse_feature_flags(cfg)}
        assert flags["self_audit_footer"]["enabled"] is True
        assert flags["tool_broker"]["enabled"] is True

    def test_flags_rollup_nonempty_env_overrides_config(self, monkeypatch):
        monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "0")
        monkeypatch.setenv("MUSE_TOOL_BROKER", "1")
        monkeypatch.delenv("MUSE_EFFORT_CAP", raising=False)
        cfg = {
            "display": {"self_audit_footer": {"enabled": True}},
            "security": {"tool_broker": {"enabled": False}},
        }
        flags = {f["feature"]: f for f in muse_feature_flags(cfg)}
        assert flags["self_audit_footer"]["enabled"] is False
        assert flags["tool_broker"]["enabled"] is True
