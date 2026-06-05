"""Shared read-only HTTP helper for the free public-API plugins.

The github-assistant plugin proved the pattern: a thin, synchronous,
session-injectable client that never lets a secret cross its public
surface. Several new plugins (``weather``, ``finance``, ``news``,
``timeutil``) each need the same three properties, so rather than copy
the plumbing four times we centralise it here:

  1. **Bounded.** Every request has a hard ``timeout`` and the response
     body is capped at ``max_bytes`` so a hostile or buggy endpoint can't
     blow up the model context. JSON over the cap is refused; text over
     the cap is truncated.
  2. **Host-pinned.** A non-empty ``allowed_hosts`` allowlist is enforced
     before the socket opens. Combined with each plugin pinning its base
     URL as a constant, a tool cannot be redirected at an arbitrary host
     (SSRF / exfil guard).
  3. **Redacted.** Any configured secret value and common token-shaped
     substrings are stripped from every error message before it can reach
     the model or the logs. This is the first line; the Hermes
     RedactingFormatter is defence in depth.

No exceptions other than :class:`HttpClientError` cross the public
surface, and that exception only ever carries a sanitised message.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence
from urllib.parse import urljoin, urlsplit

import requests

DEFAULT_TIMEOUT_SECONDS = 20.0
# 256 KB — generous for JSON data feeds, small enough to protect context.
DEFAULT_MAX_BYTES = 256 * 1024
DEFAULT_USER_AGENT = "hermes-agent/public-apis"
# Hops we'll follow ourselves (auto-redirects are disabled so we can
# re-check the allowlist on every hop — see _request).
DEFAULT_MAX_REDIRECTS = 5
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})

# Generic secret-shaped patterns. These are intentionally broad — false
# positives only cost a few redacted characters in an error string.
_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|apikey)=\S+"),
    re.compile(r"(?i)authorization:\s*\S+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]


def redact(text: str, secrets: Sequence[str] = ()) -> str:
    """Strip known secret literals and token-shaped substrings from ``text``.

    ``secrets`` is the set of exact values (e.g. a resolved API key) that
    must never appear; we also scrub generic ``key=...`` / ``Bearer ...``
    shapes so an echoed query string or auth header can't leak.
    """
    if not text:
        return ""
    out = text
    for secret in secrets:
        if secret and len(secret) >= 4:
            out = out.replace(secret, "***REDACTED***")
    for pat in _SECRET_PATTERNS:
        out = pat.sub("***REDACTED***", out)
    return out


class HttpClientError(Exception):
    """A bounded, sanitised HTTP failure.

    ``error`` is a short machine code (``timeout``, ``transport``,
    ``http_error``, ``host_not_allowed``, ``response_too_large``,
    ``bad_response``); ``message`` is always run through :func:`redact`.
    """

    def __init__(self, error: str, message: str = "", *, status: Optional[int] = None):
        self.error = error
        self.message = message
        self.status = status
        super().__init__(f"{error}: {message}" if message else error)


class PublicApiClient:
    """Synchronous, redacting, host-allowlisted GET client for public APIs."""

    def __init__(
        self,
        *,
        allowed_hosts: Sequence[str] = (),
        session: Optional[requests.Session] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        secrets: Sequence[str] = (),
        user_agent: str = DEFAULT_USER_AGENT,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
    ) -> None:
        self._allowed_hosts = tuple(h.lower() for h in allowed_hosts)
        self._session = session or requests.Session()
        self._timeout = timeout
        self._max_bytes = max_bytes
        self._max_redirects = max_redirects
        # Keep the secret list private; only used by redact(), never echoed.
        self._secrets = tuple(s for s in secrets if s)
        self._user_agent = user_agent

    # -- public surface ------------------------------------------------------

    def get_json(
        self,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """GET ``url`` and parse JSON. Raises HttpClientError on any failure."""
        resp = self._request("GET", url, params=params, headers=headers)
        content = resp.content or b""
        if len(content) > self._max_bytes:
            raise HttpClientError(
                "response_too_large",
                f"response exceeded {self._max_bytes} bytes",
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise HttpClientError(
                "bad_response", self._clean(f"response was not valid JSON: {exc}")
            ) from exc

    def get_text(
        self,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> str:
        """GET ``url`` and return text, truncated to ``max_bytes``."""
        resp = self._request("GET", url, params=params, headers=headers)
        text = resp.text or ""
        encoded = text.encode("utf-8", "replace")
        if len(encoded) > self._max_bytes:
            text = encoded[: self._max_bytes].decode("utf-8", "ignore")
        return text

    def post_json(
        self,
        url: str,
        *,
        json_body: Any = None,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """POST a JSON body to ``url`` and parse the JSON response.

        Used by read-style query APIs that require POST (e.g. OSV.dev's
        vulnerability query) and the opt-in code sandbox. Inherits every
        guarantee of :meth:`get_json` — host allowlist (re-checked on each
        redirect hop), 256 KB cap, secret redaction, and one retry on a
        transient/5xx failure. Raises HttpClientError on any failure.
        """
        resp = self._request(
            "POST", url, params=params, headers=headers, json_body=json_body
        )
        content = resp.content or b""
        if len(content) > self._max_bytes:
            raise HttpClientError(
                "response_too_large",
                f"response exceeded {self._max_bytes} bytes",
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise HttpClientError(
                "bad_response", self._clean(f"response was not valid JSON: {exc}")
            ) from exc

    # -- plumbing ------------------------------------------------------------

    def _clean(self, text: str) -> str:
        return redact(text, self._secrets)

    def _check_host(self, url: str) -> None:
        if not self._allowed_hosts:
            return
        host = (urlsplit(url).hostname or "").lower()
        if host not in self._allowed_hosts:
            raise HttpClientError(
                "host_not_allowed",
                f"host {host!r} is not in the plugin allowlist",
            )

    def _headers(self, extra: Optional[Mapping[str, str]]) -> dict[str, str]:
        h = {"User-Agent": self._user_agent, "Accept": "application/json"}
        if extra:
            h.update(extra)
        return h

    def _call_with_retry(
        self,
        method: str,
        url: str,
        params: Mapping[str, Any],
        headers: Optional[Mapping[str, str]],
        json_body: Any = None,
    ) -> requests.Response:
        """One network call with a single retry on transient failure.

        Retries exactly once on connect/read timeout, connection error, or a
        5xx status. ``allow_redirects=False`` so the caller can re-check the
        host allowlist on every redirect hop rather than letting ``requests``
        silently follow a 3xx to an off-allowlist host. Returns the response
        (including 3xx/4xx); raises a sanitised HttpClientError only on a
        transport-level failure that survives the retry.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(2):
            try:
                resp = self._session.request(
                    method,
                    url,
                    headers=self._headers(headers),
                    params=dict(params or {}),
                    timeout=self._timeout,
                    allow_redirects=False,
                    json=json_body,
                )
            except requests.Timeout as exc:
                last_exc = exc
                continue
            except requests.RequestException as exc:
                last_exc = exc
                continue
            if resp.status_code >= 500 and attempt == 0:
                # Transient server error — retry once.
                continue
            return resp
        if isinstance(last_exc, requests.Timeout):
            raise HttpClientError("timeout", "request timed out") from last_exc
        raise HttpClientError(
            "transport", self._clean(str(last_exc) if last_exc else "request failed")
        ) from last_exc

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]],
        headers: Optional[Mapping[str, str]],
        json_body: Any = None,
    ) -> requests.Response:
        """Issue a request, following redirects manually with allowlist re-checks.

        Auto-redirects are disabled; we follow up to ``max_redirects`` hops
        ourselves and run :meth:`_check_host` against every hop's target. This
        keeps the host-pinning / SSRF guard intact even when an allowlisted
        host 3xx-redirects elsewhere — and prevents an auth header (e.g.
        NewsAPI's ``X-Api-Key``) from being carried to a foreign host.
        """
        self._check_host(url)
        hop_url = url
        hop_params: Mapping[str, Any] = dict(params or {})
        for _hop in range(self._max_redirects + 1):
            resp = self._call_with_retry(
                method, hop_url, hop_params, headers, json_body
            )
            status = resp.status_code
            if status in _REDIRECT_CODES:
                location = resp.headers.get("Location")
                if location:
                    # Resolve relative redirects against the current URL, then
                    # re-validate the new host before following it. Drop our
                    # query params — the redirect target is fully formed.
                    hop_url = urljoin(hop_url, location)
                    self._check_host(hop_url)
                    hop_params = {}
                    continue
            if status is not None and status >= 400:
                body = ""
                try:
                    body = self._clean((resp.text or "")[:300])
                except Exception:
                    body = ""
                raise HttpClientError(
                    "http_error",
                    f"{urlsplit(hop_url).hostname} returned {status}: {body}",
                    status=status,
                )
            return resp
        raise HttpClientError(
            "too_many_redirects",
            f"exceeded {self._max_redirects} redirects",
        )
