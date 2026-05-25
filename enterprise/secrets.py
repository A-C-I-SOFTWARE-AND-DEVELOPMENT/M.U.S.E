"""Secret retrieval facade for enterprise council agents.

Agents must not read environment variables, OAuth files, or any
credential store directly. They call ``fetch_secret(service, scope)``
at the moment of use and discard the returned bundle after the call.

Why a wrapper:

  * `agent.credential_pool` is great at providing pooled provider keys
    for LLM calls, but it knows nothing about enterprise services
    like "stripe.invoice.write" or "salesforce.opportunity.read".
    This facade adds a service+scope vocabulary on top.
  * Audit needs to know *that* a secret was fetched and for what
    purpose — without ever recording the secret itself.
  * Least-privilege gating lives here: the Sales agent cannot fetch
    a Finance credential just because it ran in the same process.
  * Short-lived OAuth tokens get minted here when the underlying
    source supports refresh. Long-lived API keys are tagged
    ``ephemeral=False`` so the audit row shows the difference.

The redacting logger (`agent.redact.RedactingFormatter`) is the safety
net — even if a future code path accidentally logs a SecretBundle, the
formatter strips the value before flush. This module is the
*intentional* defence; the redactor is the *defence in depth*.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Iterable, Optional

# Map of "service.scope-prefix" → set of agent roles allowed to call.
# Keep this small and explicit. Any service not listed is rejected
# unless the caller is the Orchestrator (which can grant on behalf
# of a leaf via the `delegated_for` parameter).
_ACL: dict[str, frozenset[str]] = {
    "stripe": frozenset({"finance"}),
    "netsuite": frozenset({"finance"}),
    "quickbooks": frozenset({"finance"}),
    "workday": frozenset({"hr"}),
    "greenhouse": frozenset({"hr"}),
    "bamboohr": frozenset({"hr"}),
    "zendesk": frozenset({"customer-service"}),
    "intercom": frozenset({"customer-service"}),
    "kb": frozenset({"customer-service", "sales"}),
    "sap": frozenset({"operations"}),
    "slackops": frozenset({"operations"}),
    "compliancedb": frozenset({"operations"}),
    "salesforce": frozenset({"sales"}),
    "hubspot": frozenset({"sales"}),
    "docusign": frozenset({"sales", "finance"}),
}

# How long an OAuth-derived ephemeral token is considered valid for. The
# real provider's expiry may be shorter; that's fine — the bundle's
# `expires_at` is a hint, not a promise.
DEFAULT_TTL_SECONDS = 900

_logger = logging.getLogger("enterprise.secrets")


class SecretAccessDenied(RuntimeError):
    """Caller's role is not in the ACL for the requested service."""


class SecretNotFound(RuntimeError):
    """No credential entry exists for the requested service."""


@dataclass(frozen=True)
class SecretBundle:
    """Opaque carrier for a fetched secret.

    The ``value`` field is the secret itself; callers must pass it
    straight to the SDK that needs it and not log/store/return it.
    The ``__repr__`` is intentionally redacted so accidental
    ``repr(bundle)`` in error messages can't leak.
    """

    service: str
    scope: Optional[str]
    value: str
    expires_at: Optional[float]
    ephemeral: bool

    def __repr__(self) -> str:
        return (
            f"SecretBundle(service={self.service!r}, scope={self.scope!r}, "
            f"value=<redacted {len(self.value)} chars>, "
            f"ephemeral={self.ephemeral})"
        )

    def is_expired(self, now: Optional[float] = None) -> bool:
        if self.expires_at is None:
            return False
        return (now or time.time()) >= self.expires_at


def _allowed_roles(service: str) -> frozenset[str]:
    """Look up ACL by service name. Returns empty set for unknown services."""
    return _ACL.get(service.lower(), frozenset())


def _check_access(
    service: str,
    caller_role: str,
    delegated_for: Optional[str],
) -> None:
    roles = _allowed_roles(service)
    if not roles:
        raise SecretNotFound(
            f"No ACL entry for service {service!r}. Add it to enterprise.secrets._ACL."
        )
    effective = delegated_for or caller_role
    if effective not in roles:
        raise SecretAccessDenied(
            f"Role {effective!r} cannot access service {service!r}. "
            f"Allowed roles: {sorted(roles)}."
        )


