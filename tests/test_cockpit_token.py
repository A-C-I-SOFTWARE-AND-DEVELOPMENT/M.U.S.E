"""Tests for cockpit device-token hashing and authorization (Sprint 6)."""

from __future__ import annotations

import pytest

from muse_cli.cockpit_token import (
    HASH_PREFIX,
    generate_token,
    hash_token,
    is_authorized,
    verify_token,
)


def test_generate_token_is_unique_and_urlsafe():
    a = generate_token()
    b = generate_token()
    assert a != b
    assert len(a) >= 32
    # URL-safe alphabet only
    assert all(c.isalnum() or c in "-_" for c in a)


def test_generate_token_rejects_low_entropy():
    with pytest.raises(ValueError):
        generate_token(nbytes=8)


def test_hash_token_deterministic_and_prefixed():
    raw = "device-token-xyz"
    h1 = hash_token(raw)
    h2 = hash_token(raw)
    assert h1 == h2
    assert h1.startswith(HASH_PREFIX)
    assert raw not in h1  # the raw token never appears in its hash


def test_hash_token_rejects_empty():
    with pytest.raises(ValueError):
        hash_token("")


def test_different_tokens_hash_differently():
    assert hash_token("a") != hash_token("b")


def test_verify_token_roundtrip():
    raw = generate_token()
    stored = hash_token(raw)
    assert verify_token(raw, stored) is True


def test_verify_token_wrong_token():
    stored = hash_token("correct")
    assert verify_token("wrong", stored) is False


def test_verify_token_empty_inputs():
    assert verify_token("", hash_token("x")) is False
    assert verify_token("x", "") is False


def test_verify_token_against_tampered_hash():
    raw = generate_token()
    stored = hash_token(raw)
    tampered = stored[:-1] + ("0" if stored[-1] != "0" else "1")
    assert verify_token(raw, tampered) is False


def test_is_authorized_valid_not_revoked():
    raw = generate_token()
    stored = hash_token(raw)
    assert is_authorized(raw, stored) is True


def test_is_authorized_blocks_revoked_hash():
    raw = generate_token()
    stored = hash_token(raw)
    revoked = [hash_token(raw)]
    assert is_authorized(raw, stored, revoked_hashes=revoked) is False


def test_is_authorized_false_for_wrong_token_even_if_not_revoked():
    stored = hash_token("correct")
    assert is_authorized("wrong", stored) is False


def test_revocation_list_holds_hashes_not_raw():
    raw = generate_token()
    stored = hash_token(raw)
    # a revocation list containing the *raw* token must NOT match (we revoke hashes)
    assert is_authorized(raw, stored, revoked_hashes=[raw]) is True
