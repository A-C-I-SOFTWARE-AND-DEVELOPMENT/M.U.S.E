"""Bearer-token auth for the Hermes cockpit API.

The cockpit HTTP API (consumed by the muse Android app) is
loopback-only by default, but still requires a bearer token on every
route except ``/v1/health`` — so a hostile process that can reach the
loopback port can't drive the agent without the token the user paired
with. The token is generated once and stored owner-only under
``${HERMES_HOME}/cockpit/token``.

Stdlib-only (Termux-safe). No network, no third-party deps.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path


def cockpit_dir() -> Path:
    """``${HERMES_HOME:-~/.hermes}/cockpit`` — cockpit state dir."""
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "cockpit"


def token_path() -> Path:
    return cockpit_dir() / "token"


SERVICE_SCOPES = frozenset(
    {
        "status",
        "catalog",
        "agents",
        "jobs",
        "cron",
        "kanban",
        "approvals",
        "routing",
        "emergency_stop",
    }
)
SERVICE_TOKEN_DEFAULT_TTL_SECONDS = 900
SERVICE_TOKEN_MAX_TTL_SECONDS = 3600
_SERVICE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$")
_SERVICE_LOCK = threading.RLock()
_REPLAY_LOCK = threading.Lock()
_SEEN_REQUESTS: dict[tuple[str, str], float] = {}


@dataclass(frozen=True)
class AuthPrincipal:
    """Authenticated cockpit caller without exposing credential material."""

    kind: str
    identity: str
    credential_id: str
    scopes: frozenset[str] = frozenset()
    expires_at: float | None = None

    @property
    def is_owner(self) -> bool:
        return self.kind in {"owner_shared", "owner_device"}

    @property
    def is_service(self) -> bool:
        return self.kind == "service"


@dataclass(frozen=True)
class IssuedServiceToken:
    credential_id: str
    identity: str
    token: str
    scopes: frozenset[str]
    issued_at: float
    expires_at: float


def service_tokens_path() -> Path:
    return cockpit_dir() / "service_tokens.jsonl"


def _hash_service_token(raw: str) -> str:
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _service_records() -> list[dict]:
    path = service_tokens_path()
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    records: list[dict] = []
    for line in lines:
        try:
            record = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def issue_service_token(
    identity: str,
    scopes: list[str] | tuple[str, ...] | set[str] | frozenset[str],
    *,
    ttl_seconds: int = SERVICE_TOKEN_DEFAULT_TTL_SECONDS,
) -> IssuedServiceToken:
    """Mint a short-lived, hash-at-rest service credential.

    Only the explicit control-plane scopes in :data:`SERVICE_SCOPES` are
    accepted. The HTTP handler that calls this function is owner-only.
    """
    normalized_identity = str(identity or "").strip().lower()
    if not _SERVICE_ID_RE.fullmatch(normalized_identity):
        raise ValueError("invalid service identity")
    normalized_scopes = frozenset(str(scope).strip().lower() for scope in scopes)
    if not normalized_scopes:
        raise ValueError("at least one service scope is required")
    unknown = normalized_scopes - SERVICE_SCOPES
    if unknown:
        raise ValueError(f"unknown service scope(s): {', '.join(sorted(unknown))}")
    try:
        ttl = int(ttl_seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError("ttl_seconds must be an integer") from exc
    if ttl < 60 or ttl > SERVICE_TOKEN_MAX_TTL_SECONDS:
        raise ValueError(
            f"ttl_seconds must be between 60 and {SERVICE_TOKEN_MAX_TTL_SECONDS}"
        )

    now = time.time()
    raw = "muse_svc_" + secrets.token_urlsafe(32)
    credential_id = "svc_" + secrets.token_hex(8)
    record = {
        "kind": "service",
        "credential_id": credential_id,
        "identity": normalized_identity,
        "token_hash": _hash_service_token(raw),
        "scopes": sorted(normalized_scopes),
        "issued_at": now,
        "expires_at": now + ttl,
    }
    with _SERVICE_LOCK:
        path = service_tokens_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        _tighten(path)
    return IssuedServiceToken(
        credential_id=credential_id,
        identity=normalized_identity,
        token=raw,
        scopes=normalized_scopes,
        issued_at=now,
        expires_at=now + ttl,
    )


def verify_service_token(raw: str | None) -> AuthPrincipal | None:
    """Resolve a live service credential, rejecting expired/unknown tokens."""
    if not raw or not raw.startswith("muse_svc_"):
        return None
    presented_hash = _hash_service_token(raw)
    now = time.time()
    with _SERVICE_LOCK:
        records = _service_records()
    # Do not stop on the first mismatch; compare every stored hash.
    matched: dict | None = None
    for record in records:
        stored = str(record.get("token_hash") or "")
        if stored and hmac.compare_digest(presented_hash, stored):
            matched = record
    if matched is None:
        return None
    try:
        expires_at = float(matched.get("expires_at", 0))
    except (TypeError, ValueError):
        return None
    if expires_at <= now:
        return None
    scopes = frozenset(
        scope
        for scope in (str(value).strip().lower() for value in matched.get("scopes", []))
        if scope in SERVICE_SCOPES
    )
    if not scopes:
        return None
    return AuthPrincipal(
        kind="service",
        identity=str(matched.get("identity") or "unknown-service"),
        credential_id=str(matched.get("credential_id") or "unknown"),
        scopes=scopes,
        expires_at=expires_at,
    )


def valid_request_id(value: str | None) -> bool:
    """Whether a caller-supplied replay identifier is bounded and printable."""
    return bool(value and _REQUEST_ID_RE.fullmatch(value))


def claim_request_id(
    principal: AuthPrincipal,
    request_id: str,
    *,
    now: float | None = None,
) -> bool:
    """Claim one service request id for the credential lifetime.

    The cache is process-local defense in depth. A repeated mutating request on
    the same running gateway is rejected; route handlers still remain
    idempotent/owner-gated where their existing contracts require it.
    """
    if not principal.is_service or not valid_request_id(request_id):
        return False
    current = time.time() if now is None else float(now)
    expiry = float(principal.expires_at or (current + SERVICE_TOKEN_MAX_TTL_SECONDS))
    key = (principal.credential_id, request_id)
    with _REPLAY_LOCK:
        expired = [item for item, until in _SEEN_REQUESTS.items() if until <= current]
        for item in expired:
            _SEEN_REQUESTS.pop(item, None)
        if key in _SEEN_REQUESTS:
            return False
        _SEEN_REQUESTS[key] = expiry
    return True


def _tighten(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - platform-dependent
        pass


def load_or_create_token() -> str:
    """Return the cockpit pairing token, generating + persisting one once.

    The token is a URL-safe 32-byte secret. The file is written owner-only
    (0600). Concurrent first-runs are fine: the last writer wins and both
    end up with a valid token.
    """
    path = token_path()
    existing = read_token()
    if existing:
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(token, encoding="utf-8")
    _tighten(tmp)
    os.replace(tmp, path)
    _tighten(path)
    return token


def read_token() -> str | None:
    """Return the persisted token, or None if not yet created/readable."""
    path = token_path()
    if not path.is_file():
        return None
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:  # pragma: no cover - defensive
        return None
    return value or None


def rotate_token() -> str:
    """Generate a fresh token, replacing any existing one. Returns the new token."""
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(token, encoding="utf-8")
    _tighten(tmp)
    os.replace(tmp, path)
    _tighten(path)
    return token


def token_matches(presented: str | None, expected: str | None) -> bool:
    """Constant-time compare of a presented bearer token against expected."""
    if not presented or not expected:
        return False
    return hmac.compare_digest(presented, expected)


def extract_bearer(authorization_header: str | None) -> str | None:
    """Pull the token out of an ``Authorization: Bearer <token>`` header."""
    if not authorization_header:
        return None
    parts = authorization_header.strip().split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


def authenticate_bearer(
    presented: str | None, expected: str | None
) -> AuthPrincipal | None:
    """Resolve owner, owner-device, or scoped service identity."""
    if not presented:
        return None
    if token_matches(presented, expected):
        return AuthPrincipal(
            kind="owner_shared",
            identity="owner",
            credential_id="cockpit-shared",
        )
    from gateway.cockpit import device_pairing

    device_id = device_pairing.verify_device_token(presented)
    if device_id is not None:
        return AuthPrincipal(
            kind="owner_device",
            identity=device_id,
            credential_id=device_id,
        )
    return verify_service_token(presented)


def authorize_bearer(presented: str | None, expected: str | None) -> bool:
    """Authorize a presented bearer token against EITHER credential path.

    A request is authorized when the presented token is:

    * the shared cockpit token (``expected``) — the original, unchanged
      path, compared constant-time via :func:`token_matches`; or
    * a valid per-device pairing token — i.e.
      :func:`gateway.cockpit.device_pairing.verify_device_token` returns a
      ``device_id`` (constant-time per stored hash, revoke-aware: a revoked
      device's token never authenticates).

    This is purely additive: the shared-token decision is identical to
    :func:`token_matches`, and a missing/garbage token still returns
    ``False`` (the caller 401s). The per-device check is consulted **only**
    when the shared token does not match, so it can never weaken the
    existing path.

    ``device_pairing`` is imported lazily because that module imports this
    one at load time; a top-level import here would be circular.
    """
    return authenticate_bearer(presented, expected) is not None


__all__ = [
    "AuthPrincipal",
    "IssuedServiceToken",
    "SERVICE_SCOPES",
    "SERVICE_TOKEN_DEFAULT_TTL_SECONDS",
    "SERVICE_TOKEN_MAX_TTL_SECONDS",
    "authenticate_bearer",
    "authorize_bearer",
    "claim_request_id",
    "cockpit_dir",
    "extract_bearer",
    "issue_service_token",
    "load_or_create_token",
    "read_token",
    "rotate_token",
    "service_tokens_path",
    "token_matches",
    "token_path",
    "valid_request_id",
    "verify_service_token",
]
