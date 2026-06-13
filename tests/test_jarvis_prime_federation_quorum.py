"""Tests for M-of-N quorum authorization (federation/quorum_auth.py)."""

from datetime import datetime, timedelta, timezone

import pytest

from hermes_cli.jarvis_prime.federation import ARTIFACT_QUORUM_GRANT, KIND_QUORUM_GRANT
from hermes_cli.jarvis_prime.federation.quorum_auth import (
    KILL_SWITCH_ACTION,
    QuorumPolicy,
    QuorumChallenge,
    create_quorum_challenge,
    finalize,
    is_satisfied,
    respond,
)
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE, create_challenge


def test_solo_policy_matches_single_owner_challenge_contract():
    quorum = create_quorum_challenge("production_deploy")
    assert quorum.policy == QuorumPolicy.solo()
    solo_challenge = quorum.per_signer["owner"]
    reference = create_challenge("production_deploy")
    # Same phrase format: exact constant + nonce code.
    assert solo_challenge.required_phrase == f"{AUTHORIZATION_PHRASE} Code: {solo_challenge.nonce}"
    assert reference.required_phrase == f"{AUTHORIZATION_PHRASE} Code: {reference.nonce}"

    # The exact per-signer phrase grants; the bare static phrase does not.
    assert respond(quorum, "owner", AUTHORIZATION_PHRASE) is None
    assert respond(quorum, "owner", "yes with authorization") is None
    assert respond(quorum, "owner", f"{AUTHORIZATION_PHRASE} Code: 000000") is None or (
        solo_challenge.nonce == "000000"
    )
    grant = respond(quorum, "owner", solo_challenge.required_phrase)
    assert grant is not None
    assert is_satisfied(quorum)


def test_two_of_three_happy_path(tmp_path):
    policy = QuorumPolicy(threshold=2, signers=("alice", "bob", "carol"))
    quorum = create_quorum_challenge("force_push", policy=policy, subject="repo main")
    assert not is_satisfied(quorum)

    assert respond(quorum, "alice", quorum.per_signer["alice"].required_phrase) is not None
    assert not is_satisfied(quorum)
    assert finalize(quorum) is None

    assert respond(quorum, "bob", quorum.per_signer["bob"].required_phrase) is not None
    assert is_satisfied(quorum)

    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    grant = finalize(quorum, ledger=ledger)
    assert grant is not None
    assert grant.signer_ids == ("alice", "bob")
    assert grant.threshold == 2
    artifact = grant.to_artifact()
    assert artifact.artifact_type == ARTIFACT_QUORUM_GRANT
    assert artifact.verify_payload()
    records = ledger.read_all()
    assert records[-1].kind == KIND_QUORUM_GRANT
    assert ledger.verify_chain().ok


def test_duplicate_signer_never_double_counts():
    policy = QuorumPolicy(threshold=2, signers=("alice", "bob"))
    quorum = create_quorum_challenge("force_push", policy=policy)
    phrase = quorum.per_signer["alice"].required_phrase
    assert respond(quorum, "alice", phrase) is not None
    assert respond(quorum, "alice", phrase) is not None  # idempotent re-response
    assert not is_satisfied(quorum)
    assert finalize(quorum) is None


def test_signer_cannot_answer_anothers_nonce():
    policy = QuorumPolicy(threshold=2, signers=("alice", "bob"))
    quorum = create_quorum_challenge("force_push", policy=policy)
    # bob submits alice's phrase as himself — his own nonce differs, so it fails.
    alice_phrase = quorum.per_signer["alice"].required_phrase
    if quorum.per_signer["bob"].nonce != quorum.per_signer["alice"].nonce:
        assert respond(quorum, "bob", alice_phrase) is None
    assert respond(quorum, "mallory", alice_phrase) is None  # unknown signer


def test_expiry_fails_closed():
    quorum = create_quorum_challenge("production_deploy", ttl_seconds=60)
    phrase = quorum.per_signer["owner"].required_phrase
    later = datetime.now(timezone.utc) + timedelta(seconds=120)
    assert respond(quorum, "owner", phrase, now=later) is None
    # Even with a recorded grant, finalize after expiry refuses.
    assert respond(quorum, "owner", phrase) is not None
    assert finalize(quorum, now=later) is None


def test_non_gated_action_raises_and_kill_switch_is_admitted():
    with pytest.raises(ValueError):
        create_quorum_challenge("make_coffee")
    with pytest.raises(ValueError):
        create_quorum_challenge(KILL_SWITCH_ACTION, extra_actions=frozenset())
    quorum = create_quorum_challenge(
        KILL_SWITCH_ACTION,
        policy=QuorumPolicy(threshold=2, signers=("a", "b", "c")),
    )
    assert respond(quorum, "a", quorum.per_signer["a"].required_phrase) is not None
    assert respond(quorum, "b", quorum.per_signer["b"].required_phrase) is not None
    grant = finalize(quorum)
    assert grant is not None and grant.action == KILL_SWITCH_ACTION


def test_policy_validation():
    assert QuorumPolicy(0, ("a",)).validate()
    assert QuorumPolicy(3, ("a", "b")).validate()
    assert QuorumPolicy(1, ("a", "a")).validate()
    assert QuorumPolicy(1, ()).validate()
    assert QuorumPolicy(1, ("",)).validate()
    assert not QuorumPolicy(2, ("a", "b", "c")).validate()
    with pytest.raises(ValueError):
        create_quorum_challenge("force_push", policy=QuorumPolicy(5, ("a",)))


def test_quorum_challenge_json_round_trip():
    policy = QuorumPolicy(threshold=2, signers=("alice", "bob", "carol"))
    quorum = create_quorum_challenge("force_push", policy=policy, rationale="ship it")
    respond(quorum, "alice", quorum.per_signer["alice"].required_phrase)
    restored = QuorumChallenge.from_dict(quorum.to_dict())
    assert restored.quorum_id == quorum.quorum_id
    assert restored.policy == policy
    assert set(restored.grants) == {"alice"}
    # The restored challenge continues the flow seamlessly.
    assert respond(restored, "bob", restored.per_signer["bob"].required_phrase) is not None
    assert is_satisfied(restored)
