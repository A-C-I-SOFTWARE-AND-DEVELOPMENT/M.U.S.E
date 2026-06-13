"""Sovereign-node identity with opportunistic signing (Vol VI Part 1/3).

Mirrors the ``guardrail_evidence`` stance on crypto: the cross-node trust
anchor is always the **content hash** (``payload_sha256`` / ``bundle_sha256``);
signatures strengthen attestations opportunistically. Ed25519 is used when
``cryptography`` happens to be importable (it ships transitively via
``PyJWT[crypto]``); otherwise an HMAC-SHA256 over a locally held secret is
used — which peers cannot verify, and honestly report as such.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import canonical_json, sha256_hex

from . import federation_dir

# Opportunistic Ed25519 (never required). The module namespace is held in an
# Any-typed slot so the ImportError fallback type-checks cleanly.
_ED25519: Any = None
try:
    from cryptography.hazmat.primitives.asymmetric import ed25519 as _ed25519_module

    _ED25519 = _ed25519_module
    _ED25519_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    _ED25519_AVAILABLE = False

ALGO_ED25519 = "ed25519"
ALGO_HMAC = "hmac-sha256"

_IDENTITY_FILE = "identity.json"
_SECRET_FILE = "node_secret"
_PRIVATE_KEY_FILE = "node_ed25519_private"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chmod_private(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - platform-dependent
        pass


def _write_private_bytes(path: Path, data: bytes) -> None:
    """Create a key file with 0o600 from the first instant (no chmod window).

    Local key material on disk is by design (the SSH-key pattern): this node
    is local-first and stdlib-first, so the secret never leaves the machine;
    restrictive permissions are applied atomically at creation.
    """

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


@dataclass(frozen=True)
class NodeIdentity:
    """One sovereign MUSE node's public identity."""

    node_id: str  # "node_" + sha256(public material)[:16] — content-derived
    display_name: str
    created_at: str
    algo: str  # ed25519 | hmac-sha256
    public_key_hex: str  # "" for hmac

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "display_name": self.display_name,
            "created_at": self.created_at,
            "algo": self.algo,
            "public_key_hex": self.public_key_hex,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NodeIdentity":
        return cls(
            node_id=str(data["node_id"]),
            display_name=str(data.get("display_name", "")),
            created_at=str(data.get("created_at", "")),
            algo=str(data.get("algo", ALGO_HMAC)),
            public_key_hex=str(data.get("public_key_hex", "")),
        )


def default_identity_dir() -> Path:
    return federation_dir()


def ed25519_available() -> bool:
    return _ED25519_AVAILABLE


def init_identity(
    display_name: str,
    *,
    dir: Optional[Path] = None,
    prefer_ed25519: bool = True,
) -> NodeIdentity:
    """Create (or return the existing) node identity in ``dir``."""

    base = Path(dir) if dir is not None else default_identity_dir()
    base.mkdir(parents=True, exist_ok=True)
    existing = load_identity(base)
    if existing is not None:
        return existing

    if prefer_ed25519 and _ED25519_AVAILABLE:
        private_key = _ED25519.Ed25519PrivateKey.generate()
        from cryptography.hazmat.primitives import serialization

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_hex = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()
        key_path = base / _PRIVATE_KEY_FILE
        _write_private_bytes(key_path, private_bytes)
        algo = ALGO_ED25519
        public_material = public_hex
    else:
        secret = secrets.token_bytes(32)
        secret_path = base / _SECRET_FILE
        _write_private_bytes(secret_path, secret)
        algo = ALGO_HMAC
        public_hex = ""
        # No public key exists; derive the id from a hash of the secret so the
        # id is stable without ever disclosing the secret itself.
        public_material = sha256_hex(secret.hex())

    identity = NodeIdentity(
        node_id="node_" + sha256_hex(public_material)[:16],
        display_name=display_name,
        created_at=_utc_iso(),
        algo=algo,
        public_key_hex=public_hex,
    )
    identity_path = base / _IDENTITY_FILE
    identity_path.write_text(
        json.dumps(identity.to_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    _chmod_private(identity_path)
    return identity


def load_identity(dir: Optional[Path] = None) -> Optional[NodeIdentity]:
    base = Path(dir) if dir is not None else default_identity_dir()
    path = base / _IDENTITY_FILE
    if not path.exists():
        return None
    try:
        return NodeIdentity.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def sign_payload(payload: Mapping[str, Any], *, dir: Optional[Path] = None) -> dict[str, str]:
    """Sign ``canonical_json(payload)`` with this node's key material.

    Returns ``{}`` when no identity exists — signatures are opportunistic, the
    content hash remains the trust anchor.
    """

    base = Path(dir) if dir is not None else default_identity_dir()
    identity = load_identity(base)
    if identity is None:
        return {}
    message = canonical_json(dict(payload)).encode("utf-8")

    if identity.algo == ALGO_ED25519 and _ED25519_AVAILABLE:
        key_path = base / _PRIVATE_KEY_FILE
        if not key_path.exists():
            return {}
        private_key = _ED25519.Ed25519PrivateKey.from_private_bytes(key_path.read_bytes())
        signature = private_key.sign(message).hex()
    else:
        secret_path = base / _SECRET_FILE
        if not secret_path.exists():
            return {}
        signature = hmac.new(secret_path.read_bytes(), message, "sha256").hexdigest()

    return {"algo": identity.algo, "key_id": identity.node_id, "signature_hex": signature}


def verify_signature(
    payload: Mapping[str, Any],
    signature: Mapping[str, str],
    identity: NodeIdentity,
) -> tuple[bool, str]:
    """Verify a peer's signature. HMAC signatures are honestly unverifiable."""

    if not signature:
        return False, "no signature present"
    algo = str(signature.get("algo", ""))
    if algo == ALGO_HMAC:
        return False, "unverifiable-by-peer (hmac is a local-only commitment)"
    if algo != ALGO_ED25519:
        return False, f"unknown signature algo {algo!r}"
    if not _ED25519_AVAILABLE:
        return False, "ed25519 verification unavailable in this environment"
    if not identity.public_key_hex:
        return False, "peer identity carries no public key"
    message = canonical_json(dict(payload)).encode("utf-8")
    try:
        public_key = _ED25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(identity.public_key_hex))
        public_key.verify(bytes.fromhex(str(signature.get("signature_hex", ""))), message)
    except Exception:
        return False, "ed25519 signature invalid"
    return True, "ed25519 signature valid"


__all__ = [
    "ALGO_ED25519",
    "ALGO_HMAC",
    "NodeIdentity",
    "default_identity_dir",
    "ed25519_available",
    "init_identity",
    "load_identity",
    "sign_payload",
    "verify_signature",
]
