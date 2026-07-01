"""Tests for the MUSE Challenge Contract detector.

Covers the guarantees:

- Each of the six challenge-element categories is detected via boundary-aware
  markers, with a false-positive guard for embedded substrings.
- A non-trivial request answered with no challenge element → contract violation;
  the same reply on a trivial request → satisfied (exempt).
- ``classify_request_triviality`` separates trivial (greeting / ack / lookup)
  from non-trivial (decision / plan / build / strategy) inputs.
- The detector is pure / deterministic / offline (no model call, no network).
- Enforcement is gated: ``challenge_contract_enabled`` is OFF by default and ON
  only via the opt-in config key or env var — proving default behavior is
  unchanged.
"""

from __future__ import annotations

import pytest  # ty: ignore[unresolved-import]

from hermes_cli.jarvis_prime.challenge_contract import (
    ChallengeContractResult,
    ChallengeElement,
    ChallengeViolation,
    RequestTriviality,
    challenge_contract_enabled,
    classify_request_triviality,
    evaluate_challenge_contract,
)


# ---------------------------------------------------------------------------
# Per-category detection — each of the six elements satisfies the contract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected_element",
    [
        (
            "Directionally right, but here is a stronger version of the plan "
            "that ships the same value with half the surface area.",
            ChallengeElement.STRONGER_VERSION,
        ),
        (
            "The real risk is that the migration fails midway with no clean "
            "rollback.",
            ChallengeElement.NAMED_RISK,
        ),
        (
            "I'd narrow the scope to just the auth path first and defer the "
            "rest.",
            ChallengeElement.SCOPE_REDUCTION,
        ),
        (
            "Rather than rewriting the whole module, an alternative is to wrap "
            "the existing one behind an adapter.",
            ChallengeElement.COUNTERPROPOSAL,
        ),
        (
            "This rests on an unverified assumption about traffic; we need "
            "data before committing.",
            ChallengeElement.EVIDENCE_GAP,
        ),
        (
            "Do not do this yet — it is premature until the pricing "
            "experiment lands.",
            ChallengeElement.DEFER,
        ),
    ],
)
def test_each_category_detected(text, expected_element):
    result = evaluate_challenge_contract(text, request_is_trivial=False)
    assert result.satisfied is True
    assert result.exempt is False
    assert expected_element.value in result.found
    assert result.violation is None


def test_multiple_categories_all_reported():
    text = (
        "The real risk is data loss on rollback, so do not do this yet; "
        "instead, narrow the scope to a read-only pass first."
    )
    result = evaluate_challenge_contract(text, request_is_trivial=False)
    assert result.satisfied is True
    assert ChallengeElement.NAMED_RISK.value in result.found
    assert ChallengeElement.DEFER.value in result.found
    assert ChallengeElement.COUNTERPROPOSAL.value in result.found
    assert ChallengeElement.SCOPE_REDUCTION.value in result.found


# ---------------------------------------------------------------------------
# Boundary-aware detection — embedded substrings must NOT false-positive
# ---------------------------------------------------------------------------

def test_markers_require_word_boundary_no_false_positive():
    # "brisk" embeds "risk", "executed" embeds "cut", "deference" embeds
    # "defer", "instead" is avoided, "assumes" is avoided by wording. None of
    # these are real challenge elements, so a non-trivial reply built only from
    # them must still fail the contract.
    text = (
        "We moved at a brisk pace and executed cleanly with great deference "
        "to the roadmap. Everything landed smoothly and the team was happy."
    )
    result = evaluate_challenge_contract(text, request_is_trivial=False)
    assert result.satisfied is False
    assert result.found == ()
    assert result.violation is not None
    assert result.violation.code == "missing_challenge"


def test_real_marker_words_still_trigger():
    # The whole-word forms of the same roots must still count.
    assert (
        evaluate_challenge_contract(
            "There is a real risk here.", request_is_trivial=False
        ).satisfied
        is True
    )
    assert (
        evaluate_challenge_contract(
            "I'd cut scope to the smallest first step.",
            request_is_trivial=False,
        ).satisfied
        is True
    )


# ---------------------------------------------------------------------------
# Missing challenge on a non-trivial request → violation
# ---------------------------------------------------------------------------

_AGREEABLE_REPLY = (
    "Great idea. I fully agree and think you should ship it right away. This "
    "is exactly the right move and I love the direction."
)


def test_non_trivial_no_challenge_violates():
    result = evaluate_challenge_contract(_AGREEABLE_REPLY, request_is_trivial=False)
    assert result.satisfied is False
    assert result.exempt is False
    assert result.found == ()
    assert result.violation is not None
    assert result.violation.code == "missing_challenge"
    # All six categories are offered as ways to satisfy it.
    assert set(result.violation.expected) == {
        e.value for e in ChallengeElement
    }


def test_same_reply_on_trivial_request_is_exempt():
    # The identical agreeable reply is auto-satisfied when the request is
    # trivial (a greeting / ack / lookup).
    result = evaluate_challenge_contract(_AGREEABLE_REPLY, request_is_trivial=True)
    assert result.satisfied is True
    assert result.exempt is True
    assert result.found == ()
    assert result.violation is None


