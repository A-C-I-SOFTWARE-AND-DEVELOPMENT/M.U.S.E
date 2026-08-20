"""One agent-facing image-search tool (Openverse, no API key).

Returns openly-licensed images with the attribution metadata the contract's
copyright rules require (creator, license, license URL, source landing page). The
uniform ``{"success": bool, ...}`` envelope matches the other plugins. The only
gate is ``image_search.enabled``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from plugins.image_search import config as image_config
from plugins.image_search.client import OpenverseClient
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


def check_image_search_requirements() -> bool:
    """Offer the tool only when ``image_search.enabled`` is True (no key needed)."""
    return image_config.load_config().enabled


def _enabled_or_error() -> str | None:
    if not image_config.load_config().enabled:
        return _err("plugin_disabled", "image_search.enabled is false")
    return None


SEARCH_SCHEMA: Dict[str, Any] = {
    "name": "image_search",
    "description": (
        "Search the web for openly-licensed (Creative Commons / public-domain) "
        "images via Openverse. Returns up to `limit` results, each with a title, "
        "direct image URL, thumbnail, source, creator, and license + attribution. "
        "Read-only, no API key. Always show the attribution when displaying an "
        "image."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to find images of, e.g. 'pangolin' or 'Tokyo at night'.",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}


def handle_image_search(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return _err("bad_args", "query is required")
    limit = int(args.get("limit") or 4)
    try:
        payload = OpenverseClient().search(query.strip(), limit=limit)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)

    rows = payload.get("results") if isinstance(payload, dict) else None
    results: List[Dict[str, Any]] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        lic = r.get("license")
        lic_ver = r.get("license_version")
        license_name = (
            f"CC {str(lic).upper()} {lic_ver}".strip()
            if lic and str(lic).lower() not in {"pdm", "cc0"}
            else (str(lic).upper() if lic else None)
        )
        results.append({
            "title": r.get("title"),
            "image_url": r.get("url"),
            "thumbnail": r.get("thumbnail"),
            "source": r.get("source") or r.get("provider"),
            "creator": r.get("creator"),
            "license": license_name,
            "license_url": r.get("license_url"),
            "landing_url": r.get("foreign_landing_url"),
            "attribution": r.get("attribution"),
            "width": r.get("width"),
            "height": r.get("height"),
        })
    return _ok(
        results=results,
        count=len(results),
        total=payload.get("result_count") if isinstance(payload, dict) else None,
    )


TOOL_REGISTRATIONS = (
    ("image_search", SEARCH_SCHEMA, handle_image_search, "🖼️"),
)
