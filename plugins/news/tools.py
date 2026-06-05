"""Two agent-facing news tools.

  news_top       — Hacker News top stories. Always available when the
                   plugin is enabled (no key).
  news_headlines — NewsAPI.org headlines/search. Hidden from the model
                   until NEWSAPI_KEY is configured.

Uniform envelope ``{"success": bool, ...}``. Read-only GETs only.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from plugins.news import config as news_config
from plugins.news.client import HackerNewsClient, NewsApiClient, newsapi_key
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
    if not news_config.load_config().enabled:
        return _err("plugin_disabled", "news.enabled is false")
    return None


# ── check_fns ────────────────────────────────────────────────────────────────


def check_news_enabled() -> bool:
    """Hacker News tool: visible whenever the plugin is enabled."""
    return news_config.load_config().enabled


def check_newsapi_ready() -> bool:
    """NewsAPI tool: visible only when enabled AND NEWSAPI_KEY is present."""
    return news_config.load_config().enabled and bool(newsapi_key())


# ── schemas ──────────────────────────────────────────────────────────────────

NEWS_TOP_SCHEMA: Dict[str, Any] = {
    "name": "news_top",
    "description": (
        "Top stories from Hacker News (free, no key). Returns up to `limit` "
        "stories with title, url, score, author, and comment count. Great "
        "for tech/startup/developer news. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 30},
        },
        "additionalProperties": False,
    },
}

NEWS_HEADLINES_SCHEMA: Dict[str, Any] = {
    "name": "news_headlines",
    "description": (
        "General news headlines via NewsAPI.org. Either browse top headlines "
        "(optionally by country/category) or search all articles with `query`. "
        "Requires NEWSAPI_KEY in ~/.hermes/.env. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Optional search query."},
            "country": {
                "type": "string",
                "description": "2-letter country code for top headlines, e.g. 'us'.",
            },
            "category": {
                "type": "string",
                "enum": [
                    "business",
                    "entertainment",
                    "general",
                    "health",
                    "science",
                    "sports",
                    "technology",
                ],
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 30},
        },
        "additionalProperties": False,
    },
}


# ── handlers ─────────────────────────────────────────────────────────────────


def handle_news_top(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    limit = int(args.get("limit") or 10)
    limit = max(1, min(limit, 30))
    client = HackerNewsClient()
    try:
        ids = client.top_story_ids()[:limit]
        stories = []
        for sid in ids:
            item = client.item(sid)
            if not isinstance(item, dict):
                continue
            stories.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "url": item.get("url")
                or f"https://news.ycombinator.com/item?id={item.get('id')}",
                "score": item.get("score"),
                "by": item.get("by"),
                "comments": item.get("descendants"),
            })
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    return _ok(stories=stories, source="hacker_news")


def handle_news_headlines(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    client = NewsApiClient()
    if not client.has_key():
        return _err(
            "no_key",
            "NEWSAPI_KEY is not configured. Set it in ~/.hermes/.env, or use "
            "news_top (Hacker News) which needs no key.",
        )
    limit = int(args.get("limit") or 10)
    limit = max(1, min(limit, 30))
    query = args.get("query") if isinstance(args.get("query"), str) else None
    try:
        if query and query.strip():
            payload = client.search(query.strip(), page_size=limit)
        else:
            country = (
                args.get("country") if isinstance(args.get("country"), str) else None
            )
            category = (
                args.get("category") if isinstance(args.get("category"), str) else None
            )
            payload = client.top_headlines(
                country=country, category=category, page_size=limit
            )
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    articles = [
        {
            "title": a.get("title"),
            "source": (a.get("source") or {}).get("name"),
            "author": a.get("author"),
            "url": a.get("url"),
            "published_at": a.get("publishedAt"),
            "description": a.get("description"),
        }
        for a in (payload.get("articles") or [])
        if isinstance(a, dict)
    ]
    return _ok(articles=articles, total_results=payload.get("totalResults"))


# (name, schema, handler, emoji, check_fn, requires_env)
TOOL_REGISTRATIONS = (
    ("news_top", NEWS_TOP_SCHEMA, handle_news_top, "📰", check_news_enabled, []),
    (
        "news_headlines",
        NEWS_HEADLINES_SCHEMA,
        handle_news_headlines,
        "🗞️",
        check_newsapi_ready,
        ["NEWSAPI_KEY"],
    ),
)
