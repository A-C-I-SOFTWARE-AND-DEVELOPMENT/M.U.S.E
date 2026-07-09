"""Tests for the opt-in response-style enforcement gate + composed evaluator.

Covers (P2-7):

- ``style_enforcement_enabled`` resolves False by default (None / {} /
  DEFAULT_CONFIG, env unset), True when config enables it, and the env var wins
  over config in both directions — with a present-but-empty env deferring to
  config (P1-11 parity, mirroring ``tool_broker_enabled``).
- ``evaluate_enforcement`` composes the EXISTING style + challenge detectors:
  a Critic reply with no objection is not ok; a non-trivial request answered
  with pure agreement is a challenge violation; a clean reply is ok; empty text
  is ok (nothing to enforce); an unknown mode skips the style check.
- ``resolve_max_attempts`` clamps into [1, 2].
"""

from __future__ import annotations

import os
from unittest.mock import patch

from hermes_cli.config import DEFAULT_CONFIG
from hermes_cli.jarvis_prime.modes import Mode
from hermes_cli.jarvis_prime.response_enforcement import (
    DEFAULT_MAX_ATTEMPTS,
    MAX_ATTEMPTS_CEILING,
    EnforcementCheck,
    _corrective_nudge,
    evaluate_enforcement,
    resolve_max_attempts,
    style_enforcement_enabled,
)

_ENABLED = {"response": {"style_enforcement": {"enabled": True}}}
_DISABLED = {"response": {"style_enforcement": {"enabled": False}}}


def _clear_env():
    os.environ.pop("MUSE_STYLE_ENFORCEMENT", None)


class TestGateResolution:
    def test_off_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            _clear_env()
            assert style_enforcement_enabled(None) is False
            assert style_enforcement_enabled({}) is False
            assert style_enforcement_enabled(DEFAULT_CONFIG) is False

    def test_config_enables(self):
        with patch.dict(os.environ, {}, clear=False):
            _clear_env()
            assert style_enforcement_enabled(_ENABLED) is True
            assert style_enforcement_enabled(_DISABLED) is False

    def test_env_true_overrides_config_false(self, monkeypatch):
        monkeypatch.setenv("MUSE_STYLE_ENFORCEMENT", "1")
        assert style_enforcement_enabled(_DISABLED) is True

    def test_env_false_overrides_config_true(self, monkeypatch):
        monkeypatch.setenv("MUSE_STYLE_ENFORCEMENT", "0")
        assert style_enforcement_enabled(_ENABLED) is False

    def test_empty_env_defers_to_config_true(self, monkeypatch):
        monkeypatch.setenv("MUSE_STYLE_ENFORCEMENT", "")
        assert style_enforcement_enabled(_ENABLED) is True

    def test_empty_env_defers_to_config_false(self, monkeypatch):
        monkeypatch.setenv("MUSE_STYLE_ENFORCEMENT", "")
        assert style_enforcement_enabled(_DISABLED) is False

    def test_whitespace_env_defers_to_config(self, monkeypatch):
        monkeypatch.setenv("MUSE_STYLE_ENFORCEMENT", "   ")
        assert style_enforcement_enabled(_ENABLED) is True
        assert style_enforcement_enabled(_DISABLED) is False

    def test_default_config_key_present_and_false(self):
        assert (
            DEFAULT_CONFIG["response"]["style_enforcement"]["enabled"] is False
        )


class TestResolveMaxAttempts:
    def test_default_when_absent(self):
        assert resolve_max_attempts(None) == DEFAULT_MAX_ATTEMPTS
        assert resolve_max_attempts({}) == DEFAULT_MAX_ATTEMPTS
        assert resolve_max_attempts(_ENABLED) == DEFAULT_MAX_ATTEMPTS

    def test_clamped_to_ceiling(self):
        cfg = {"response": {"style_enforcement": {"max_attempts": 5}}}
        assert resolve_max_attempts(cfg) == MAX_ATTEMPTS_CEILING

    def test_floor_of_one(self):
        cfg = {"response": {"style_enforcement": {"max_attempts": 0}}}
        assert resolve_max_attempts(cfg) == DEFAULT_MAX_ATTEMPTS

    def test_malformed_falls_back(self):
        cfg = {"response": {"style_enforcement": {"max_attempts": "banana"}}}
        assert resolve_max_attempts(cfg) == DEFAULT_MAX_ATTEMPTS

    def test_exact_two(self):
        cfg = {"response": {"style_enforcement": {"max_attempts": 2}}}
        assert resolve_max_attempts(cfg) == 2


class TestEvaluateEnforcement:
    def test_empty_text_is_ok(self):
        check = evaluate_enforcement(Mode.CRITIC, "", request_text="should we ship?")
        assert check.ok is True
        assert check.style_violations == ()
        assert check.challenge_violation is None

    def test_critic_no_objection_not_ok(self):
        # A Critic reply that carries no objection marker violates the style
        # contract. Use a request without a non-trivial marker so the challenge
        # contract does not also fire (isolates the style violation).
        check = evaluate_enforcement(
            Mode.CRITIC,
            "That is a wonderful idea and I love everything about it.",
            request_text="",
        )
        assert check.ok is False
        codes = {v.code for v in check.style_violations}
        assert "critic_no_objection" in codes

    def test_non_trivial_pure_agreement_is_challenge_violation(self):
        # A non-trivial request answered with pure agreement (no challenge
        # element) fails the challenge contract. Companion mode has no style
        # rule, so the failure is purely the challenge contract.
        check = evaluate_enforcement(
            Mode.COMPANION,
            "Ship it, looks perfect, no notes.",
            request_text="Should we build and launch the new pricing strategy?",
        )
        assert check.ok is False
        assert check.challenge_violation is not None
        assert check.challenge_violation.satisfied is False

    def test_clean_reply_is_ok(self):
        # Critic reply that names a risk AND a request that draws a challenge.
        check = evaluate_enforcement(
            Mode.CRITIC,
            "The risk is that this breaks under load; here is the concern.",
            request_text="Should we ship the migration?",
        )
        assert check.ok is True

    def test_unknown_mode_skips_style(self):
        # Unknown/None mode -> no style check. A challenge violation can still
        # fire off the request+reply, but a reply that itself carries a
        # challenge element (named risk) is ok even with no mode.
        check = evaluate_enforcement(
            None,
            "The risk is significant here; consider a counterproposal instead.",
            request_text="Should we build this?",
        )
        assert check.style_violations == ()
        assert check.ok is True

    def test_unknown_mode_no_request_is_ok(self):
        check = evaluate_enforcement(None, "anything at all", request_text="")
        assert check.ok is True

    def test_never_raises_on_odd_input(self):
        # Odd mode object and weird text must not raise.
        check = evaluate_enforcement(12345, "text", request_text="plan this build")
        assert isinstance(check, EnforcementCheck)


class TestCorrectiveNudge:
    def test_ok_check_returns_empty(self):
        assert _corrective_nudge(EnforcementCheck(ok=True)) == ""

    def test_challenge_nudge_names_contract(self):
        check = evaluate_enforcement(
            Mode.COMPANION,
            "Ship it, looks perfect.",
            request_text="Should we build and launch the pricing strategy?",
        )
        nudge = _corrective_nudge(check)
        assert nudge
        assert "risk" in nudge.lower()

    def test_style_nudge_names_contract(self):
        check = evaluate_enforcement(
            Mode.CRITIC,
            "Great idea, love it.",
            request_text="",
        )
        nudge = _corrective_nudge(check)
        assert "objection" in nudge.lower() or "pushback" in nudge.lower()
