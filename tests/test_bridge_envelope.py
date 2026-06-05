"""Tests for the signed bridge-command envelope (Sprint 12)."""

from __future__ import annotations

import pytest

from hermes_cli.bridge_envelope import (
    SIGNATURE_FIELD,
    VerifyResult,
    canonical_bytes,
    sign,
    signed_envelope,
    verify,
)

KEY = "shared-secret-key"
NOW = 1000.0


def _payload(**over) -> dict:
    base = {
        "command_id": "bcmd_1",
        "job_id": "job_1",
        "workspace_id": "repo_alias",
        "nonce": "nonce-1",
        "expires_at": NOW + 100,
    }
    base.update(over)
    return base


# --- signing ---------------------------------------------------------------


def test_sign_is_deterministic():
    p = _payload()
    assert sign(p, KEY) == sign(p, KEY)


def test_sign_requires_key():
    with pytest.raises(ValueError):
        sign(_payload(), "")


def test_signature_is_key_order_independent():
    a = {"a": 1, "b": 2, "nonce": "n"}
    b = {"nonce": "n", "b": 2, "a": 1}
    assert sign(a, KEY) == sign(b, KEY)


def test_canonical_bytes_excludes_signature():
    p = _payload()
    signed = signed_envelope(p, KEY)
    assert canonical_bytes(p) == canonical_bytes(signed)


# --- happy path ------------------------------------------------------------


def test_signed_envelope_verifies_ok():
    env = signed_envelope(_payload(), KEY)
    assert SIGNATURE_FIELD in env
    v = verify(env, KEY, now=NOW)
    assert v.ok
    assert v.result is VerifyResult.OK


def test_expiry_boundary_inclusive():
    env = signed_envelope(_payload(expires_at=NOW), KEY)
    # now == expires_at is still valid (not past)
    assert verify(env, KEY, now=NOW).ok


def test_no_expiry_field_is_ok():
    p = _payload()
    del p["expires_at"]
    env = signed_envelope(p, KEY)
    assert verify(env, KEY, now=NOW).ok


# --- signature failures ----------------------------------------------------


def test_tampered_field_fails_signature():
    env = signed_envelope(_payload(), KEY)
    tampered = {**env, "job_id": "evil_job"}
    assert verify(tampered, KEY, now=NOW).result is VerifyResult.BAD_SIGNATURE


def test_wrong_key_fails_signature():
    env = signed_envelope(_payload(), KEY)
    assert verify(env, "other-key", now=NOW).result is VerifyResult.BAD_SIGNATURE


def test_missing_signature_is_malformed():
    assert verify(_payload(), KEY, now=NOW).result is VerifyResult.MALFORMED


def test_non_mapping_is_malformed():
    assert verify("not-an-envelope", KEY, now=NOW).result is VerifyResult.MALFORMED


def test_bad_expires_at_type_is_malformed():
    env = signed_envelope(_payload(expires_at="soon"), KEY)
    assert verify(env, KEY, now=NOW).result is VerifyResult.MALFORMED


# --- expiry ----------------------------------------------------------------


def test_expired_envelope_rejected():
    env = signed_envelope(_payload(expires_at=NOW - 1), KEY)
    assert verify(env, KEY, now=NOW).result is VerifyResult.EXPIRED


# --- replay ----------------------------------------------------------------


def test_replayed_nonce_rejected():
    env = signed_envelope(_payload(nonce="abc"), KEY)
    seen: set[str] = set()
    first = verify(env, KEY, now=NOW, seen_nonces=seen)
    assert first.ok
    assert "abc" in seen
    second = verify(env, KEY, now=NOW, seen_nonces=seen)
    assert second.result is VerifyResult.REPLAYED


def test_no_seen_set_means_no_replay_enforcement():
    env = signed_envelope(_payload(nonce="abc"), KEY)
    assert verify(env, KEY, now=NOW).ok
    assert verify(env, KEY, now=NOW).ok  # OK again without a store


def test_bad_signature_does_not_consume_nonce():
    env = signed_envelope(_payload(nonce="abc"), KEY)
    tampered = {**env, "job_id": "evil"}
    seen: set[str] = set()
    assert verify(tampered, KEY, now=NOW, seen_nonces=seen).result is VerifyResult.BAD_SIGNATURE
    assert seen == set()  # nonce not burned by a forged envelope


def test_expired_does_not_consume_nonce():
    env = signed_envelope(_payload(nonce="abc", expires_at=NOW - 1), KEY)
    seen: set[str] = set()
    assert verify(env, KEY, now=NOW, seen_nonces=seen).result is VerifyResult.EXPIRED
    assert seen == set()
