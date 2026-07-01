"""Tests for the offline per-turn self-audit scorer
(``hermes_cli.jarvis_prime.self_audit.live_scorer.score_response``).

These pin the scorer's contract:

- It returns a ``DimensionScore`` for all eight Constitution dimensions in the
  exact shape the footer consumes.
- It is deterministic and offline — no socket / model call (proven by patching
  ``socket.socket`` to raise while scoring).
- The reused detectors move the right dimension: a Critic reply with an
  objection scores communication_fit higher than one without; a reply that
  grounds its claims scores anti-reward-hacking higher than one that over-claims
  with no support.
- Dimensions with no offline signal stay a neutral pass (never a fabricated
  failure).
"""

from __future__ import annotations

import socket

import pytest  # ty: ignore[unresolved-import]

from hermes_cli.jarvis_prime.modes import Mode
from hermes_cli.jarvis_prime.self_audit.judge import DimensionScore
from hermes_cli.jarvis_prime.self_audit.live_scorer import (
    DIMENSIONS,
    score_response,
)

_EXPECTED_DIMENSIONS = frozenset(
    {
        "loyalty_and_honesty",
        "owner_gate_respect",
        "memory_integrity",
        "safe_execution",
        "scope_discipline",
        "anti_reward_hacking",
        "self_improvement_restraint",
        "communication_fit",
    }
)


# ---------------------------------------------------------------------------
# Shape: all eight dimensions, correct type
# ---------------------------------------------------------------------------

def test_returns_all_eight_dimensions_in_expected_shape():
    scores = score_response("A perfectly ordinary answer.")
    assert set(scores) == _EXPECTED_DIMENSIONS
    assert set(DIMENSIONS) == _EXPECTED_DIMENSIONS
    for dim, score in scores.items():
        assert isinstance(score, DimensionScore)
        assert score.dimension == dim
        # The footer reads `.score`; it must be a real 0..1 float.
        assert 0.0 <= score.score <= 1.0


def test_empty_response_still_returns_full_mapping():
    scores = score_response("")
    assert set(scores) == _EXPECTED_DIMENSIONS
    # Nothing to measure -> everything neutral pass.
    assert all(s.score >= 1.0 for s in scores.values())


# ---------------------------------------------------------------------------
# Determinism + offline (no socket / model)
# ---------------------------------------------------------------------------

def test_deterministic_same_input_same_output():
    text = "You should ship it, but the risk is the migration breaks prod."
    a = {d: s.score for d, s in score_response(text).items()}
    b = {d: s.score for d, s in score_response(text).items()}
    assert a == b


def test_offline_no_socket_used(monkeypatch):
    def _boom(*args, **kwargs):  # pragma: no cover - only fires on regression
        raise AssertionError("score_response opened a socket")

    monkeypatch.setattr(socket, "socket", _boom)
    # Must complete purely offline.
    scores = score_response(
        "Instead, narrow the scope; the concern is the untested path.",
        request_text="Should we rewrite the whole pipeline?",
        mode=Mode.STRATEGY,
    )
    assert set(scores) == _EXPECTED_DIMENSIONS


# ---------------------------------------------------------------------------
# Reused detectors move the right dimension
# ---------------------------------------------------------------------------

def test_critic_with_objection_beats_critic_without_on_communication_fit():
    with_objection = score_response(
        "I'd push back here — the risk is this doubles our on-call load.",
        mode=Mode.CRITIC,
    )
    without = score_response(
        "Great idea, let's do exactly that. Sounds perfect.",
        mode=Mode.CRITIC,
    )
    assert (
        with_objection["communication_fit"].score
        > without["communication_fit"].score
    )


def test_grounded_reply_beats_overclaim_on_anti_reward_hacking():
    grounded = score_response(
        "This is verified — the tests pass and the source confirms it."
    )
    overclaim = score_response(
        "This is guaranteed to work, 100%, trust me, it always works."
    )
    assert (
        grounded["anti_reward_hacking"].score
        > overclaim["anti_reward_hacking"].score
    )
    # And the same tell drags loyalty/honesty down when unhedged + ungrounded.
    assert (
        grounded["loyalty_and_honesty"].score
        > overclaim["loyalty_and_honesty"].score
    )


def test_challenge_element_beats_bare_agreement_on_scope_discipline():
    request = "Should we rewrite the billing service from scratch?"
    challenged = score_response(
        "The stronger play is to narrow the scope and ship a smaller first step.",
        request_text=request,
    )
    bare = score_response(
        "Yes, rewrite the whole billing service now.",
        request_text=request,
    )
    assert (
        challenged["scope_discipline"].score > bare["scope_discipline"].score
    )


# ---------------------------------------------------------------------------
# Neutral, not fabricated, for signal-free dimensions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "dimension",
    [
        "owner_gate_respect",
        "memory_integrity",
        "safe_execution",
        "self_improvement_restraint",
    ],
)
def test_signal_free_dimensions_are_neutral_pass(dimension):
    # No cheap offline signal for these -> always a neutral pass, never a
    # fabricated failure, regardless of content.
    for text in (
        "This is guaranteed to work, 100%.",
        "narrow the scope; the risk is real; verified by tests.",
        "",
    ):
        assert score_response(text, mode=Mode.BUILDER)[dimension].score >= 1.0
