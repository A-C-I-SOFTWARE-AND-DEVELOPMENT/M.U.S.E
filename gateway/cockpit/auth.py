"""Bearer-token auth for the Hermes cockpit API.

The cockpit HTTP API (consumed by the Jarvis Prime Android app) is
loopback-only by default, but still requires a bearer token on every
route except ``/v1/health`` — so a hostile process that can reach the
loopback port can't drive the agent without the token the user paired
with. The token is generated once and stored owner-only under
``${HERMES_HOME}/cockpit/token``.

Stdlib-only (Termux-safe). No network, no third-party deps.
"""

from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path


def cockpit_dir() -> Path:
    """``${HERMES_HOME:-~/.hermes}/cockpit`` — cockpit state dir."""
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "cockpit"


def token_path() -> Path:
    return cockpit_dir() / "token"


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
    if not presented:
        return False
    if token_matches(presented, expected):
        return True
    # Lazy import (see docstring): avoids a circular import with
    # gateway.cockpit.device_pairing, which imports this module.
    from gateway.cockpit import device_pairing

    return device_pairing.verify_device_token(presented) is not None


__all__ = [
    "authorize_bearer",
    "cockpit_dir",
    "extract_bearer",
    "load_or_create_token",
    "read_token",
    "rotate_token",
    "token_matches",
    "token_path",
]
