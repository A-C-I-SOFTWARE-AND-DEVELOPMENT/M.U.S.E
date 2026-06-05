"""Minimal Supabase PostgREST client for the supabase plugin.

Thin wrapper over a project's PostgREST endpoint (``{SUPABASE_URL}/rest/v1``)
built on ``httpx`` (a Hermes base dependency). Mirrors the safety rules of
``plugins/github_assistant/client.py``:

  * Keys are read from ``os.environ`` and only placed in the ``apikey`` /
    ``Authorization`` headers — never logged, never returned, never in an
    error string (``sanitize_error`` scrubs key-shaped substrings).
  * Read queries use the **anon** key by default. The **service-role** key
    (which bypasses row-level security) is only used when the caller opts in
    *and* the plugin config allows it.
  * Every public method returns ``{"success": bool, ...}`` and never raises.

The ``httpx.Client`` is injectable so tests can supply an
``httpx.MockTransport``.
"""

from __future__ import annotations

import os
import re
from typing import Any, Mapping, Optional

import httpx

DEFAULT_TIMEOUT = 30.0
DEFAULT_ROW_CAP = 50
HARD_ROW_CAP = 1000

# Supabase keys are JWTs (three base64url segments). Scrub them and any
# leaked apikey/Authorization header from returned text.
_KEY_PATTERNS = (
    re.compile(r"(?i)(apikey|authorization):\s*\S+"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
)


def sanitize_error(text: str) -> str:
    """Strip apikey/Authorization headers and JWT-shaped keys from a string."""
    if not text:
        return ""
    out = str(text)
    for pat in _KEY_PATTERNS:
        out = pat.sub("***REDACTED***", out)
    return out


class SupabaseClient:
    """Bounded, key-safe Supabase PostgREST client."""

    def __init__(
        self,
        url: Optional[str] = None,
        anon_key: Optional[str] = None,
        service_role_key: Optional[str] = None,
        *,
        http_client: Optional[httpx.Client] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._url = (
            url if url is not None else os.environ.get("SUPABASE_URL") or ""
        ).rstrip("/")
        self._anon = (
            anon_key if anon_key is not None else os.environ.get("SUPABASE_ANON_KEY")
        )
        self._service = (
            service_role_key
            if service_role_key is not None
            else os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        )
        self._client = http_client
        self._timeout = timeout

    def has_config(self) -> bool:
        return bool(self._url and self._anon)

    def has_service_role(self) -> bool:
        return bool(self._service)

    # -- internals ---------------------------------------------------------

    def _key(self, *, service_role: bool) -> Optional[str]:
        return self._service if service_role else self._anon

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        service_role: bool = False,
    ) -> dict[str, Any]:
        if not self.has_config():
            return {
                "success": False,
                "error": "not_configured",
                "message": "SUPABASE_URL and SUPABASE_ANON_KEY must be set in ~/.hermes/.env.",
            }
        key = self._key(service_role=service_role)
        if not key:
            return {
                "success": False,
                "error": "no_key",
                "message": "Requested key is not configured.",
            }
        url = f"{self._url}/rest/v1{path}"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "hermes-agent/supabase-plugin",
        }
        client = self._client or httpx.Client(timeout=self._timeout)
        owns_client = self._client is None
        try:
            resp = client.request(
                method, url, headers=headers, params=dict(params or {})
            )
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "timeout",
                "message": "Supabase API timed out",
            }
        except httpx.HTTPError as exc:
            return {
                "success": False,
                "error": "transport",
                "message": sanitize_error(str(exc)),
            }
        finally:
            if owns_client:
                client.close()

        if resp.status_code >= 400:
            try:
                excerpt = sanitize_error(resp.text[:500])
            except Exception:
                excerpt = ""
            return {
                "success": False,
                "error": "http_error",
                "status": resp.status_code,
                "message": f"Supabase API returned {resp.status_code}: {excerpt}",
            }
        try:
            payload = resp.json() if resp.text else None
        except ValueError:
            payload = None
        return {"success": True, "status": resp.status_code, "payload": payload}

    # -- read --------------------------------------------------------------

    def query(
        self,
        table: str,
        *,
        select: str = "*",
        limit: int = DEFAULT_ROW_CAP,
        service_role: bool = False,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), HARD_ROW_CAP))
        return self._request(
            "GET",
            f"/{table}",
            params={"select": select or "*", "limit": limit},
            service_role=service_role,
        )

    def list_tables(self) -> dict[str, Any]:
        """Fetch the PostgREST root (OpenAPI) and extract table names."""
        res = self._request("GET", "/")
        if not res.get("success"):
            return res
        spec = res.get("payload") or {}
        tables: list[str] = []
        if isinstance(spec, dict):
            defs = spec.get("definitions")
            if isinstance(defs, dict):
                tables = [k for k in defs.keys() if isinstance(k, str)]
            elif isinstance(spec.get("paths"), dict):
                tables = [
                    p.lstrip("/")
                    for p in spec["paths"].keys()
                    if isinstance(p, str)
                    and p.startswith("/")
                    and "{" not in p
                    and p != "/"
                ]
        return {"success": True, "tables": sorted(set(tables))}
