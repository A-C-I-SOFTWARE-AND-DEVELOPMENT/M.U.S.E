"""Eight agent-facing GitHub tools registered by the github-assistant plugin.

Each tool returns a JSON string with the same envelope:

    {"success": bool, ...payload}

Failure cases (no token, writes disabled, repo not allowed, malformed
input, network error, HTTP error from GitHub) all share the same shape
so the agent's structured-output parsing is uniform.

The tool layer is also where two safety gates live:

  * `_check_repo_allowed`  — applies `github.allowed_repositories`.
  * `_writes_enabled`      — reads `github.allow_writes` for each call,
                             so the operator can flip the gate without
                             restarting the agent.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from plugins.github_assistant import config as github_config
from plugins.github_assistant.client import (
    DEFAULT_LIST_CAP,
    HARD_LIST_CAP,
    GithubClient,
)

logger = logging.getLogger("github_assistant.tools")


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------


def _json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _err(error: str, message: str = "", **extra: Any) -> str:
    body: Dict[str, Any] = {"success": False, "error": error}
    if message:
        body["message"] = message
    body.update(extra)
    return _json(body)


def _ok(**payload: Any) -> str:
    return _json({"success": True, **payload})


# ---------------------------------------------------------------------------
# Runtime gate (check_fn for the registry)
# ---------------------------------------------------------------------------


def check_github_requirements() -> bool:
    """Return True when the plugin can usefully be offered to the model.

    Two conditions:
      * ``github.enabled`` is True.
      * A PAT is configured (env var present).

    When either is False we return False; the registry then hides the
    tools from the model rather than dangling broken handlers.
    """
    cfg = github_config.load_config()
    if not cfg.enabled:
        return False
    client = GithubClient()
    return client.has_token()


# ---------------------------------------------------------------------------
# Validation helpers used by every handler
# ---------------------------------------------------------------------------
#
# Each helper raises ``_GateFailure`` carrying a ready-to-return JSON
# error envelope. Handlers catch it once at the top and return the
# payload — keeps every handler short and lets the type checker narrow
# owner/name/client to non-Optional after a successful gate run.


class _GateFailure(Exception):
    """A handler-level input or policy failure with the JSON to return."""

    def __init__(self, payload_json: str) -> None:
        self.payload_json = payload_json
        super().__init__(payload_json)


def _validate_repo(args: Dict[str, Any]) -> tuple[str, str]:
    """Return (owner, name) or raise _GateFailure with a bad_args error."""
    owner = args.get("owner")
    name = args.get("name") or args.get("repo")
    if not isinstance(owner, str) or not isinstance(name, str):
        raise _GateFailure(_err("bad_args", "owner and name must be strings"))
    try:
        github_config.validate_owner_name(owner, name)
    except github_config.ConfigError as exc:
        raise _GateFailure(_err("bad_args", str(exc))) from exc
    return owner, name


def _check_repo_allowed(cfg: github_config.GithubConfig, owner: str, name: str) -> None:
    if not cfg.is_repo_allowed(owner, name):
        raise _GateFailure(
            _err(
                "repo_not_allowed",
                f"{owner}/{name} is not in github.allowed_repositories",
            )
        )


def _check_writes_enabled(cfg: github_config.GithubConfig) -> None:
    if not cfg.allow_writes:
        raise _GateFailure(
            _err(
                "writes_disabled",
                "github.allow_writes is false; refusing to mutate the repo. "
                "Set github.allow_writes: true in ~/.hermes/config.yaml to enable.",
            )
        )


def _require_client() -> GithubClient:
    """Return a GithubClient with a token, or raise _GateFailure."""
    client = GithubClient()
    if not client.has_token():
        raise _GateFailure(
            _err(
                "no_token",
                "GITHUB_PERSONAL_ACCESS_TOKEN is not configured. "
                "Set it in ~/.hermes/.env.",
            )
        )
    return client


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_OWNER_PROP = {
    "type": "string",
    "description": "Repository owner (user or org login), e.g. 'echerd27-design'.",
}
_NAME_PROP = {
    "type": "string",
    "description": "Repository name, e.g. 'hermes-agent'.",
}


AUDIT_REPO_SCHEMA: Dict[str, Any] = {
    "name": "github_audit_repo",
    "description": (
        "Return high-level metadata about a GitHub repository: description, "
        "primary language, star/fork/issue counts, default branch, license, "
        "and topics. Read-only. Useful as the first call before any deeper "
        "GitHub work — the rest of the tools all take owner/name from this."
    ),
    "parameters": {
        "type": "object",
        "properties": {"owner": _OWNER_PROP, "name": _NAME_PROP},
        "required": ["owner", "name"],
        "additionalProperties": False,
    },
}

GET_REPO_FILE_SCHEMA: Dict[str, Any] = {
    "name": "github_get_repo_file",
    "description": (
        "Fetch a single file from a GitHub repository by path. Returns the "
        "decoded text content plus the sha, size, and html_url. Path is "
        "relative to the repo root (e.g. 'README.md', 'src/main.py'). Use "
        "ref to pin a branch/tag/commit; omit for the default branch."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "owner": _OWNER_PROP,
            "name": _NAME_PROP,
            "path": {"type": "string", "description": "File path inside the repo."},
            "ref": {
                "type": "string",
                "description": "Optional branch, tag, or commit SHA. Defaults to the repo default branch.",
            },
        },
        "required": ["owner", "name", "path"],
        "additionalProperties": False,
    },
}

LIST_BRANCHES_SCHEMA: Dict[str, Any] = {
    "name": "github_list_branches",
    "description": (
        "List branches in a repository, newest-first as GitHub returns them. "
        "Capped to limit (default 50, max 250)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "owner": _OWNER_PROP,
            "name": _NAME_PROP,
            "limit": {"type": "integer", "minimum": 1, "maximum": HARD_LIST_CAP},
        },
        "required": ["owner", "name"],
        "additionalProperties": False,
    },
}

LIST_ISSUES_SCHEMA: Dict[str, Any] = {
    "name": "github_list_issues",
    "description": (
        "List issues in a repository. By default returns open issues; "
        "set state to 'closed' or 'all'. Excludes PRs (the underlying "
        "endpoint mixes both — they are filtered out here)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "owner": _OWNER_PROP,
            "name": _NAME_PROP,
            "state": {"type": "string", "enum": ["open", "closed", "all"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": HARD_LIST_CAP},
        },
        "required": ["owner", "name"],
        "additionalProperties": False,
    },
}

CREATE_ISSUE_SCHEMA: Dict[str, Any] = {
    "name": "github_create_issue",
    "description": (
        "Open a new GitHub issue. WRITE ACTION — refused unless "
        "github.allow_writes is true in ~/.hermes/config.yaml. Body is "
        "optional but recommended. Labels are optional; unknown labels "
        "are rejected by GitHub, not silently dropped."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "owner": _OWNER_PROP,
            "name": _NAME_PROP,
            "title": {"type": "string", "description": "Issue title."},
            "body": {"type": "string", "description": "Markdown body for the issue."},
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional label names that already exist in the repo.",
            },
        },
        "required": ["owner", "name", "title"],
        "additionalProperties": False,
    },
}

LIST_PULL_REQUESTS_SCHEMA: Dict[str, Any] = {
    "name": "github_list_pull_requests",
    "description": (
        "List pull requests in a repository. Defaults to open PRs; state "
        "can be 'closed' or 'all'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "owner": _OWNER_PROP,
            "name": _NAME_PROP,
            "state": {"type": "string", "enum": ["open", "closed", "all"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": HARD_LIST_CAP},
        },
        "required": ["owner", "name"],
        "additionalProperties": False,
    },
}

GET_PULL_REQUEST_SCHEMA: Dict[str, Any] = {
    "name": "github_get_pull_request",
    "description": (
        "Return one pull request with its head/base refs, mergeability, "
        "review state, labels, and last commit sha. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "owner": _OWNER_PROP,
            "name": _NAME_PROP,
            "number": {"type": "integer", "description": "PR number."},
        },
        "required": ["owner", "name", "number"],
        "additionalProperties": False,
    },
}

COMMENT_SCHEMA: Dict[str, Any] = {
    "name": "github_comment_on_issue_or_pr",
    "description": (
        "Post a comment on an existing issue or pull request (GitHub "
        "stores PRs as issues under the hood, so the same endpoint "
        "handles both). WRITE ACTION — refused unless "
        "github.allow_writes is true in ~/.hermes/config.yaml."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "owner": _OWNER_PROP,
            "name": _NAME_PROP,
            "number": {"type": "integer", "description": "Issue or PR number."},
            "body": {"type": "string", "description": "Markdown comment body."},
        },
        "required": ["owner", "name", "number", "body"],
        "additionalProperties": False,
    },
}


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

# We slim the GitHub payloads before returning to the agent: most of
# their fields are heavy URLs and timestamps that waste tokens. The
# helpers below pick the fields agents actually need.


def _slim_repo(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "full_name": payload.get("full_name"),
        "description": payload.get("description"),
        "default_branch": payload.get("default_branch"),
        "language": payload.get("language"),
        "topics": payload.get("topics", []),
        "private": payload.get("private"),
        "fork": payload.get("fork"),
        "archived": payload.get("archived"),
        "stargazers_count": payload.get("stargazers_count"),
        "forks_count": payload.get("forks_count"),
        "open_issues_count": payload.get("open_issues_count"),
        "license": (payload.get("license") or {}).get("spdx_id"),
        "html_url": payload.get("html_url"),
    }


def _slim_branch(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": payload.get("name"),
        "sha": (payload.get("commit") or {}).get("sha"),
        "protected": payload.get("protected"),
    }


def _slim_issue(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "number": payload.get("number"),
        "title": payload.get("title"),
        "state": payload.get("state"),
        "labels": [
            lbl.get("name")
            for lbl in payload.get("labels", [])
            if isinstance(lbl, dict)
        ],
        "user": (payload.get("user") or {}).get("login"),
        "comments": payload.get("comments"),
        "created_at": payload.get("created_at"),
        "html_url": payload.get("html_url"),
    }


def _slim_pull(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "number": payload.get("number"),
        "title": payload.get("title"),
        "state": payload.get("state"),
        "draft": payload.get("draft"),
        "user": (payload.get("user") or {}).get("login"),
        "head": (payload.get("head") or {}).get("ref"),
        "base": (payload.get("base") or {}).get("ref"),
        "merged": payload.get("merged"),
        "mergeable": payload.get("mergeable"),
        "mergeable_state": payload.get("mergeable_state"),
        "labels": [
            lbl.get("name")
            for lbl in payload.get("labels", [])
            if isinstance(lbl, dict)
        ],
        "html_url": payload.get("html_url"),
    }


def _decode_file_content(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Decode a single-file `/contents` response. Refuse directories/binaries."""
    import base64

    if isinstance(payload, list):
        return {
            "kind": "directory",
            "entries": [
                {"name": p.get("name"), "type": p.get("type"), "size": p.get("size")}
                for p in payload[:HARD_LIST_CAP]
                if isinstance(p, dict)
            ],
        }
    encoding = payload.get("encoding")
    content_b64 = payload.get("content") or ""
    decoded: str | None = None
    if encoding == "base64" and content_b64:
        try:
            raw = base64.b64decode(content_b64.replace("\n", ""))
            try:
                decoded = raw.decode("utf-8")
            except UnicodeDecodeError:
                decoded = None
        except Exception:
            decoded = None
    return {
        "kind": "file",
        "path": payload.get("path"),
        "sha": payload.get("sha"),
        "size": payload.get("size"),
        "html_url": payload.get("html_url"),
        "encoding": encoding,
        "content_utf8": decoded,
        "content_binary": decoded is None and bool(content_b64),
    }


