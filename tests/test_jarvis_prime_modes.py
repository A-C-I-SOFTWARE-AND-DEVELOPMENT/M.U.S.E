"""Tests for muse_cli.jarvis_prime.modes — classifier + Mode enum."""

from __future__ import annotations

import pytest

from muse_cli.jarvis_prime.modes import (
    ClassifierContext,
    Mode,
    ModeClassifier,
    mode_from_slash_command,
)


@pytest.fixture
def classifier() -> ModeClassifier:
    return ModeClassifier()


def test_mode_enum_has_six_values() -> None:
    assert {m.value for m in Mode} == {
        "companion", "strategy", "critic", "operator",
        "builder", "mobile_voice",
    }


def test_builder_keywords_route_to_builder(classifier: ModeClassifier) -> None:
    result = classifier.classify("Refactor the model router and add a pytest test")
    assert result.mode == Mode.BUILDER
    assert result.confidence > 0.6


def test_voice_input_routes_to_mobile_voice(classifier: ModeClassifier) -> None:
    result = classifier.classify(
        "quick idea about pricing",
        ClassifierContext(is_voice_input=True),
    )
    assert result.mode == Mode.MOBILE_VOICE
    assert "voice input" in result.reason or "jogging" in result.reason


def test_strategy_keyword_routes_to_strategy(classifier: ModeClassifier) -> None:
    result = classifier.classify(
        "What's the strategic tradeoff between launching now and waiting for v2 positioning?"
    )
    assert result.mode == Mode.STRATEGY


def test_critic_keyword_routes_to_critic(classifier: ModeClassifier) -> None:
    result = classifier.classify("Tear apart this product proposal, find the blind spots.")
    assert result.mode == Mode.CRITIC


def test_companion_keyword_routes_to_companion(classifier: ModeClassifier) -> None:
    result = classifier.classify("I'm tired and feeling stressed about the launch.")
    assert result.mode == Mode.COMPANION


def test_operator_audit_keyword_routes_to_operator(classifier: ModeClassifier) -> None:
    result = classifier.classify("Audit the repo for blockers and merge conflicts.")
    assert result.mode == Mode.OPERATOR


def test_explicit_override_wins(classifier: ModeClassifier) -> None:
    context = ClassifierContext(explicit_mode=Mode.CRITIC)
    result = classifier.classify("I'm tired", context=context)
    assert result.mode == Mode.CRITIC
    assert result.confidence == 1.0


def test_empty_intent_defaults_to_operator(classifier: ModeClassifier) -> None:
    result = classifier.classify("")
    assert result.mode == Mode.OPERATOR
    assert result.confidence == 0.3


def test_no_keywords_falls_back_to_companion(classifier: ModeClassifier) -> None:
    result = classifier.classify("hello there friend")
    assert result.mode == Mode.COMPANION


def test_repo_root_upweights_builder(classifier: ModeClassifier) -> None:
    # An ambiguous intent with repo_root set → builder.
    result = classifier.classify(
        "review the changes",
        ClassifierContext(repo_root="/home/user/hermes-agent"),
    )
    assert result.mode == Mode.BUILDER


def test_high_risk_class_upweights_critic(classifier: ModeClassifier) -> None:
    result = classifier.classify(
        "what should we do",
        ClassifierContext(risk_class="RC4"),
    )
    # RC4 + no specific keywords → critic gets the boost via priority.
    assert result.mode in (Mode.CRITIC, Mode.OPERATOR)


def test_mobile_surface_upweights_mobile_voice(classifier: ModeClassifier) -> None:
    result = classifier.classify(
        "quick idea",
        ClassifierContext(surface="telegram", is_voice_input=False),
    )
    assert result.mode == Mode.MOBILE_VOICE


@pytest.mark.parametrize(
    "command,expected",
    [
        ("/companion", Mode.COMPANION),
        ("/strategy", Mode.STRATEGY),
        ("/critic", Mode.CRITIC),
        ("/operator", Mode.OPERATOR),
        ("/builder", Mode.BUILDER),
        ("/voice", Mode.MOBILE_VOICE),
        ("/mobile-voice", Mode.MOBILE_VOICE),
        ("/mobile_voice", Mode.MOBILE_VOICE),
    ],
)
def test_slash_command_mapping_known_modes(command: str, expected: Mode) -> None:
    assert mode_from_slash_command(command) == expected


@pytest.mark.parametrize("command", ["/jarvis", "/jarvis-prime", "/jp"])
def test_slash_command_apex_returns_none_for_auto_classify(command: str) -> None:
    assert mode_from_slash_command(command) is None


def test_slash_command_unknown_returns_none() -> None:
    assert mode_from_slash_command("/not-a-mode") is None
