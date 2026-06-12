"""Tests for muse_cli.jarvis_prime.reasoning — induce + deduce."""

from __future__ import annotations

from muse_cli.jarvis_prime.reasoning import (
    Inference,
    Premise,
    Reasoner,
    ReasoningKind,
    Rule,
    deduce,
    induce,
    should_research,
)


def test_deduce_all_conditions_matched_high_confidence() -> None:
    rule = Rule(
        name="builder-requires-tests",
        conditions=("builder mode", "code change"),
        conclusion="must run tests",
        confidence=0.9,
    )
    premises = [
        Premise("we are in builder mode", confidence=1.0),
        Premise("there is a code change in parser.py", confidence=1.0),
    ]
    inference = deduce(rule, premises)
    assert inference.kind == ReasoningKind.DEDUCTIVE
    assert inference.conclusion == "must run tests"
    assert inference.confidence == 0.9
    assert not inference.requires_corroboration


def test_deduce_partial_match_holds_low_confidence() -> None:
    rule = Rule(
        name="critic-when-rc4",
        conditions=("critic mode", "risk class RC4"),
        conclusion="escalate to owner",
        confidence=0.95,
    )
    premises = [Premise("critic mode active")]
    inference = deduce(rule, premises, strict=True)
    assert inference.confidence < 0.5
    assert inference.requires_corroboration


def test_induce_below_minimum_observations_needs_corroboration() -> None:
    observations = [
        Premise("last week, the build took 5min", confidence=1.0),
    ]
    inference = induce(observations, "builds always take 5min", minimum_observations=3)
    assert inference.requires_corroboration
    assert inference.kind == ReasoningKind.INDUCTIVE


def test_induce_with_enough_observations_higher_confidence() -> None:
    observations = [
        Premise(f"observation {i}", confidence=0.95)
        for i in range(5)
    ]
    inference = induce(observations, "pattern holds")
    assert inference.confidence > 0.7
    assert not inference.requires_corroboration


def test_induce_empty_observations_zero_confidence() -> None:
    inference = induce([], "all swans are white")
    assert inference.confidence == 0.0
    assert inference.requires_corroboration


def test_should_research_true_when_low_confidence() -> None:
    inference = Inference(
        kind=ReasoningKind.DEDUCTIVE,
        conclusion="x",
        confidence=0.4,
        evidence=(),
        reasoning="weak",
    )
    assert should_research(inference) is True


def test_should_research_true_when_corroboration_needed() -> None:
    inference = Inference(
        kind=ReasoningKind.INDUCTIVE,
        conclusion="x",
        confidence=0.9,
        evidence=(),
        reasoning="needs more obs",
        requires_corroboration=True,
    )
    assert should_research(inference) is True


def test_should_research_false_when_strong() -> None:
    inference = Inference(
        kind=ReasoningKind.DEDUCTIVE,
        conclusion="x",
        confidence=0.9,
        evidence=(),
        reasoning="all conditions met",
    )
    assert should_research(inference) is False


def test_reasoner_bundles_helpers() -> None:
    r = Reasoner()
    rule = Rule(name="r", conditions=("a",), conclusion="b")
    premises = [Premise("a")]
    inf = r.deduce(rule, premises)
    assert inf.conclusion == "b"
    assert not r.should_research(inf)
