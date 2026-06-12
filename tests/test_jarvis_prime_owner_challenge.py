"""Tests for challenge-bound owner authorization.

The legacy static phrase remains for backward compatibility, but strict
guardrails require a nonce-bound challenge response: a replayed bare phrase must
not authorize, and the grant binds to a specific action + subject.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from muse_cli.jarvis_prime.owner_auth import (
    AUTHORIZATION_PHRASE,
    OwnerAuth,
    authorize_challenge,
    create_challenge,
)
from muse_cli.jarvis_prime.guardrail_evidence import ARTIFACT_OWNER_GRANT


def test_wrong_nonce_rejected() -> None:
    ch = create_challenge("production_deploy", rationale="ship", subject="branch:x")
    wrong = f"{AUTHORIZATION_PHRASE} Code: 000000"
    if ch.nonce != "000000":
        assert authorize_challenge(ch, wrong) is None


def test_bare_phrase_does_not_satisfy_challenge() -> None:
    ch = create_challenge("package_publish")
    assert authorize_challenge(ch, AUTHORIZATION_PHRASE) is None


def test_expired_challenge_rejected() -> None:
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    ch = create_challenge("production_deploy", ttl_seconds=60, now=past)
    # Evaluated "now" the challenge is well past expiry.
    assert authorize_challenge(ch, ch.required_phrase) is None


def test_correct_challenge_accepted_and_binds_action_subject() -> None:
    ch = create_challenge("spend_money", rationale="buy GPU", subject="invoice#42")
    grant = authorize_challenge(ch, ch.required_phrase)
    assert grant is not None
    assert grant.action == "spend_money"
    assert grant.subject == "invoice#42"
    assert grant.challenge_id == ch.challenge_id


def test_grant_emits_content_addressed_artifact() -> None:
    ch = create_challenge("oauth_change", subject="github")
    grant = authorize_challenge(ch, ch.required_phrase)
    assert grant is not None
    art = grant.to_artifact()
    assert art.artifact_type == ARTIFACT_OWNER_GRANT
    assert art.verify_payload() is True
    assert art.payload["action"] == "oauth_change"


def test_create_challenge_rejects_unknown_action() -> None:
    import pytest

    with pytest.raises(ValueError):
        create_challenge("definitely_not_a_gated_action")


def test_owner_auth_stateful_roundtrip() -> None:
    auth = OwnerAuth()
    ch = auth.create_challenge("force_push", subject="branch:y")
    assert auth.authorize_challenge(ch.challenge_id, AUTHORIZATION_PHRASE) is None
    grant = auth.authorize_challenge(ch.challenge_id, ch.required_phrase)
    assert grant is not None
    # Challenge is consumed; a replay does not re-authorize.
    assert auth.authorize_challenge(ch.challenge_id, ch.required_phrase) is None
    assert any(g.action == "force_push" and g.authorized for g in auth.history)


def test_static_phrase_alone_does_not_grant_strict_owner_gate() -> None:
    # The legacy authorize() still works for legacy pending gates...
    auth = OwnerAuth()
    auth.request("production_deploy", risk_class="RC3", rationale="x")
    assert [g.action for g in auth.authorize(AUTHORIZATION_PHRASE)] == ["production_deploy"]
    # ...but it produces no challenge-bound grant artifact, so strict mode
    # (which requires an owner_authorization_grant artifact) is unaffected.
    assert not getattr(auth, "challenges", {})
