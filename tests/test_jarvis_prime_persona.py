"""Tests for muse_cli.jarvis_prime.persona.

The persona is the seat of MUSE's identity/voice. These
tests pin:

- The mode → rules → format mapping per the spec.
- The composed prompt includes identity, mode rules, response
  format, awareness summary (when given), and owner-gate reminder.
- The six canonical mode names exist.
"""

from __future__ import annotations

import pytest

from muse_cli.jarvis_prime.awareness import AwarenessSnapshot, UserProfile
from muse_cli.jarvis_prime.modes import Mode
from muse_cli.jarvis_prime.persona import (
    DEFAULT_FORMAT,
    MOBILE_VOICE_FORMAT,
    OPERATOR_FORMAT,
    Persona,
    known_modes,
)


def test_known_modes_returns_six_canonical_names() -> None:
    modes = known_modes()
    assert set(modes) == {
        "companion", "strategy", "critic", "operator", "builder", "mobile_voice",
    }


def test_persona_build_includes_identity_and_mode_rules() -> None:
    persona = Persona()
    prompt = persona.build(Mode.OPERATOR)
    text = prompt.render()
    assert "MUSE" in text
    assert "loyal to" in text.lower()
    assert "Mode: Operator" in text
    assert prompt.mode_name == "operator"


@pytest.mark.parametrize(
    "mode,expected_format",
    [
        (Mode.COMPANION, DEFAULT_FORMAT),
        (Mode.STRATEGY, DEFAULT_FORMAT),
        (Mode.CRITIC, DEFAULT_FORMAT),
        (Mode.OPERATOR, OPERATOR_FORMAT),
        (Mode.BUILDER, OPERATOR_FORMAT),
        (Mode.MOBILE_VOICE, MOBILE_VOICE_FORMAT),
    ],
)
def test_persona_picks_correct_format_per_mode(mode: Mode, expected_format: str) -> None:
    persona = Persona()
    prompt = persona.build(mode)
    assert prompt.response_format == expected_format


def test_persona_includes_owner_gate_reminder() -> None:
    persona = Persona()
    prompt = persona.build(Mode.BUILDER)
    text = prompt.render()
    assert "Yes, with authorization." in text


def test_persona_includes_awareness_summary_when_provided() -> None:
    persona = Persona()
    snap = AwarenessSnapshot(
        user_profile=UserProfile(name="Jeremiah", long_term_mission="ship JARVIS"),
    )
    prompt = persona.build(Mode.STRATEGY, awareness=snap)
    text = prompt.render()
    assert "AWARENESS SNAPSHOT" in text
    assert "User: Jeremiah" in text
    assert "Mission: ship JARVIS" in text


def test_persona_omits_awareness_summary_when_none() -> None:
    persona = Persona()
    prompt = persona.build(Mode.STRATEGY)
    text = prompt.render()
    assert "AWARENESS SNAPSHOT" not in text


def test_persona_rejects_unknown_mode_name() -> None:
    persona = Persona()
    with pytest.raises(ValueError):
        persona.build("not-a-real-mode")


def test_persona_accepts_string_mode_name() -> None:
    persona = Persona()
    prompt = persona.build("critic")
    assert prompt.mode_name == "critic"
    assert "I disagree" in prompt.render()


def test_handoff_format_constant_has_expected_sections() -> None:
    # The constant is exercised by render_handoff in runtime; this is
    # a smoke check that the seven canonical lines exist.
    from muse_cli.jarvis_prime.persona import HANDOFF_FORMAT

    for label in (
        "Mission:", "Route selected:", "Actions taken:", "Verification:",
        "Owner gates:", "Result:", "Next step:",
    ):
        assert label in HANDOFF_FORMAT
