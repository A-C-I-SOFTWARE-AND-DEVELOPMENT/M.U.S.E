"""Four agent-facing learning tools.

  books_search     — Open Library book search (no key)
  gutenberg_search — Project Gutenberg free ebooks (no key)
  quote_random     — a random quote (no key)
  wolfram_answer   — Wolfram|Alpha short answer; hidden until WOLFRAM_APP_ID set

Uniform envelope ``{"success": bool, ...}``. Read-only GETs only.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from plugins.learning import config as learning_config
from plugins.learning.client import LearningClient, WolframClient, wolfram_app_id
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


def _enabled_or_error() -> str | None:
    if not learning_config.load_config().enabled:
        return _err("plugin_disabled", "learning.enabled is false")
    return None


def check_learning_enabled() -> bool:
    """Key-less tools: visible whenever the plugin is enabled."""
    return learning_config.load_config().enabled


def check_wolfram_ready() -> bool:
    """Wolfram tool: visible only when enabled AND WOLFRAM_APP_ID is present."""
    return learning_config.load_config().enabled and bool(wolfram_app_id())


def _str_arg(args: Dict[str, Any], key: str) -> str | None:
    val = args.get(key)
    if not isinstance(val, str) or not val.strip():
        return None
    return val.strip()


# ── schemas ──────────────────────────────────────────────────────────────────

BOOKS_SCHEMA: Dict[str, Any] = {
    "name": "books_search",
    "description": (
        "Search books on Open Library (free, no key). Returns up to `limit` "
        "matches with title, author(s), first publish year, and edition count. "
        "Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Title, author, or keywords."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 30},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

GUTENBERG_SCHEMA: Dict[str, Any] = {
    "name": "gutenberg_search",
    "description": (
        "Search Project Gutenberg's free public-domain ebooks via Gutendex "
        "(no key). Returns matching books with authors, download count, and "
        "download links (plain text / HTML / epub). Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Title or author."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

QUOTE_SCHEMA: Dict[str, Any] = {
    "name": "quote_random",
    "description": (
        "Return a random inspirational quote with its author (ZenQuotes, free, "
        "no key). Read-only."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

WOLFRAM_SCHEMA: Dict[str, Any] = {
    "name": "wolfram_answer",
    "description": (
        "Ask Wolfram|Alpha a factual/computational question and get a short "
        "text answer (math, unit conversions, science, dates, statistics). "
        "Requires WOLFRAM_APP_ID in ~/.hermes/.env. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "The question."}},
        "required": ["query"],
        "additionalProperties": False,
    },
}


# ── handlers ─────────────────────────────────────────────────────────────────


def handle_books_search(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    query = _str_arg(args, "query")
    if query is None:
        return _err("bad_args", "query is required")
    limit = int(args.get("limit") or 5)
    try:
        payload = LearningClient().books(query, limit=limit)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    docs = (payload or {}).get("docs") or []
    books = [
        {
            "title": d.get("title"),
            "authors": d.get("author_name"),
            "first_publish_year": d.get("first_publish_year"),
            "edition_count": d.get("edition_count"),
            "openlibrary_key": d.get("key"),
        }
        for d in docs[:limit]
        if isinstance(d, dict)
    ]
    return _ok(books=books, total=(payload or {}).get("numFound"))


def handle_gutenberg_search(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    query = _str_arg(args, "query")
    if query is None:
        return _err("bad_args", "query is required")
    limit = int(args.get("limit") or 5)
    try:
        payload = LearningClient().gutenberg(query)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    results = (payload or {}).get("results") or []
    books = []
    for b in results[:limit]:
        if not isinstance(b, dict):
            continue
        formats = b.get("formats") or {}
        books.append({
            "id": b.get("id"),
            "title": b.get("title"),
            "authors": [
                a.get("name") for a in b.get("authors") or [] if isinstance(a, dict)
            ],
            "download_count": b.get("download_count"),
            "text_url": formats.get("text/plain; charset=utf-8")
            or formats.get("text/plain"),
            "html_url": formats.get("text/html"),
            "epub_url": formats.get("application/epub+zip"),
        })
    return _ok(books=books, total=(payload or {}).get("count"))


def handle_quote_random(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    try:
        payload = LearningClient().quote()
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    rows = payload if isinstance(payload, list) else []
    if not rows or not isinstance(rows[0], dict):
        return _err("bad_response", "unexpected quote response")
    return _ok(quote=rows[0].get("q"), author=rows[0].get("a"))


def handle_wolfram_answer(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    client = WolframClient()
    if not client.has_key():
        return _err(
            "no_key",
            "WOLFRAM_APP_ID is not configured. Set it in ~/.hermes/.env.",
        )
    query = _str_arg(args, "query")
    if query is None:
        return _err("bad_args", "query is required")
    try:
        answer = client.short_answer(query)
    except HttpClientError as exc:
        # Wolfram returns 501 when it has no short answer for the input.
        if exc.status == 501:
            return _err("not_found", "Wolfram|Alpha had no short answer")
        return _err(exc.error, exc.message, status=exc.status)
    return _ok(answer=answer)


# (name, schema, handler, emoji, check_fn, requires_env)
TOOL_REGISTRATIONS = (
    (
        "books_search",
        BOOKS_SCHEMA,
        handle_books_search,
        "📚",
        check_learning_enabled,
        [],
    ),
    (
        "gutenberg_search",
        GUTENBERG_SCHEMA,
        handle_gutenberg_search,
        "📜",
        check_learning_enabled,
        [],
    ),
    (
        "quote_random",
        QUOTE_SCHEMA,
        handle_quote_random,
        "💬",
        check_learning_enabled,
        [],
    ),
    (
        "wolfram_answer",
        WOLFRAM_SCHEMA,
        handle_wolfram_answer,
        "🧮",
        check_wolfram_ready,
        ["WOLFRAM_APP_ID"],
    ),
)
