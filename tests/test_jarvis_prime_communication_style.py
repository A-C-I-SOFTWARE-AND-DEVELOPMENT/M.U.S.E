"""Tests for hermes_cli.jarvis_prime.communication_style — pacing + turn-taking."""

from __future__ import annotations

from hermes_cli.jarvis_prime.communication_style import (
    Cadence,
    PacingContext,
    SpeakingPosture,
    TurnTakingPolicy,
    decide_pacing,
    is_backchannel,
    is_topic_shift,
    needs_interrupt,
)


def test_backchannel_recognized() -> None:
    assert is_backchannel("uh huh") is True
    assert is_backchannel("yeah") is True
    assert is_backchannel("Right") is True
    assert is_backchannel("go on") is True


def test_backchannel_long_text_is_not_backchannel() -> None:
    assert is_backchannel("yeah but I think we need to dig into this more deeply") is False


def test_topic_shift_recognized() -> None:
    assert is_topic_shift("anyway, what's the plan for tomorrow") is True
    assert is_topic_shift("btw, what about the migration") is True


def test_topic_shift_negative() -> None:
    assert is_topic_shift("let's continue with the plan") is False


def test_needs_interrupt_safety_trigger() -> None:
    assert needs_interrupt("here's my api key sk-abc") is True  # api key is in safety triggers
    assert needs_interrupt("password is hunter2") is True
    assert needs_interrupt("let's force push to main") is True
    assert needs_interrupt("just checking in") is False


def test_decide_pacing_safety_interrupts() -> None:
    decision = decide_pacing("rm -rf the production database")
    assert decision.posture == SpeakingPosture.INTERRUPT
    assert decision.cadence == Cadence.BRIEF


def test_decide_pacing_backchannel_acknowledges() -> None:
    decision = decide_pacing("mhm")
    assert decision.posture == SpeakingPosture.BACKCHANNEL
    assert decision.max_sentences == 1


def test_decide_pacing_voice_is_brief() -> None:
    decision = decide_pacing(
        "give me the full repo audit", PacingContext(surface="voice", user_appears_moving=True)
    )
    assert decision.cadence == Cadence.BRIEF


def test_decide_pacing_topic_shift_normal_cadence() -> None:
    decision = decide_pacing("anyway, switching gears - what about the pricing model")
    assert decision.posture == SpeakingPosture.SPEAK
    assert decision.cadence == Cadence.NORMAL


def test_decide_pacing_short_user_after_long_response_is_brief() -> None:
    decision = decide_pacing("ok", PacingContext(prior_response_length=600))
    assert decision.cadence == Cadence.BRIEF


def test_decide_pacing_long_question_goes_deep() -> None:
    long_q = (
        "Can you walk me through the full reasoning for choosing muse "
        "as the apex persona over a different naming convention, "
        "including the tradeoffs and how it interacts with the AOS council?"
    )
    decision = decide_pacing(long_q)
    assert decision.cadence == Cadence.DEEP
    assert decision.posture == SpeakingPosture.SPEAK


def test_decide_pacing_default_normal() -> None:
    decision = decide_pacing("show me what's next")
    assert decision.cadence == Cadence.NORMAL


def test_turn_taking_policy_evaluates() -> None:
    policy = TurnTakingPolicy()
    decision = policy.evaluate("mhm")
    assert decision.posture == SpeakingPosture.BACKCHANNEL