# Per-handler signature is `(args: Dict[str, Any], **_kw) -> str` to
# match the rest of the Hermes tool ecosystem.


def handle_audit_repo(args: Dict[str, Any], **_kw) -> str:
    cfg = github_config.load_config()
    if not cfg.enabled:
        return _err("plugin_disabled", "github.enabled is false")
    try:
        owner, name = _validate_repo(args)
        _check_repo_allowed(cfg, owner, name)
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    res = client.repo(owner, name)
    if not res.get("success"):
        return _json(res)
    return _ok(repo=_slim_repo(res["payload"] or {}))


def handle_get_repo_file(args: Dict[str, Any], **_kw) -> str:
    cfg = github_config.load_config()
    if not cfg.enabled:
        return _err("plugin_disabled", "github.enabled is false")
    try:
        owner, name = _validate_repo(args)
        _check_repo_allowed(cfg, owner, name)
    except _GateFailure as exc:
        return exc.payload_json
    path = args.get("path")
    if not isinstance(path, str) or not path:
        return _err("bad_args", "path is required")
    if "\x00" in path or ".." in path.split("/"):
        return _err("bad_args", "path contains forbidden segments")
    ref = args.get("ref") if isinstance(args.get("ref"), str) else None
    try:
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    res = client.file_contents(owner, name, path, ref=ref)
    if not res.get("success"):
        return _json(res)
    return _ok(file=_decode_file_content(res["payload"] or {}))


