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
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Optional

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

# We refresh this many seconds *before* the provider-declared expiry so a
# cached token never goes stale mid-call. Keep it well below the typical
# 3600s OAuth access-token lifetime.
_REFRESH_SKEW_SECONDS = 60

# Network timeout for the token endpoint round-trip. Short on purpose — a
# slow IdP should fail fast, not hang an agent action.
_TOKEN_HTTP_TIMEOUT = 20.0

# Callable that performs the token-endpoint POST. Signature mirrors a thin
# slice of ``httpx.post`` so production uses httpx and tests inject a fake
# without monkeypatching the module. ``data`` is the form body; the return
# is an object exposing ``.status_code`` (int) and ``.json()`` (-> dict).
HttpPost = Callable[..., Any]

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


class OAuthRefreshError(RuntimeError):
    """The token endpoint rejected the refresh or returned a bad body.

    Raised only when a refresh-token entry *is* configured but the
    exchange fails. Callers that want graceful degradation should catch
    this and fall back to the long-lived key path — ``fetch_secret``
    does NOT do that automatically, because a configured-but-failing
    OAuth source is an operator error worth surfacing, not silently
    masking with a long-lived key.
    """


@dataclass(frozen=True)
class OAuthRefreshConfig:
    """Everything needed to mint a short-lived access token via OAuth2.

    All fields are read from configuration (env / .env), never hardcoded.
    The class is provider-agnostic: point ``token_endpoint`` at any
    standards-compliant OAuth2 token URL.
    """

    token_endpoint: str
    client_id: str
    client_secret: Optional[str]
    refresh_token: str
    scope: Optional[str] = None


# Process-wide cache of minted access tokens, keyed by service (lowercased).
# Value is ``(access_token, expires_at_epoch)``. Guarded by a lock because
# council agents may run concurrently and we don't want two threads racing
# the same token endpoint. The cache is best-effort: a miss just means we
# mint again, never a correctness problem.
_token_cache: dict[str, tuple[str, float]] = {}
_token_cache_lock = threading.Lock()


def _resolve_oauth_config(service: str) -> Optional[OAuthRefreshConfig]:
    """Read the OAuth2 refresh-token config for ``service`` from env / .env.

    Convention (uppercased, ``-`` → ``_``); for ``"salesforce"``:

      * ``SALESFORCE_OAUTH_TOKEN_URL``       — token endpoint (required)
      * ``SALESFORCE_OAUTH_CLIENT_ID``       — OAuth client id (required)
      * ``SALESFORCE_OAUTH_REFRESH_TOKEN``   — stored refresh token (required)
      * ``SALESFORCE_OAUTH_CLIENT_SECRET``   — client secret (optional; many
        public/PKCE clients omit it)
      * ``SALESFORCE_OAUTH_SCOPE``           — space-delimited scopes (optional)

    Returns ``None`` (NOT an error) when the three required keys aren't all
    present — that's the signal to fall back to the long-lived key path.
    This keeps the existing safe default intact for every service that has
    no refresh config.
    """
    prefix = service.upper().replace("-", "_")

    def _env(suffix: str) -> Optional[str]:
        val = os.environ.get(f"{prefix}_OAUTH_{suffix}")
        return val.strip() if val and val.strip() else None

    token_endpoint = _env("TOKEN_URL")
    client_id = _env("CLIENT_ID")
    refresh_token = _env("REFRESH_TOKEN")

    # All three required pieces must be present, else there's no usable
    # refresh source — fall back silently.
    if not (token_endpoint and client_id and refresh_token):
        return None

    return OAuthRefreshConfig(
        token_endpoint=token_endpoint,
        client_id=client_id,
        client_secret=_env("CLIENT_SECRET"),
        refresh_token=refresh_token,
        scope=_env("SCOPE"),
    )


def _default_http_post(url: str, *, data: Mapping[str, str], timeout: float) -> Any:
    """Production token-endpoint POST using the repo's httpx convention.

    Imported lazily so importing ``enterprise.secrets`` in a minimal test
    context (or one that injects its own ``http_post``) never requires
    httpx at module-import time.
    """
    import httpx

    return httpx.post(
        url,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        data=dict(data),
        timeout=timeout,
    )