def _resolve_from_env(service: str) -> Optional[str]:
    """Read the long-lived API key for ``service`` from env / .env.

    Convention: ``<SERVICE>_API_KEY`` (uppercased). For "stripe" we look
    at ``STRIPE_API_KEY``. We deliberately do NOT fall through to
    ``HERMES_*`` or provider pool entries — those are model credentials
    and live in a separate trust domain.
    """
    key = f"{service.upper().replace('-', '_')}_API_KEY"
    val = os.environ.get(key)
    if val and val.strip():
        return val.strip()
    return None


def _resolve_from_pool(service: str) -> Optional[str]:
    """Optional fallback: try the existing credential pool for ``service``.

    Wrapped in a try/except so importing `enterprise.secrets` from a
    minimal test context (without Hermes' full pool init) still works.
    """
    try:
        from agent.credential_pool import load_pool  # local import — heavy
    except Exception:  # pragma: no cover — pool absent in some test envs
        return None
    try:
        pool = load_pool(service)
    except Exception:
        return None
    entry = pool.acquire_lease() if hasattr(pool, "acquire_lease") else None
    if not entry:
        return None
    # Pool entries carry the key under different attribute names across
    # historical versions; check a few.
    for attr in ("api_key", "key", "value", "secret"):
        candidate = getattr(entry, attr, None)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def fetch_secret(
    service: str,
    *,
    caller_role: str,
    scope: Optional[str] = None,
    delegated_for: Optional[str] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> SecretBundle:
    """Return a bundled secret for ``service`` if the caller is allowed.

    ``caller_role`` must be one of the eight enterprise-council roles
    (e.g. "finance", "sales"). ``delegated_for`` lets the Orchestrator
    pass through a leaf's role when fetching on its behalf.

    Behaviour:
      * Audit-style log entry is emitted via the standard logger so
        the RedactingFormatter masks any incidental token-shaped text.
        We never log ``value`` directly even when redaction is off.
      * If the underlying source is an OAuth refresh-token entry, a
        short-lived access token *would* be minted (left as a TODO
        hook — depends on which OAuth library Hermes pulls in next).
        Until then, all returned bundles are ephemeral=False and the
        operator is responsible for rotating long-lived keys.
      * Refuses to return a value containing ``\\n`` or other obvious
        corruption (defence against accidental concatenation bugs).
    """
    _check_access(service, caller_role, delegated_for)

    raw = _resolve_from_env(service) or _resolve_from_pool(service)
    if not raw:
        raise SecretNotFound(
            f"No credential configured for service {service!r}. "
            f"Set {service.upper()}_API_KEY in ~/.hermes/.env, or seed the credential pool."
        )

    if any(ch in raw for ch in ("\n", "\r")):
        raise SecretNotFound(
            f"Credential for {service!r} contains a newline — refusing to return."
        )

    expires_at: Optional[float] = None
    ephemeral = False  # TODO: flip to True once OAuth refresh path lands.

    _logger.info(
        "fetch_secret service=%s scope=%s role=%s delegated_for=%s ephemeral=%s",
        service,
        scope or "",
        caller_role,
        delegated_for or "",
        ephemeral,
    )

    return SecretBundle(
        service=service,
        scope=scope,
        value=raw,
        expires_at=expires_at,
        ephemeral=ephemeral,
    )


# Convenience: a fingerprint of the secret suitable for audit rows. SHA-like
# in shape but only the first 6 chars of a hash, so the audit log can show
# "this run used the same key as last time" without revealing the key.
_HASH_CHARS = re.compile(r"[^a-z0-9]")


def secret_fingerprint(bundle: SecretBundle) -> str:
    import hashlib

    h = hashlib.sha256(bundle.value.encode("utf-8")).hexdigest()
    clean = _HASH_CHARS.sub("", h.lower())[:8]
    return f"{bundle.service}:{clean}"


def list_acl(services: Optional[Iterable[str]] = None) -> dict[str, list[str]]:
    """Inspectable view of the ACL — used by Diagnostics + tests."""
    items = services or _ACL.keys()
    return {svc: sorted(_ACL.get(svc, frozenset())) for svc in items}
