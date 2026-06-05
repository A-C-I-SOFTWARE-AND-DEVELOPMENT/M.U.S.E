"""Four agent-facing general-knowledge tools (Wikipedia, dictionary, countries).

Uniform envelope ``{"success": bool, ...}``. The only gate is
``knowledge.enabled`` — every call is a read-only GET, no API key.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from plugins.knowledge import config as knowledge_config
from plugins.knowledge.client import KnowledgeClient
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


def check_knowledge_requirements() -> bool:
    return knowledge_config.load_config().enabled


def _enabled_or_error() -> str | None:
    if not knowledge_config.load_config().enabled:
        return _err("plugin_disabled", "knowledge.enabled is false")
    return None


def _str_arg(args: Dict[str, Any], key: str) -> str | None:
    val = args.get(key)
    if not isinstance(val, str) or not val.strip():
        return None
    return val.strip()


# ── schemas ──────────────────────────────────────────────────────────────────

WIKI_SUMMARY_SCHEMA: Dict[str, Any] = {
    "name": "wikipedia_summary",
    "description": (
        "Get the lead summary of an English Wikipedia article by title "
        "(Wikimedia REST, free, no key). Returns the extract, description, and "
        "page URL. If unsure of the exact title, use wikipedia_search first. "
        "Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {"title": {"type": "string", "description": "Article title."}},
        "required": ["title"],
        "additionalProperties": False,
    },
}

WIKI_SEARCH_SCHEMA: Dict[str, Any] = {
    "name": "wikipedia_search",
    "description": (
        "Search English Wikipedia for articles matching a query (free, no key). "
        "Returns up to `limit` results with title, a snippet, and page id. "
        "Read-only."
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

DICTIONARY_SCHEMA: Dict[str, Any] = {
    "name": "dictionary_define",
    "description": (
        "Define an English word using the Free Dictionary API (no key). Returns "
        "phonetics and meanings grouped by part of speech with definitions and "
        "examples. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {"word": {"type": "string", "description": "Word to define."}},
        "required": ["word"],
        "additionalProperties": False,
    },
}

COUNTRY_SCHEMA: Dict[str, Any] = {
    "name": "country_info",
    "description": (
        "Look up facts about a country by name via REST Countries (free, no "
        "key): capital, region, population, area, currencies, languages, "
        "timezones, and flag. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Country name."}},
        "required": ["name"],
        "additionalProperties": False,
    },
}


# ── handlers ─────────────────────────────────────────────────────────────────


def handle_wikipedia_summary(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    title = _str_arg(args, "title")
    if title is None:
        return _err("bad_args", "title is required")
    try:
        payload = KnowledgeClient().wiki_summary(title)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    payload = payload or {}
    return _ok(
        title=payload.get("title"),
        description=payload.get("description"),
        extract=payload.get("extract"),
        url=((payload.get("content_urls") or {}).get("desktop") or {}).get("page"),
        thumbnail=(payload.get("thumbnail") or {}).get("source"),
    )


def handle_wikipedia_search(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    query = _str_arg(args, "query")
    if query is None:
        return _err("bad_args", "query is required")
    limit = int(args.get("limit") or 5)
    try:
        payload = KnowledgeClient().wiki_search(query, limit=limit)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    hits = ((payload or {}).get("query") or {}).get("search") or []
    results = [
        {
            "title": h.get("title"),
            "pageid": h.get("pageid"),
            "snippet": h.get("snippet"),
            "wordcount": h.get("wordcount"),
        }
        for h in hits
        if isinstance(h, dict)
    ]
    return _ok(results=results)


def handle_dictionary_define(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    word = _str_arg(args, "word")
    if word is None:
        return _err("bad_args", "word is required")
    try:
        payload = KnowledgeClient().define(word)
    except HttpClientError as exc:
        # The Free Dictionary API returns 404 for unknown words.
        if exc.status == 404:
            return _err("not_found", f"no definition for {word!r}")
        return _err(exc.error, exc.message, status=exc.status)
    entries = payload if isinstance(payload, list) else []
    if not entries:
        return _err("not_found", f"no definition for {word!r}")
    first = entries[0] if isinstance(entries[0], dict) else {}
    meanings = [
        {
            "part_of_speech": m.get("partOfSpeech"),
            "definitions": [
                {"definition": d.get("definition"), "example": d.get("example")}
                for d in (m.get("definitions") or [])[:5]
                if isinstance(d, dict)
            ],
        }
        for m in (first.get("meanings") or [])
        if isinstance(m, dict)
    ]
    phonetics = [
        p.get("text")
        for p in (first.get("phonetics") or [])
        if isinstance(p, dict) and p.get("text")
    ]
    return _ok(word=first.get("word"), phonetics=phonetics, meanings=meanings)


def handle_country_info(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    name = _str_arg(args, "name")
    if name is None:
        return _err("bad_args", "name is required")
    try:
        payload = KnowledgeClient().country(name)
    except HttpClientError as exc:
        if exc.status == 404:
            return _err("not_found", f"no country matching {name!r}")
        return _err(exc.error, exc.message, status=exc.status)
    rows = payload if isinstance(payload, list) else []
    if not rows:
        return _err("not_found", f"no country matching {name!r}")
    c = rows[0] if isinstance(rows[0], dict) else {}
    return _ok(
        country={
            "name": (c.get("name") or {}).get("common"),
            "official_name": (c.get("name") or {}).get("official"),
            "capital": c.get("capital"),
            "region": c.get("region"),
            "subregion": c.get("subregion"),
            "population": c.get("population"),
            "area": c.get("area"),
            "languages": list((c.get("languages") or {}).values()),
            "currencies": list((c.get("currencies") or {}).keys()),
            "timezones": c.get("timezones"),
            "cca2": c.get("cca2"),
            "flag": (c.get("flags") or {}).get("png"),
        }
    )


TOOL_REGISTRATIONS = (
    ("wikipedia_summary", WIKI_SUMMARY_SCHEMA, handle_wikipedia_summary, "📖"),
    ("wikipedia_search", WIKI_SEARCH_SCHEMA, handle_wikipedia_search, "🔎"),
    ("dictionary_define", DICTIONARY_SCHEMA, handle_dictionary_define, "📕"),
    ("country_info", COUNTRY_SCHEMA, handle_country_info, "🌐"),
)