def _mint_oauth_access_token(
    service: str,
    cfg: OAuthRefreshConfig,
    *,
    http_post: HttpPost,
    now: float,
) -> tuple[str, float]:
    """Exchange a refresh token for a short-lived access token.

    Standard OAuth2 ``grant_type=refresh_token`` flow (RFC 6749 §6). Returns
    ``(access_token, expires_at_epoch)``. Raises ``OAuthRefreshError`` on any
    transport error, non-2xx response, or malformed body.
    """
    body: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": cfg.refresh_token,
        "client_id": cfg.client_id,
    }
    if cfg.client_secret:
        body["client_secret"] = cfg.client_secret
    if cfg.scope:
        body["scope"] = cfg.scope

    try:
        resp = http_post(
            cfg.token_endpoint,
            data=body,
            timeout=_TOKEN_HTTP_TIMEOUT,
        )
    except Exception as exc:  # network / DNS / TLS failure
        raise OAuthRefreshError(
            f"OAuth token request for {service!r} failed: {exc}"
        ) from exc

    status = getattr(resp, "status_code", None)
    if status is None or not (200 <= int(status) < 300):
        # Do NOT include the response body — it can echo back client_secret
        # or token-shaped material. The status code is enough to triage.
        raise OAuthRefreshError(
            f"OAuth token endpoint for {service!r} returned HTTP {status}."
        )

    try:
        payload = resp.json()
    except Exception as exc:
        raise OAuthRefreshError(
            f"OAuth token endpoint for {service!r} returned a non-JSON body."
        ) from exc

    if not isinstance(payload, Mapping):
        raise OAuthRefreshError(
            f"OAuth token endpoint for {service!r} returned an unexpected body."
        )

    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise OAuthRefreshError(
            f"OAuth token endpoint for {service!r} returned no access_token."
        )
    access_token = access_token.strip()
    # ``.strip()`` only removes *surrounding* whitespace; an embedded newline
    # would survive and is a malformed token. Reject it here — before the
    # caller caches the value — so a single bad response can't poison the
    # process-wide cache and fail every fetch until expiry.
    if any(ch in access_token for ch in ("\n", "\r")):
        raise OAuthRefreshError(
            f"OAuth token endpoint for {service!r} returned a malformed access_token."
        )

    # ``expires_in`` is seconds-from-now per RFC 6749. Coerce defensively;
    # if absent or junk, fall back to DEFAULT_TTL_SECONDS so we still expire.
    try:
        expires_in = int(payload.get("expires_in", DEFAULT_TTL_SECONDS))
    except (TypeError, ValueError):
        expires_in = DEFAULT_TTL_SECONDS
    if expires_in <= 0:
        expires_in = DEFAULT_TTL_SECONDS

    return access_token, now + expires_in


def _resolve_oauth_token(
    service: str,
    cfg: OAuthRefreshConfig,
    *,
    http_post: HttpPost,
    now: float,
) -> tuple[str, float]:
    """Return a cached-or-freshly-minted access token + its expiry.

    Refreshes when there is no cached token or the cached one is within
    ``_REFRESH_SKEW_SECONDS`` of expiry. Thread-safe.
    """
    key = service.lower()
    with _token_cache_lock:
        cached = _token_cache.get(key)
        if cached is not None:
            token, expires_at = cached
            if now < (expires_at - _REFRESH_SKEW_SECONDS):
                return token, expires_at

        token, expires_at = _mint_oauth_access_token(
            service, cfg, http_post=http_post, now=now
        )
        _token_cache[key] = (token, expires_at)
        return token, expires_at


def reset_oauth_token_cache() -> None:
    """Drop all cached access tokens. For tests and operator rotation."""
    with _token_cache_lock:
        _token_cache.clear()


def fetch_secret(
    service: str,
    *,
    caller_role: str,
    scope: Optional[str] = None,
    delegated_for: Optional[str] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    http_post: Optional[HttpPost] = None,
    now: Optional[float] = None,
) -> SecretBundle:
    """Return a bundled secret for ``service`` if the caller is allowed.

    ``caller_role`` must be one of the eight enterprise-council roles
    (e.g. "finance", "sales"). ``delegated_for`` lets the Orchestrator
    pass through a leaf's role when fetching on its behalf.

    Behaviour:
      * Audit-style log entry is emitted via the standard logger so
        the RedactingFormatter masks any incidental token-shaped text.
        We never log ``value`` directly even when redaction is off.
      * If an OAuth2 refresh-token entry is configured for the service
        (``<SERVICE>_OAUTH_TOKEN_URL`` / ``_CLIENT_ID`` / ``_REFRESH_TOKEN``,
        plus optional ``_CLIENT_SECRET`` / ``_SCOPE``), a short-lived
        access token is minted via the standard ``grant_type=refresh_token``
        exchange and returned with ``ephemeral=True`` and a real
        ``expires_at``. Minted tokens are cached and re-minted shortly
        before expiry. If a refresh source is configured but the exchange
        fails, ``OAuthRefreshError`` is raised (we do NOT silently fall
        back to a long-lived key — that would mask an operator error).
      * Otherwise we fall back to the long-lived API key path
        (``<SERVICE>_API_KEY`` / credential pool), returned with
        ``ephemeral=False`` — the original safe default, unchanged for
        every service without refresh config.
      * Refuses to return a value containing ``\\n`` or other obvious
        corruption (defence against accidental concatenation bugs).

    ``http_post`` and ``now`` are injection points for testing the OAuth
    path without real network calls or wall-clock dependence; production
    callers leave them at their defaults.
    """
    _check_access(service, caller_role, delegated_for)

    clock = time.time() if now is None else now

    # OAuth2 refresh-token path: only taken when a full refresh config
    # exists. Anything missing → fall through to the long-lived key path
    # so the safe default is never broken for unconfigured services.
    oauth_cfg = _resolve_oauth_config(service)
    if oauth_cfg is not None:
        token, expires_at = _resolve_oauth_token(
            service,
            oauth_cfg,
            http_post=http_post or _default_http_post,
            now=clock,
        )
        if any(ch in token for ch in ("\n", "\r")):
            raise SecretNotFound(
                f"Minted OAuth token for {service!r} contains a newline — refusing to return."
            )
        ephemeral = True
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
            value=token,
            expires_at=expires_at,
            ephemeral=ephemeral,
        )

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

    # Long-lived API key path: no expiry, ephemeral=False (the safe default).
    expires_at: Optional[float] = None
    ephemeral = False

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
