"""Signed bridge-command envelope (Sprint 12 core).

The Windows bridge's current ``JobManifest`` carries a per-job ``auth_token``
but **no cryptographic signature, nonce, or expiry** — the plan's
non-negotiable for any remote-execution path ("signed command envelopes with
nonce and expiry required"). This kernel provides detached HMAC signing and a
verifier that enforces, in order:

1. a valid **signature** (HMAC-SHA256 over a canonical serialization);
2. **expiry** (``now <= expires_at``);
3. a single-use **nonce** (anti-replay).

The signing key is a shared secret the *caller* reads from config/env and
passes in — this module never reads secrets itself. The canonical bytes are
JSON with sorted keys and the signature field excluded, so the signature is
stable regardless of dict ordering and a round-trip verifies.

Anti-replay needs a caller-owned ``seen_nonces`` set (persisted by the
caller). A nonce is recorded only after the signature and expiry checks pass,
so a forged or expired envelope can't burn a nonce. Wiring this into the
bridge transport (replacing the bare token) is a deliberate follow-up.
"""

from __future__ import annotations

import enum
import hashlib
import hmac
import json
from collections.abc import Mapping, MutableSet
from dataclasses import dataclass
from typing import Any, Optional

__all__ = [
    "SIGNATURE_FIELD",
    "VerifyResult",
    "Verification",
    "canonical_bytes",
    "sign",
    "signed_envelope",
    "verify",
]

SIGNATURE_FIELD = "signature"


def canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    """Stable bytes to sign: sorted-key compact JSON, signature excluded."""

    filtered = {k: payload[k] for k in payload if k != SIGNATURE_FIELD}
    return json.dumps(
        filtered, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def sign(payload: Mapping[str, Any], key: str) -> str:
    """Detached HMAC-SHA256 signature over the canonical bytes of ``payload``."""

    if not key:
        raise ValueError("signing key must be non-empty")
    return hmac.new(
        key.encode("utf-8"), canonical_bytes(payload), hashlib.sha256
    ).hexdigest()


def signed_envelope(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    """Return ``payload`` plus its ``signature`` field."""

    return {**payload, SIGNATURE_FIELD: sign(payload, key)}


class VerifyResult(str, enum.Enum):
    OK = "ok"
    MALFORMED = "malformed"
    BAD_SIGNATURE = "bad_signature"
    EXPIRED = "expired"
    REPLAYED = "replayed"


@dataclass(frozen=True)
class Verification:
    result: VerifyResult
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.result is VerifyResult.OK


def verify(
    envelope: Any,
    key: str,
    *,
    now: float,
    seen_nonces: Optional[MutableSet[str]] = None,
) -> Verification:
    """Verify signature, then expiry, then nonce (anti-replay).

    On success, if ``seen_nonces`` is provided and the envelope has a
    ``nonce``, the nonce is added to the set. The nonce is recorded only after
    signature and expiry pass, so invalid envelopes can't consume nonces.
    """

    if not isinstance(envelope, Mapping):
        return Verification(VerifyResult.MALFORMED, "envelope is not a mapping")

    signature = envelope.get(SIGNATURE_FIELD)
    if not isinstance(signature, str) or not signature:
        return Verification(VerifyResult.MALFORMED, "missing signature")

    expected = sign(envelope, key)
    if not hmac.compare_digest(expected, signature):
        return Verification(VerifyResult.BAD_SIGNATURE, "signature mismatch")

    expires_at = envelope.get("expires_at")
    if expires_at is not None:
        try:
            expiry = float(expires_at)
        except (TypeError, ValueError):
            return Verification(VerifyResult.MALFORMED, "expires_at is not a number")
        if now > expiry:
            return Verification(VerifyResult.EXPIRED, "envelope expired")

    nonce = envelope.get("nonce")
    if seen_nonces is not None and nonce is not None:
        nonce_key = str(nonce)
        if nonce_key in seen_nonces:
            return Verification(VerifyResult.REPLAYED, "nonce already used")
        seen_nonces.add(nonce_key)

    return Verification(VerifyResult.OK)