def test_empty_reply_on_non_trivial_request_violates():
    result = evaluate_challenge_contract("", request_is_trivial=False)
    assert result.satisfied is False
    assert result.violation is not None


# ---------------------------------------------------------------------------
# Request triviality classifier
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "hi",
        "hey there",
        "thanks!",
        "ok got it",
        "what time is it?",
        "who is Ada Lovelace?",
        "define idempotent",
    ],
)
def test_trivial_requests_classified_trivial(text):
    assert classify_request_triviality(text) is RequestTriviality.TRIVIAL


@pytest.mark.parametrize(
    "text",
    [
        "Should I rewrite the billing service or patch it?",
        "Build a plan to launch the mobile app next quarter.",
        "What's the best way to price the pro tier?",
        "Help me decide our positioning against the incumbent.",
        "Design the migration strategy for the data layer.",
    ],
)
def test_non_trivial_requests_classified_non_trivial(text):
    assert classify_request_triviality(text) is RequestTriviality.NON_TRIVIAL


def test_empty_request_is_trivial():
    assert classify_request_triviality("") is RequestTriviality.TRIVIAL
    assert classify_request_triviality("   ") is RequestTriviality.TRIVIAL


def test_effort_hint_e0_downgrades_ambiguous_to_trivial():
    # A longer prompt with no decision/plan/build marker: default non-trivial,
    # but an E0 effort hint (direct answer, no council) makes it trivial.
    text = "Please tell me the capital city of that country we discussed."
    assert classify_request_triviality(text) is RequestTriviality.NON_TRIVIAL
    assert (
        classify_request_triviality(text, effort_class="E0")
        is RequestTriviality.TRIVIAL
    )


def test_effort_hint_never_overrides_explicit_non_trivial_marker():
    text = "Should I rewrite the service?"
    # Even an E0 hint does not make an explicit decision request trivial.
    assert (
        classify_request_triviality(text, effort_class="E0")
        is RequestTriviality.NON_TRIVIAL
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_result_is_serializable():
    result = evaluate_challenge_contract(_AGREEABLE_REPLY, request_is_trivial=False)
    payload = result.to_dict()
    assert payload["satisfied"] is False
    assert payload["exempt"] is False
    assert payload["found"] == []
    assert payload["violation"]["code"] == "missing_challenge"
    assert isinstance(result, ChallengeContractResult)
    assert isinstance(result.violation, ChallengeViolation)


def test_satisfied_result_serializes_found():
    result = evaluate_challenge_contract(
        "The real risk is a rollback failure.", request_is_trivial=False
    )
    payload = result.to_dict()
    assert payload["satisfied"] is True
    assert ChallengeElement.NAMED_RISK.value in payload["found"]
    assert payload["violation"] is None


# ---------------------------------------------------------------------------
# Purity — deterministic and offline (no model / network call)
# ---------------------------------------------------------------------------

def test_detector_is_deterministic():
    text = "There is a real risk here; instead, narrow the scope first."
    first = evaluate_challenge_contract(text, request_is_trivial=False)
    second = evaluate_challenge_contract(text, request_is_trivial=False)
    assert first.to_dict() == second.to_dict()


def test_classifier_is_deterministic():
    text = "Should I build the analytics pipeline now?"
    assert classify_request_triviality(text) == classify_request_triviality(text)


def test_detector_makes_no_network_or_model_call():
    """The detector must not open a socket or call a model — it is pure."""
    import socket

    def _no_network(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("challenge-contract detector must not open a socket")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(socket.socket, "connect", _no_network, raising=False)
        result = evaluate_challenge_contract(
            "The real risk is data loss.", request_is_trivial=False
        )
        classify_request_triviality("Should I ship this?")
    assert result.satisfied is True


# ---------------------------------------------------------------------------
# Enforcement gate — default OFF, opt-in ON
# ---------------------------------------------------------------------------

def test_enforcement_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MUSE_CHALLENGE_CONTRACT", raising=False)
    assert challenge_contract_enabled(None) is False
    assert challenge_contract_enabled({}) is False


def test_enforcement_enabled_via_config(monkeypatch):
    monkeypatch.delenv("MUSE_CHALLENGE_CONTRACT", raising=False)
    cfg = {"display": {"challenge_contract": {"enabled": True}}}
    assert challenge_contract_enabled(cfg) is True


def test_enforcement_enabled_via_env(monkeypatch):
    monkeypatch.setenv("MUSE_CHALLENGE_CONTRACT", "1")
    assert challenge_contract_enabled({}) is True
    monkeypatch.setenv("MUSE_CHALLENGE_CONTRACT", "off")
    assert challenge_contract_enabled({}) is False


def test_enforcement_env_overrides_config(monkeypatch):
    monkeypatch.setenv("MUSE_CHALLENGE_CONTRACT", "0")
    cfg = {"display": {"challenge_contract": {"enabled": True}}}
    assert challenge_contract_enabled(cfg) is False


def test_enforcement_ignores_malformed_config(monkeypatch):
    monkeypatch.delenv("MUSE_CHALLENGE_CONTRACT", raising=False)
    assert (
        challenge_contract_enabled({"display": {"challenge_contract": "on"}})
        is False
    )
