"""Tests for the per-mode response-style validator.

Covers the guarantees:

- Per-mode rules: Mobile Voice brevity, Critic must object, Builder must ship a
  verification plan; non-styled modes always pass.
- The validator is pure / deterministic / offline (no model call, no network).
- Enforcement is gated: ``style_validator_enabled`` is OFF by default and ON
  only via the opt-in config key or env var — proving default behavior is
  unchanged.
"""

from __future__ import annotations

import pytest  # ty: ignore[unresolved-import]

from hermes_cli.jarvis_prime.modes import Mode
from hermes_cli.jarvis_prime.response_style import (
    DEFAULT_MOBILE_VOICE_MAX_SENTENCES,
    StyleValidationResult,
    StyleViolation,
    style_validator_enabled,
    validate_response_style,
)


# ---------------------------------------------------------------------------
# Mobile Voice — brevity
# ---------------------------------------------------------------------------

def test_mobile_voice_within_length_is_ok():
    text = "Noted. I'll capture that idea."  # 2 sentences == budget
    result = validate_response_style(Mode.MOBILE_VOICE, text)
    assert result.ok is True
    assert result.violations == ()


def test_mobile_voice_over_length_violates():
    text = (
        "First point here. Second point here. Third point here. "
        "Fourth point here."
    )  # 4 sentences > budget of 2
    result = validate_response_style(Mode.MOBILE_VOICE, text)
    assert result.ok is False
    codes = [v.code for v in result.violations]
    assert "mobile_voice_too_long" in codes
    violation = result.violations[0]
    assert violation.observed == 4
    assert violation.limit == DEFAULT_MOBILE_VOICE_MAX_SENTENCES


def test_mobile_voice_custom_budget():
    text = "One. Two. Three."  # 3 sentences
    # With a budget of 3 it is fine; with the default 2 it would violate.
    ok = validate_response_style(
        Mode.MOBILE_VOICE, text, mobile_voice_max_sentences=3
    )
    assert ok.ok is True
    bad = validate_response_style(
        Mode.MOBILE_VOICE, text, mobile_voice_max_sentences=2
    )
    assert bad.ok is False


# ---------------------------------------------------------------------------
# Critic — must name an objection
# ---------------------------------------------------------------------------

def test_critic_with_objection_is_ok():
    text = (
        "This plan is directionally right, but the rollback path is a real "
        "risk if the migration fails midway."
    )
    result = validate_response_style(Mode.CRITIC, text)
    assert result.ok is True
    assert result.violations == ()


def test_critic_without_objection_violates():
    text = "Great idea. I fully agree and think you should ship it right away."
    result = validate_response_style(Mode.CRITIC, text)
    assert result.ok is False
    assert [v.code for v in result.violations] == ["critic_no_objection"]


# ---------------------------------------------------------------------------
# Builder — must ship a verification plan
# ---------------------------------------------------------------------------

def test_builder_with_verification_plan_is_ok():
    text = (
        "I'll add the cache module and cover it with pytest unit tests, then "
        "run ruff and the type check before opening the PR."
    )
    result = validate_response_style(Mode.BUILDER, text)
    assert result.ok is True
    assert result.violations == ()


def test_builder_without_verification_plan_violates():
    text = "I'll add the cache module and wire it into the request handler."
    result = validate_response_style(Mode.BUILDER, text)
    assert result.ok is False
    assert [v.code for v in result.violations] == ["builder_no_verification"]


# ---------------------------------------------------------------------------
# Non-styled modes — always ok
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", [Mode.COMPANION, Mode.STRATEGY, Mode.OPERATOR])
def test_non_styled_modes_always_ok(mode):
    # Long, opinion-free, verification-free text is still ok for these modes.
    text = "Here is a long answer. It has several sentences. None of them push back."
    result = validate_response_style(mode, text)
    assert result.ok is True
    assert result.violations == ()


def test_accepts_string_mode_values():
    # The validator coerces the string form of a Mode too.
    result = validate_response_style("mobile_voice", "One. Two. Three. Four.")
    assert result.ok is False
    assert result.violations[0].code == "mobile_voice_too_long"


def test_unknown_mode_and_empty_text_are_ok():
    assert validate_response_style("not_a_mode", "anything at all here").ok is True
    assert validate_response_style(Mode.CRITIC, "").ok is True
    assert validate_response_style(Mode.CRITIC, "   ").ok is True


def test_result_is_serializable():
    result = validate_response_style(Mode.CRITIC, "I fully agree.")
    payload = result.to_dict()
    assert payload["mode"] == "critic"
    assert payload["ok"] is False
    assert payload["violations"][0]["code"] == "critic_no_objection"
    assert isinstance(result, StyleValidationResult)
    assert isinstance(result.violations[0], StyleViolation)


# ---------------------------------------------------------------------------
# Purity — deterministic and offline (no model / network call)
# ---------------------------------------------------------------------------

def test_validator_is_deterministic():
    text = "This is fine, but there is a clear risk in the rollout."
    first = validate_response_style(Mode.CRITIC, text)
    second = validate_response_style(Mode.CRITIC, text)
    assert first.to_dict() == second.to_dict()


def test_validator_makes_no_network_or_model_call():
    """The validator must not open a socket or call a model — it is pure."""
    import socket

    def _no_network(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("response-style validator must not open a socket")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(socket.socket, "connect", _no_network, raising=False)
        result = validate_response_style(
            Mode.BUILDER, "I'll ship it and cover it with tests."
        )
    assert result.ok is True


# ---------------------------------------------------------------------------
# Enforcement gate — default OFF, opt-in ON
# ---------------------------------------------------------------------------

def test_enforcement_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MUSE_STYLE_VALIDATOR", raising=False)
    assert style_validator_enabled(None) is False
    assert style_validator_enabled({}) is False


def test_enforcement_enabled_via_config(monkeypatch):
    monkeypatch.delenv("MUSE_STYLE_VALIDATOR", raising=False)
    cfg = {"display": {"style_validator": {"enabled": True}}}
    assert style_validator_enabled(cfg) is True


def test_enforcement_enabled_via_env(monkeypatch):
    monkeypatch.setenv("MUSE_STYLE_VALIDATOR", "1")
    assert style_validator_enabled({}) is True
    monkeypatch.setenv("MUSE_STYLE_VALIDATOR", "off")
    assert style_validator_enabled({}) is False


def test_enforcement_env_overrides_config(monkeypatch):
    monkeypatch.setenv("MUSE_STYLE_VALIDATOR", "0")
    cfg = {"display": {"style_validator": {"enabled": True}}}
    assert style_validator_enabled(cfg) is False


def test_enforcement_ignores_malformed_config(monkeypatch):
    monkeypatch.delenv("MUSE_STYLE_VALIDATOR", raising=False)
    assert style_validator_enabled({"display": {"style_validator": "on"}}) is False
