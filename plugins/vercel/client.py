"""Minimal Vercel REST client for the vercel plugin.

Thin wrapper over the Vercel REST API (https://api.vercel.com) built on
``httpx`` (a Hermes base dependency — no lazy install needed). Design rules
mirror ``plugins/github_assistant/client.py``:

  * The ``VERCEL_TOKEN`` is read from ``os.environ`` and is only ever placed
    in the ``Authorization`` header — never logged, never returned, never put
    in an error string (``sanitize_error`` scrubs token-shaped substrings).
  * Every public method returns a uniform ``{"success": bool, ...}`` dict and
    never raises across its surface.
  * All calls are bounded by a hard timeout.

The underlying ``httpx.Client`` is injectable so tests can supply an
``httpx.MockTransport`` and assert behaviour without touching the network.
"""

from __future__ import annotations

import os
import re
from typing import Any, Mapping, Optional

import httpx

API_ROOT = "https://api.vercel.com"
DEFAULT_TIMEOUT = 30.0
DEFAULT_LIST_CAP = 20
HARD_LIST_CAP = 100

# Token shapes to scrub from any text we might return or log. Vercel tokens
# are opaque ~24+ char strings; we also catch a leaked Bearer header.
_TOKEN_PATTERNS = (
    re.compile(r"(?i)authorization:\s*bearer\s+\S+"),
    re.compile(r"\bBearer\s+[A-Za-z0-9_-]{16,}\b"),
)


def sanitize_error(text: str) -> str:
    """Strip Authorization headers / Bearer tokens from a string."""
    if not text:
        return ""
    out = str(text)
    for pat in _TOKEN_PATTERNS:
        out = pat.sub("Authorization: ***REDACTED***", out)
    return out


class VercelClient:
    """Bounded, token-safe Vercel REST client."""

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        http_client: Optional[httpx.Client] = None,
        timeout: float = DEFAULT_TIMEOUT,
        api_root: str = API_ROOT,
    ) -> None:
        self._token = token if token is not None else os.environ.get("VERCEL_TOKEN")
        self._client = http_client
        self._timeout = timeout
        self._api_root = api_root.rstrip("/")

    def has_token(self) -> bool:
        return bool(self._token and self._token.strip())

    # -- internals ---------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h = {
            "Accept": "application/json",
            "User-Agent": "hermes-agent/vercel-plugin",
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
        json_body: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        if not self.has_token():
            return {
                "success": False,
                "error": "no_token",
                "message": "VERCEL_TOKEN is not configured. Set it in ~/.hermes/.env.",
            }
        url = path if path.startswith("http") else f"{self._api_root}{path}"
        client = self._client or httpx.Client(timeout=self._timeout)
        owns_client = self._client is None
        try:
            resp = client.request(
                method,
                url,
                headers=self._headers(),
                params=dict(params or {}),
                json=dict(json_body) if json_body is not None else None,
            )
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "timeout",
                "message": "Vercel API timed out",
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
                "message": f"Vercel API returned {resp.status_code}: {excerpt}",
            }
        try:
            payload = resp.json() if resp.text else None
        except ValueError:
            payload = None
        return {"success": True, "status": resp.status_code, "payload": payload}

    # -- read --------------------------------------------------------------

    def list_projects(self, *, limit: int = DEFAULT_LIST_CAP) -> dict[str, Any]:
        limit = max(1, min(int(limit), HARD_LIST_CAP))
        return self._request("GET", "/v9/projects", params={"limit": limit})

    def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v13/deployments/{deployment_id}")

    def list_deployments(
        self, *, project_id: str, limit: int = 1, target: Optional[str] = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "projectId": project_id,
            "limit": max(1, min(int(limit), HARD_LIST_CAP)),
        }
        if target:
            params["target"] = target
        return self._request("GET", "/v6/deployments", params=params)

    def get_deployment_events(
        self, deployment_id: str, *, limit: int = DEFAULT_LIST_CAP
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/v2/deployments/{deployment_id}/events",
            params={"limit": max(1, min(int(limit), HARD_LIST_CAP))},
        )

    # -- write (callers must gate via the decision engine first) -----------

    def create_env(
        self,
        *,
        project_id: str,
        key: str,
        value: str,
        target: list[str],
        type_: str = "encrypted",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v10/projects/{project_id}/env",
            json_body={"key": key, "value": value, "type": type_, "target": target},
        )

    def cancel_deployment(self, deployment_id: str) -> dict[str, Any]:
        return self._request("PATCH", f"/v12/deployments/{deployment_id}/cancel")

    def trigger_deploy_hook(self, hook_url: str) -> dict[str, Any]:
        # Deploy hooks are pre-authorized POST URLs scoped to one project/branch.
        return self._request("POST", hook_url)
