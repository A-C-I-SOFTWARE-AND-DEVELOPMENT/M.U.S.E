"""Four agent-facing developer-reference tools (PyPI, npm, crates, Stack Overflow).

Uniform envelope ``{"success": bool, ...}``. The only gate is
``devtools.enabled`` — every call is a read-only GET, no API key.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from plugins.devtools import config as devtools_config
from plugins.devtools.client import DevtoolsClient
from tools.http_client import HttpClientError


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


def check_devtools_requirements() -> bool:
    return devtools_config.load_config().enabled


def _enabled_or_error() -> str | None:
    if not devtools_config.load_config().enabled:
        return _err("plugin_disabled", "devtools.enabled is false")
    return None


def _require_name(args: Dict[str, Any], key: str = "name") -> str | None:
    val = args.get(key)
    if not isinstance(val, str) or not val.strip():
        return None
    return val.strip()


# ── schemas ──────────────────────────────────────────────────────────────────

PYPI_SCHEMA: Dict[str, Any] = {
    "name": "pypi_package",
    "description": (
        "Look up a Python package on PyPI (free, no key). Returns the latest "
        "version, summary, license, project URLs, required Python, and release "
        "count. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Package name, e.g. 'requests'."}
        },
        "required": ["name"],
        "additionalProperties": False,
    },
}

NPM_SCHEMA: Dict[str, Any] = {
    "name": "npm_package",
    "description": (
        "Look up a Node.js package on the npm registry (free, no key). Returns "
        "the latest version, description, license, homepage, and maintainers. "
        "Supports scoped names like '@scope/pkg'. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Package name, e.g. 'express'."}
        },
        "required": ["name"],
        "additionalProperties": False,
    },
}

CRATES_SCHEMA: Dict[str, Any] = {
    "name": "crates_package",
    "description": (
        "Look up a Rust crate on crates.io (free, no key). Returns the max "
        "version, description, downloads, repository, and license. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Crate name, e.g. 'serde'."}
        },
        "required": ["name"],
        "additionalProperties": False,
    },
}

STACKOVERFLOW_SCHEMA: Dict[str, Any] = {
    "name": "stackoverflow_search",
    "description": (
        "Search Stack Overflow questions via the Stack Exchange API (free, no "
        "key). Returns up to `limit` questions with title, score, answer count, "
        "whether answered, tags, and link. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search terms."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 30},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}


# ── handlers ─────────────────────────────────────────────────────────────────


def handle_pypi_package(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    name = _require_name(args)
    if name is None:
        return _err("bad_args", "name is required")
    try:
        payload = DevtoolsClient().pypi(name)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    info = (payload or {}).get("info") or {}
    releases = (payload or {}).get("releases") or {}
    return _ok(
        package={
            "name": info.get("name"),
            "version": info.get("version"),
            "summary": info.get("summary"),
            "license": info.get("license"),
            "requires_python": info.get("requires_python"),
            "home_page": info.get("home_page") or info.get("project_url"),
            "project_urls": info.get("project_urls"),
            "release_count": len(releases),
        }
    )


def handle_npm_package(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    name = _require_name(args)
    if name is None:
        return _err("bad_args", "name is required")
    try:
        payload = DevtoolsClient().npm(name)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    payload = payload or {}
    latest = (payload.get("dist-tags") or {}).get("latest")
    versions = payload.get("versions") or {}
    return _ok(
        package={
            "name": payload.get("name"),
            "version": latest,
            "description": payload.get("description"),
            "license": payload.get("license"),
            "homepage": payload.get("homepage"),
            "version_count": len(versions),
        }
    )


def handle_crates_package(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    name = _require_name(args)
    if name is None:
        return _err("bad_args", "name is required")
    try:
        payload = DevtoolsClient().crates(name)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    crate = (payload or {}).get("crate") or {}
    versions = (payload or {}).get("versions") or []
    license_ = (
        versions[0].get("license")
        if versions and isinstance(versions[0], dict)
        else None
    )
    return _ok(
        crate={
            "name": crate.get("name"),
            "max_version": crate.get("max_stable_version") or crate.get("max_version"),
            "description": crate.get("description"),
            "downloads": crate.get("downloads"),
            "homepage": crate.get("homepage"),
            "repository": crate.get("repository"),
            "documentation": crate.get("documentation"),
            "license": license_,
        }
    )


def handle_stackoverflow_search(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    query = _require_name(args, "query")
    if query is None:
        return _err("bad_args", "query is required")
    limit = int(args.get("limit") or 5)
    try:
        payload = DevtoolsClient().stackoverflow(query, limit=limit)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    items = [
        {
            "title": q.get("title"),
            "score": q.get("score"),
            "is_answered": q.get("is_answered"),
            "answer_count": q.get("answer_count"),
            "tags": q.get("tags"),
            "link": q.get("link"),
        }
        for q in (payload or {}).get("items", [])
        if isinstance(q, dict)
    ]
    return _ok(questions=items, quota_remaining=(payload or {}).get("quota_remaining"))


TOOL_REGISTRATIONS = (
    ("pypi_package", PYPI_SCHEMA, handle_pypi_package, "🐍"),
    ("npm_package", NPM_SCHEMA, handle_npm_package, "📦"),
    ("crates_package", CRATES_SCHEMA, handle_crates_package, "🦀"),
    ("stackoverflow_search", STACKOVERFLOW_SCHEMA, handle_stackoverflow_search, "💬"),
)
