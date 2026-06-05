"""Cockpit device-token hashing and authorization (Sprint 6 core).

Today the cockpit compares a bearer token against a persisted **plaintext**
value and has no per-device revocation. This kernel provides the pieces to
fix both, without yet changing the live auth path (`gateway/cockpit/auth.py`):

* :func:`generate_token` — a high-entropy, URL-safe opaque device token.
* :func:`hash_token` — a stable digest to store **instead of** the raw token.
* :func:`verify_token` — constant-time comparison of a presented token
  against a stored hash.
* :func:`is_authorized` — verify **and** check the token's hash isn't in a
  revocation set (per-device revocation).

Device tokens are 256-bit random, so a plain SHA-256 digest is the right
at-rest representation (no slow KDF needed — these aren't human passwords).
Comparison is constant-time via :func:`hmac.compare_digest`. Revocation
stores token **hashes**, never raw tokens. Wiring this into the gateway
(store the hash, check revocation on each request) is a deliberate follow-up.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Iterable

__all__ = [
    "HASH_PREFIX",
    "generate_token",
    "hash_token",
    "verify_token",
    "is_authorized",
]

HASH_PREFIX = "sha256:"
_DEFAULT_TOKEN_BYTES = 32  # 256 bits of entropy


def generate_token(*, nbytes: int = _DEFAULT_TOKEN_BYTES) -> str:
    """Return a fresh high-entropy, URL-safe device token."""

    if nbytes < 16:
        raise ValueError("token must be at least 16 bytes of entropy")
    return secrets.token_urlsafe(nbytes)


def hash_token(raw: str) -> str:
    """Return the stable, prefixed at-rest digest of ``raw``.

    The prefix records the algorithm so the scheme can evolve later without
    ambiguity. Never store or log ``raw`` — store this instead.
    """

    if not raw:
        raise ValueError("token must be non-empty")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{HASH_PREFIX}{digest}"


def verify_token(raw: str, stored_hash: str) -> bool:
    """Constant-time check that ``raw`` hashes to ``stored_hash``."""

    if not raw or not stored_hash:
        return False
    try:
        candidate = hash_token(raw)
    except ValueError:
        return False
    return hmac.compare_digest(candidate, stored_hash)


def is_authorized(
    raw: str,
    stored_hash: str,
    *,
    revoked_hashes: Iterable[str] = (),
) -> bool:
    """True when ``raw`` matches ``stored_hash`` and is not revoked.

    ``revoked_hashes`` holds token *hashes* (the output of :func:`hash_token`),
    so a revocation list never contains raw tokens.
    """

    if not verify_token(raw, stored_hash):
        return False
    return hash_token(raw) not in set(revoked_hashes)