def handle_list_branches(args: Dict[str, Any], **_kw) -> str:
    cfg = github_config.load_config()
    if not cfg.enabled:
        return _err("plugin_disabled", "github.enabled is false")
    try:
        owner, name = _validate_repo(args)
        _check_repo_allowed(cfg, owner, name)
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    limit = int(args.get("limit") or DEFAULT_LIST_CAP)
    res = client.branches(owner, name, limit=limit)
    if not res.get("success"):
        return _json(res)
    payload = res["payload"] or []
    return _ok(branches=[_slim_branch(b) for b in payload if isinstance(b, dict)])


def handle_list_issues(args: Dict[str, Any], **_kw) -> str:
    cfg = github_config.load_config()
    if not cfg.enabled:
        return _err("plugin_disabled", "github.enabled is false")
    try:
        owner, name = _validate_repo(args)
        _check_repo_allowed(cfg, owner, name)
    except _GateFailure as exc:
        return exc.payload_json
    state = args.get("state") or "open"
    if state not in {"open", "closed", "all"}:
        return _err("bad_args", "state must be open|closed|all")
    limit = int(args.get("limit") or DEFAULT_LIST_CAP)
    try:
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    res = client.issues(owner, name, state=state, limit=limit)
    if not res.get("success"):
        return _json(res)
    # /issues mixes PRs with issues; strip the PR entries.
    items = [
        _slim_issue(i)
        for i in (res["payload"] or [])
        if isinstance(i, dict) and "pull_request" not in i
    ]
    return _ok(issues=items)


