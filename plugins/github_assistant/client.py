"""Thin GitHub REST API client used by the github-assistant tools.

Three safety properties this module is responsible for:

  1. **Token never leaves the process.** The token lives in
     ``GithubClient._token`` and is only ever passed as the
     ``Authorization`` request header. We never put it in a returned
     payload, never include it in an error string, and never log it.
  2. **Errors are sanitized.** GitHub error responses can echo the
     ``Authorization`` header back when a request is malformed, and
     transport errors from ``requests`` can include the full URL with
     a query string. ``sanitize_error`` strips known token shapes and
     ``Authorization:`` lines.
  3. **Bounded.** Every call has a hard ``timeout``. Pagination is
     capped — we don't follow the ``Link: next`` chain unboundedly.

Resilience-by-design: every public method returns a dict with a
``success`` boolean. Callers (tools.py) JSON-encode the dict for the
agent. No exceptions cross the public surface.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Mapping, Optional

import requests

logger = logging.getLogger("github_assistant.client")

# Endpoint base — pinned so a misconfigured proxy can't redirect us to
# attacker-controlled HTTPS.
GITHUB_API_ROOT = "https://api.github.com"

# Cap on results we return per list call. The agent rarely needs more
# than this; bigger payloads waste tokens and surface PII unnecessarily.
DEFAULT_LIST_CAP = 50
HARD_LIST_CAP = 250

DEFAULT_TIMEOUT_SECONDS = 30.0

# Known GitHub token prefixes; used by sanitize_error.
_TOKEN_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{10,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{10,}"),
    re.compile(r"gho_[A-Za-z0-9]{10,}"),
    re.compile(r"ghu_[A-Za-z0-9]{10,}"),
    re.compile(r"ghs_[A-Za-z0-9]{10,}"),
    re.compile(r"ghr_[A-Za-z0-9]{10,}"),
]
_AUTH_LINE = re.compile(r"(?i)authorization:\s*\S+")


def sanitize_error(text: str) -> str:
    """Strip token-shaped strings and any echoed Authorization header.

    Cheap and conservative — runs on any error message before we return
    it to the agent or log it. The Hermes RedactingFormatter is the
    defence in depth; this is the first line.
    """
    if not text:
        return ""
    out = text
    for pat in _TOKEN_PATTERNS:
        out = pat.sub("ghp_***REDACTED***", out)
    out = _AUTH_LINE.sub("Authorization: ***REDACTED***", out)
    return out


def _resolve_token(explicit: Optional[str] = None) -> Optional[str]:
    """Return the GitHub PAT from explicit arg, env, or None.

    We do NOT fall through to credential pool entries — the GitHub PAT
    is not an LLM provider key and lives in a different trust domain.
    Operators set it in ``~/.hermes/.env``.
    """
    if explicit and explicit.strip():
        return explicit.strip()
    val = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    if val and val.strip():
        return val.strip()
    return None


class GithubClient:
    """Synchronous GitHub REST client used by github-assistant tools."""

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        session: Optional[requests.Session] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        api_root: str = GITHUB_API_ROOT,
    ) -> None:
        self._token = _resolve_token(token)
        self._session = session or requests.Session()
        self._timeout = timeout
        self._api_root = api_root.rstrip("/")

    # -- introspection -------------------------------------------------------

    def has_token(self) -> bool:
        return bool(self._token)

    # -- HTTP plumbing -------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "hermes-agent/github-assistant",
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
        """Issue one request and return a uniform-shape result dict."""
        if not self._token:
            return {
                "success": False,
                "error": "no_token",
                "message": (
                    "GITHUB_PERSONAL_ACCESS_TOKEN is not configured. "
                    "Set it in ~/.hermes/.env."
                ),
            }
        url = f"{self._api_root}{path}"
        try:
            resp = self._session.request(
                method,
                url,
                headers=self._headers(),
                params=dict(params or {}),
                json=dict(json_body) if json_body is not None else None,
                timeout=self._timeout,
            )
        except requests.Timeout:
            return {
                "success": False,
                "error": "timeout",
                "message": "GitHub API timed out",
            }
        except requests.RequestException as exc:
            return {
                "success": False,
                "error": "transport",
                "message": sanitize_error(str(exc)),
            }

        # We deliberately do not log the response body — it can echo
        # request headers including Authorization. If logging is needed
        # for debugging, route it through agent.redact.
        status = resp.status_code
        if status >= 400:
            body_excerpt = ""
            try:
                body_excerpt = sanitize_error(resp.text[:500])
            except Exception:
                body_excerpt = ""
            return {
                "success": False,
                "error": "http_error",
                "status": status,
                "message": f"GitHub returned {status}: {body_excerpt}",
            }

        try:
            payload = resp.json() if resp.text else None
        except ValueError:
            payload = None
        return {"success": True, "status": status, "payload": payload}

    # -- public surface ------------------------------------------------------

    def repo(self, owner: str, name: str) -> dict[str, Any]:
        return self._request("GET", f"/repos/{owner}/{name}")

    def file_contents(
        self, owner: str, name: str, path: str, ref: Optional[str] = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if ref:
            params["ref"] = ref
        return self._request(
            "GET", f"/repos/{owner}/{name}/contents/{path.lstrip('/')}", params=params
        )

    def branches(self, owner: str, name: str, limit: int) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/repos/{owner}/{name}/branches",
            params={"per_page": max(1, min(limit, HARD_LIST_CAP))},
        )

    def issues(self, owner: str, name: str, state: str, limit: int) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/repos/{owner}/{name}/issues",
            params={
                "state": state,
                "per_page": max(1, min(limit, HARD_LIST_CAP)),
                # GitHub returns pull-requests inside the /issues endpoint;
                # filter them out with the documented `pulls=false`
                # query parameter would be ideal, but GitHub doesn't
                # support it. Callers strip PR entries in tools.py.
            },
        )

    def create_issue(
        self,
        owner: str,
        name: str,
        title: str,
        body: Optional[str] = None,
        labels: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"title": title}
        if body is not None:
            payload["body"] = body
        if labels:
            payload["labels"] = list(labels)
        return self._request("POST", f"/repos/{owner}/{name}/issues", json_body=payload)

    def pull_requests(
        self, owner: str, name: str, state: str, limit: int
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/repos/{owner}/{name}/pulls",
            params={"state": state, "per_page": max(1, min(limit, HARD_LIST_CAP))},
        )

    def pull_request(self, owner: str, name: str, number: int) -> dict[str, Any]:
        return self._request("GET", f"/repos/{owner}/{name}/pulls/{number}")

    def comment_on_issue(
        self, owner: str, name: str, number: int, body: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/repos/{owner}/{name}/issues/{number}/comments",
            json_body={"body": body},
        )

    def create_pull_request(
        self,
        owner: str,
        name: str,
        *,
        title: str,
        head: str,
        base: str,
        body: Optional[str] = None,
        draft: bool = True,
    ) -> dict[str, Any]:
        """Open a PR (``head`` → ``base``). Requires a configured PAT."""
        payload: dict[str, Any] = {
            "title": title,
            "head": head,
            "base": base,
            "draft": bool(draft),
        }
        if body is not None:
            payload["body"] = body
        return self._request("POST", f"/repos/{owner}/{name}/pulls", json_body=payload)

    def open_pull_for_head(self, owner: str, name: str, branch: str) -> Optional[str]:
        """Return the ``html_url`` of an OPEN PR whose head is ``branch``, else None."""
        result = self._request(
            "GET",
            f"/repos/{owner}/{name}/pulls",
            params={"state": "open", "head": f"{owner}:{branch}"},
        )
        if not result.get("success"):
            return None
        items = result.get("payload") or []
        if isinstance(items, list) and items:
            return items[0].get("html_url")
        return None
