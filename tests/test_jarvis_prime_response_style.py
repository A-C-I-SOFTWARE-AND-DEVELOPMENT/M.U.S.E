"""Tests for the per-mode response-style validator.

Covers the guarantees:

- Per-mode rules: Mobile Voice brevity, Critic must object, Builder must ship a
  verification plan; non-styled modes always pass.
- The validator is pure / deterministic / offline (no model call, no network).
- The validator is always-inspection: there is no ``style_validator_enabled``
  gate. Its only consumer (the self-audit footer scorer) calls it whenever the
  footer itself is enabled, so the validator never alters default behavior.
"""

from __future__ import annotations

import re

import pytest  # ty: ignore[unresolved-import]

from hermes_cli.jarvis_prime import response_style as _rs_mod
from hermes_cli.jarvis_prime.modes import Mode
from hermes_cli.jarvis_prime.response_style import (
    DEFAULT_MOBILE_VOICE_MAX_SENTENCES,
    StyleValidationResult,
    StyleViolation,
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
# F3 — Mobile Voice length backstop (word count / line count) is not evadable
# ---------------------------------------------------------------------------

def test_mobile_voice_unpunctuated_runon_flagged_by_word_backstop():
    # ~60-word run-on with a single terminal period reads as ONE sentence, so
    # the sentence rule alone misses it; the word backstop must flag it.
    text = (
        "so basically what I would do here is take the whole plan and just "
        "run with it end to end without stopping to check anything because "
        "it all seems fine and the team is happy and the roadmap looks clean "
        "and honestly there is nothing to worry about at all in my view here."
    )
    assert len(text.split()) > 40
    assert len(re.findall(r"[.!?]+", text)) == 1  # a single terminal sentence
    result = validate_response_style(Mode.MOBILE_VOICE, text)
    assert result.ok is False
    assert result.violations[0].code == "mobile_voice_too_long"


def test_mobile_voice_bullet_list_flagged_by_line_backstop():
    # A 6-bullet list with no terminal punctuation reads as one "sentence"; the
    # newline/line backstop must flag it (6 lines > 2-sentence budget).
    text = "\n".join(
        [
            "- first item",
            "- second item",
            "- third item",
            "- fourth item",
            "- fifth item",
            "- sixth item",
        ]
    )
    result = validate_response_style(Mode.MOBILE_VOICE, text)
    assert result.ok is False
    assert result.violations[0].code == "mobile_voice_too_long"


def test_mobile_voice_genuinely_brief_reply_is_ok():
    # A real 2-sentence, short reply must still pass (precision guard — the
    # backstop must not over-flag brief replies).
    text = "Noted. I'll capture that."
    result = validate_response_style(Mode.MOBILE_VOICE, text)
    assert result.ok is True
    assert result.violations == ()


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


def test_critic_objection_markers_require_word_boundary():
    # "specificity" contains no whole objection word (guards against "ci"-style
    # substrings) and "contribute" embeds "but" — neither is a real objection,
    # so a Critic reply built only from them must still violate.
    text = (
        "I love the specificity here and how much this will contribute to "
        "the roadmap. Great work all around."
    )
    result = validate_response_style(Mode.CRITIC, text)
    assert result.ok is False
    assert [v.code for v in result.violations] == ["critic_no_objection"]


def test_critic_real_objection_words_still_trigger():
    # Real objection words present as whole words must still count.
    for text in (
        "I agree in part, but the timeline is aggressive.",
        "There is a real risk of data loss on rollback.",
        "This is solid; however, the auth path is untested.",
    ):
        result = validate_response_style(Mode.CRITIC, text)
        assert result.ok is True, text
        assert result.violations == ()


def test_critic_curly_apostrophe_objection_detected():
    # A curly apostrophe in "won't work" must still count as an objection (F4).
    text = "That won’t work — the rollback path breaks midway."
    result = validate_response_style(Mode.CRITIC, text)
    assert result.ok is True
    assert result.violations == ()


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


def test_builder_verification_markers_require_word_boundary():
    # "protestation" embeds "test" and "specificity" embeds "ci"; neither is a
    # real verification word, so a Builder reply built only from them must still
    # violate.
    text = (
        "I'll wire it in without protestation and add specificity to the "
        "config so the handler reads cleanly."
    )
    result = validate_response_style(Mode.BUILDER, text)
    assert result.ok is False
    assert [v.code for v in result.violations] == ["builder_no_verification"]


def test_builder_real_verification_words_still_trigger():
    # Real verification words present as whole words must still count.
    for text in (
        "I'll cover it with a unit test before merging.",
        "I'll verify the output against the fixture.",
        "Green CI is the gate before this ships.",
    ):
        result = validate_response_style(Mode.BUILDER, text)
        assert result.ok is True, text
        assert result.violations == ()


def test_builder_curly_apostrophe_verification_detected():
    # A curly apostrophe in "how it'll be checked" must still count (F4).
    text = "I’ll wire it in, then describe how it’ll be checked before merging."
    result = validate_response_style(Mode.BUILDER, text)
    assert result.ok is True
    assert result.violations == ()


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
# Always-inspection — no enforcement gate exists (dead-gate removed, B6 #20)
# ---------------------------------------------------------------------------

def test_no_enforcement_gate_helper():
    # The dead ``style_validator_enabled`` helper gated nothing (zero runtime
    # consumers) and was removed so the validator is documented as always-
    # inspection. Guard against it being reintroduced.
    assert not hasattr(_rs_mod, "style_validator_enabled")
    assert "style_validator_enabled" not in _rs_mod.__all__