def handle_create_issue(args: Dict[str, Any], **_kw) -> str:
    cfg = github_config.load_config()
    if not cfg.enabled:
        return _err("plugin_disabled", "github.enabled is false")
    try:
        owner, name = _validate_repo(args)
        _check_repo_allowed(cfg, owner, name)
        _check_writes_enabled(cfg)
    except _GateFailure as exc:
        return exc.payload_json
    title = args.get("title")
    if not isinstance(title, str) or not title.strip():
        return _err("bad_args", "title is required")
    body = args.get("body") if isinstance(args.get("body"), str) else None
    labels = args.get("labels") if isinstance(args.get("labels"), list) else None
    try:
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    res = client.create_issue(owner, name, title=title, body=body, labels=labels)
    if not res.get("success"):
        return _json(res)
    return _ok(issue=_slim_issue(res["payload"] or {}))


def handle_list_pull_requests(args: Dict[str, Any], **_kw) -> str:
    cfg = github_config.load_config()
    if not cfg.enabled:
        return _err("plugin_disabled", "github.enabled is false")
    try:
        owner, name = _validate_repo(args)
        _check_repo_allowed(cfg, owner, name)
    except _GateFailure as exc:
        return exc.payload_json
    state = args.get("state") or "open"
    if state not in {"open", "closed", "all"}:
        return _err("bad_args", "state must be open|closed|all")
    limit = int(args.get("limit") or DEFAULT_LIST_CAP)
    try:
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    res = client.pull_requests(owner, name, state=state, limit=limit)
    if not res.get("success"):
        return _json(res)
    return _ok(
        pull_requests=[
            _slim_pull(p) for p in (res["payload"] or []) if isinstance(p, dict)
        ]
    )


