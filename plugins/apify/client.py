"""Thin Apify REST API client used by the apify tools.

Three safety properties this module is responsible for (the same three
github_assistant guarantees, applied to Apify):

  1. **Token never leaves the process.** The token lives in
     ``ApifyClient._token`` and is only ever sent as the ``Authorization``
     request header. It is never put in a returned payload, an error
     string, a query string, or a log line.
  2. **Errors are sanitized.** ``sanitize_error`` strips Apify token shapes
     (``apify_api_…``) and any echoed ``Authorization:`` header before an
     error reaches the model or the logs.
  3. **Bounded.** Every call has a hard ``timeout`` (longer for run-sync,
     which blocks until the Actor finishes) and list/result sizes are
     capped by the caller via the ``limit`` query parameter.

The endpoint host is pinned to ``api.apify.com`` so a misconfigured proxy
can't redirect us elsewhere. Every public method returns a dict with a
``success`` boolean; no exceptions cross the public surface.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Mapping, Optional

import requests

logger = logging.getLogger("apify.client")

# Endpoint base — pinned.
APIFY_API_ROOT = "https://api.apify.com/v2"

# Cap on results we return per list call. Bigger payloads waste tokens.
DEFAULT_LIST_CAP = 25
HARD_LIST_CAP = 100

# Read calls (list/get) are quick; a run-sync call blocks until the Actor
# finishes, so it gets a much longer ceiling (still bounded).
DEFAULT_TIMEOUT_SECONDS = 30.0
RUN_SYNC_TIMEOUT_SECONDS = 305.0  # just over Apify's 300s run-sync server cap

# Apify personal API tokens look like ``apify_api_<48 alphanumerics>``.
_TOKEN_PATTERNS = [
    re.compile(r"apify_api_[A-Za-z0-9]{10,}"),
]
_AUTH_LINE = re.compile(r"(?i)authorization:\s*\S+")


def sanitize_error(text: str, *, secrets: tuple[str, ...] = ()) -> str:
    """Strip token-shaped strings, secret literals, and Authorization lines."""
    if not text:
        return ""
    out = text
    for secret in secrets:
        if secret and len(secret) >= 4:
            out = out.replace(secret, "***REDACTED***")
    for pat in _TOKEN_PATTERNS:
        out = pat.sub("apify_api_***REDACTED***", out)
    out = _AUTH_LINE.sub("Authorization: ***REDACTED***", out)
    return out


def _resolve_token(explicit: Optional[str] = None) -> Optional[str]:
    """Return the Apify token from explicit arg, env (``APIFY_TOKEN``), or None."""
    if explicit and explicit.strip():
        return explicit.strip()
    val = os.environ.get("APIFY_TOKEN")
    if val and val.strip():
        return val.strip()
    return None


class ApifyClient:
    """Synchronous Apify REST client used by the apify tools."""

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        session: Optional[requests.Session] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        api_root: str = APIFY_API_ROOT,
    ) -> None:
        self._token = _resolve_token(token)
        self._session = session or requests.Session()
        self._timeout = timeout
        self._api_root = api_root.rstrip("/")

    # -- introspection -------------------------------------------------------

    def has_token(self) -> bool:
        return bool(self._token)

    def _secrets(self) -> tuple[str, ...]:
        return (self._token,) if self._token else ()

    # -- HTTP plumbing -------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h = {
            "Accept": "application/json",
            "User-Agent": "hermes-agent/apify",
        }
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Any = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Issue one request and return a uniform-shape result dict."""
        if not self._token:
            return {
                "success": False,
                "error": "no_token",
                "message": (
                    "APIFY_TOKEN is not configured. Set it in ~/.hermes/.env."
                ),
            }
        url = f"{self._api_root}{path}"
        try:
            resp = self._session.request(
                method,
                url,
                headers=self._headers(),
                params=dict(params or {}),
                json=json_body if json_body is not None else None,
                timeout=timeout if timeout is not None else self._timeout,
            )
        except requests.Timeout:
            return {
                "success": False,
                "error": "timeout",
                "message": "Apify API timed out",
            }
        except requests.RequestException as exc:
            return {
                "success": False,
                "error": "transport",
                "message": sanitize_error(str(exc), secrets=self._secrets()),
            }

        status = resp.status_code
        if status >= 400:
            body_excerpt = ""
            try:
                body_excerpt = sanitize_error(
                    resp.text[:500], secrets=self._secrets()
                )
            except Exception:
                body_excerpt = ""
            return {
                "success": False,
                "error": "http_error",
                "status": status,
                "message": f"Apify returned {status}: {body_excerpt}",
            }

        try:
            payload = resp.json() if resp.text else None
        except ValueError:
            payload = None
        return {"success": True, "status": status, "payload": payload}

    # -- public surface ------------------------------------------------------

    def list_actors(self, *, limit: int, offset: int = 0) -> dict[str, Any]:
        """List the authenticated user's own Actors (newest first)."""
        return self._request(
            "GET",
            "/acts",
            params={
                "limit": max(1, min(limit, HARD_LIST_CAP)),
                "offset": max(0, offset),
                "desc": "true",
            },
        )

    def search_store(self, *, search: str, limit: int) -> dict[str, Any]:
        """Search the public Apify Store for Actors matching ``search``."""
        return self._request(
            "GET",
            "/store",
            params={
                "search": search,
                "limit": max(1, min(limit, HARD_LIST_CAP)),
            },
        )

    def dataset_items(
        self, dataset_id: str, *, limit: int, offset: int = 0, clean: bool = True
    ) -> dict[str, Any]:
        """Fetch items from a dataset (e.g. the output of a previous run)."""
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/items",
            params={
                "limit": max(1, min(limit, HARD_LIST_CAP)),
                "offset": max(0, offset),
                "clean": "true" if clean else "false",
                "format": "json",
            },
        )

    def run(self, run_id: str) -> dict[str, Any]:
        """Get the status/metadata of an Actor run by id."""
        return self._request("GET", f"/actor-runs/{run_id}")

    def run_actor_sync(
        self,
        actor_id: str,
        *,
        run_input: Optional[Mapping[str, Any]] = None,
        limit: int,
        timeout_secs: int,
        memory_mbytes: Optional[int] = None,
    ) -> dict[str, Any]:
        """Run an Actor and block until it finishes, returning dataset items.

        Uses Apify's ``run-sync-get-dataset-items`` endpoint. ``timeout_secs``
        is forwarded as the Actor run timeout; we also give the HTTP call a
        slightly longer client-side ceiling so the network read doesn't trip
        before the run's own timeout does.
        """
        params: dict[str, Any] = {
            "limit": max(1, min(limit, HARD_LIST_CAP)),
            "timeout": max(1, timeout_secs),
            "clean": "true",
            "format": "json",
        }
        if memory_mbytes is not None:
            params["memory"] = memory_mbytes
        return self._request(
            "POST",
            f"/acts/{actor_id}/run-sync-get-dataset-items",
            params=params,
            json_body=dict(run_input or {}),
            timeout=min(RUN_SYNC_TIMEOUT_SECONDS, max(1, timeout_secs) + 5.0),
        )