def handle_get_pull_request(args: Dict[str, Any], **_kw) -> str:
    cfg = github_config.load_config()
    if not cfg.enabled:
        return _err("plugin_disabled", "github.enabled is false")
    try:
        owner, name = _validate_repo(args)
        _check_repo_allowed(cfg, owner, name)
    except _GateFailure as exc:
        return exc.payload_json
    number = args.get("number")
    if not isinstance(number, int) or number < 1:
        return _err("bad_args", "number must be a positive integer")
    try:
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    res = client.pull_request(owner, name, number=number)
    if not res.get("success"):
        return _json(res)
    return _ok(pull_request=_slim_pull(res["payload"] or {}))


def handle_comment_on_issue_or_pr(args: Dict[str, Any], **_kw) -> str:
    cfg = github_config.load_config()
    if not cfg.enabled:
        return _err("plugin_disabled", "github.enabled is false")
    try:
        owner, name = _validate_repo(args)
        _check_repo_allowed(cfg, owner, name)
        _check_writes_enabled(cfg)
    except _GateFailure as exc:
        return exc.payload_json
    number = args.get("number")
    if not isinstance(number, int) or number < 1:
        return _err("bad_args", "number must be a positive integer")
    body = args.get("body")
    if not isinstance(body, str) or not body.strip():
        return _err("bad_args", "body is required")
    try:
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    res = client.comment_on_issue(owner, name, number=number, body=body)
    if not res.get("success"):
        return _json(res)
    payload = res["payload"] or {}
    return _ok(
        comment={
            "id": payload.get("id"),
            "html_url": payload.get("html_url"),
            "user": (payload.get("user") or {}).get("login"),
        }
    )


# Used by __init__.register(ctx) — keeps the schemas + handlers paired so
# nothing drifts between the registration order and the documented list.
TOOL_REGISTRATIONS = (
    ("github_audit_repo", AUDIT_REPO_SCHEMA, handle_audit_repo, "🔍"),
    ("github_get_repo_file", GET_REPO_FILE_SCHEMA, handle_get_repo_file, "📄"),
    ("github_list_branches", LIST_BRANCHES_SCHEMA, handle_list_branches, "🌿"),
    ("github_list_issues", LIST_ISSUES_SCHEMA, handle_list_issues, "📋"),
    ("github_create_issue", CREATE_ISSUE_SCHEMA, handle_create_issue, "🆕"),
    (
        "github_list_pull_requests",
        LIST_PULL_REQUESTS_SCHEMA,
        handle_list_pull_requests,
        "🔀",
    ),
    ("github_get_pull_request", GET_PULL_REQUEST_SCHEMA, handle_get_pull_request, "🔎"),
    (
        "github_comment_on_issue_or_pr",
        COMMENT_SCHEMA,
        handle_comment_on_issue_or_pr,
        "💬",
    ),
)
