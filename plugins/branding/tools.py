"""Five agent-facing branding / design tools.

  color_info        — name + conversions for a hex colour (no key)
  color_scheme      — generate a palette from a base colour (no key)
  placeholder_image — build a Lorem Picsum placeholder URL (no key, no request)
  stock_photo_search — Unsplash search; hidden until UNSPLASH_ACCESS_KEY set
  google_fonts      — Google Fonts catalogue; hidden until GOOGLE_FONTS_API_KEY set

Uniform envelope ``{"success": bool, ...}``. Read-only. Image tools return
URLs, never binary blobs.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict
from urllib.parse import quote

from plugins.branding import config as branding_config
from plugins.branding.client import (
    ColorClient,
    GoogleFontsClient,
    UnsplashClient,
    google_fonts_key,
    unsplash_key,
)
from tools.http_client import HttpClientError

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
PICSUM_HOST = "picsum.photos"


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
    if not branding_config.load_config().enabled:
        return _err("plugin_disabled", "branding.enabled is false")
    return None


def check_branding_enabled() -> bool:
    return branding_config.load_config().enabled


def check_unsplash_ready() -> bool:
    return branding_config.load_config().enabled and bool(unsplash_key())


def check_google_fonts_ready() -> bool:
    return branding_config.load_config().enabled and bool(google_fonts_key())


def _norm_hex(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    m = _HEX_RE.match(value.strip())
    return m.group(1) if m else None


# ── schemas ──────────────────────────────────────────────────────────────────

COLOR_INFO_SCHEMA: Dict[str, Any] = {
    "name": "color_info",
    "description": (
        "Identify a colour from its hex value via TheColorAPI (free, no key). "
        "Returns the closest named colour plus RGB and HSL conversions. "
        "Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "hex": {
                "type": "string",
                "description": "Hex colour, e.g. 'FF5733' or '#FF5733'.",
            }
        },
        "required": ["hex"],
        "additionalProperties": False,
    },
}

COLOR_SCHEME_SCHEMA: Dict[str, Any] = {
    "name": "color_scheme",
    "description": (
        "Generate a colour palette from a base hex colour via TheColorAPI "
        "(free, no key). `mode` is one of monochrome, monochrome-dark, "
        "monochrome-light, analogic, complement, analogic-complement, triad, "
        "quad. Returns `count` colours with hex + name. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "hex": {"type": "string", "description": "Base hex colour."},
            "mode": {
                "type": "string",
                "enum": [
                    "monochrome",
                    "monochrome-dark",
                    "monochrome-light",
                    "analogic",
                    "complement",
                    "analogic-complement",
                    "triad",
                    "quad",
                ],
            },
            "count": {"type": "integer", "minimum": 2, "maximum": 10},
        },
        "required": ["hex"],
        "additionalProperties": False,
    },
}

PLACEHOLDER_SCHEMA: Dict[str, Any] = {
    "name": "placeholder_image",
    "description": (
        "Build a Lorem Picsum placeholder-image URL (no key, no network call). "
        "Returns a stable URL for the given size; pass a `seed` for a "
        "repeatable image, and optionally grayscale or blur. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "width": {"type": "integer", "minimum": 1, "maximum": 5000},
            "height": {"type": "integer", "minimum": 1, "maximum": 5000},
            "seed": {
                "type": "string",
                "description": "Optional seed for a stable image.",
            },
            "grayscale": {"type": "boolean"},
            "blur": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["width", "height"],
        "additionalProperties": False,
    },
}

STOCK_PHOTO_SCHEMA: Dict[str, Any] = {
    "name": "stock_photo_search",
    "description": (
        "Search Unsplash for stock photos. Returns image URLs, descriptions, "
        "and photographer attribution. Requires UNSPLASH_ACCESS_KEY in "
        "~/.hermes/.env. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search terms."},
            "per_page": {"type": "integer", "minimum": 1, "maximum": 30},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

GOOGLE_FONTS_SCHEMA: Dict[str, Any] = {
    "name": "google_fonts",
    "description": (
        "List Google Fonts families, sorted by popularity/trending/date/alpha. "
        "Requires GOOGLE_FONTS_API_KEY in ~/.hermes/.env. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sort": {
                "type": "string",
                "enum": ["popularity", "trending", "date", "alpha", "style"],
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "additionalProperties": False,
    },
}


# ── handlers ─────────────────────────────────────────────────────────────────


def handle_color_info(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    hex_value = _norm_hex(args.get("hex"))
    if hex_value is None:
        return _err("bad_args", "hex must be a 3- or 6-digit hex colour")
    try:
        payload = ColorClient().color(hex_value)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    payload = payload or {}
    return _ok(
        color={
            "name": (payload.get("name") or {}).get("value"),
            "hex": (payload.get("hex") or {}).get("value"),
            "rgb": (payload.get("rgb") or {}).get("value"),
            "hsl": (payload.get("hsl") or {}).get("value"),
        }
    )


def handle_color_scheme(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    hex_value = _norm_hex(args.get("hex"))
    if hex_value is None:
        return _err("bad_args", "hex must be a 3- or 6-digit hex colour")
    mode_arg = args.get("mode")
    mode = mode_arg if isinstance(mode_arg, str) and mode_arg else "analogic"
    count = int(args.get("count") or 5)
    count = max(2, min(count, 10))
    try:
        payload = ColorClient().scheme(hex_value, mode=mode, count=count)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    colors = [
        {
            "hex": (c.get("hex") or {}).get("value"),
            "name": (c.get("name") or {}).get("value"),
            "rgb": (c.get("rgb") or {}).get("value"),
        }
        for c in (payload or {}).get("colors", [])
        if isinstance(c, dict)
    ]
    return _ok(mode=mode, base=f"#{hex_value}", colors=colors)


def handle_placeholder_image(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    width, height = args.get("width"), args.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        return _err("bad_args", "width and height are required integers")
    if not (1 <= width <= 5000 and 1 <= height <= 5000):
        return _err("bad_args", "width and height must be between 1 and 5000")
    seed = args.get("seed")
    if isinstance(seed, str) and seed.strip():
        url = f"https://{PICSUM_HOST}/seed/{quote(seed.strip(), safe='')}/{width}/{height}"
    else:
        url = f"https://{PICSUM_HOST}/{width}/{height}"
    query = []
    if args.get("grayscale") is True:
        query.append("grayscale")
    blur = args.get("blur")
    if isinstance(blur, int) and 1 <= blur <= 10:
        query.append(f"blur={blur}")
    if query:
        url = f"{url}?{'&'.join(query)}"
    return _ok(url=url, width=width, height=height)


def handle_stock_photo_search(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    client = UnsplashClient()
    if not client.has_key():
        return _err(
            "no_key", "UNSPLASH_ACCESS_KEY is not configured. Set it in ~/.hermes/.env."
        )
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return _err("bad_args", "query is required")
    per_page = int(args.get("per_page") or 5)
    per_page = max(1, min(per_page, 30))
    try:
        payload = client.search(query.strip(), per_page=per_page)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    photos = [
        {
            "id": r.get("id"),
            "description": r.get("description") or r.get("alt_description"),
            "url": (r.get("urls") or {}).get("regular"),
            "thumb": (r.get("urls") or {}).get("thumb"),
            "link": (r.get("links") or {}).get("html"),
            "photographer": (r.get("user") or {}).get("name"),
        }
        for r in (payload or {}).get("results", [])
        if isinstance(r, dict)
    ]
    return _ok(photos=photos, total=(payload or {}).get("total"))


def handle_google_fonts(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    client = GoogleFontsClient()
    if not client.has_key():
        return _err(
            "no_key",
            "GOOGLE_FONTS_API_KEY is not configured. Set it in ~/.hermes/.env.",
        )
    sort_arg = args.get("sort")
    sort = sort_arg if isinstance(sort_arg, str) and sort_arg else "popularity"
    limit = int(args.get("limit") or 20)
    limit = max(1, min(limit, 50))
    try:
        payload = client.fonts(sort=sort)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    fonts = [
        {
            "family": f.get("family"),
            "category": f.get("category"),
            "variants": len(f.get("variants") or []),
            "subsets": f.get("subsets"),
        }
        for f in (payload or {}).get("items", [])[:limit]
        if isinstance(f, dict)
    ]
    return _ok(sort=sort, fonts=fonts)


# (name, schema, handler, emoji, check_fn, requires_env)
TOOL_REGISTRATIONS = (
    (
        "color_info",
        COLOR_INFO_SCHEMA,
        handle_color_info,
        "🎨",
        check_branding_enabled,
        [],
    ),
    (
        "color_scheme",
        COLOR_SCHEME_SCHEMA,
        handle_color_scheme,
        "🌈",
        check_branding_enabled,
        [],
    ),
    (
        "placeholder_image",
        PLACEHOLDER_SCHEMA,
        handle_placeholder_image,
        "🖼️",
        check_branding_enabled,
        [],
    ),
    (
        "stock_photo_search",
        STOCK_PHOTO_SCHEMA,
        handle_stock_photo_search,
        "📷",
        check_unsplash_ready,
        ["UNSPLASH_ACCESS_KEY"],
    ),
    (
        "google_fonts",
        GOOGLE_FONTS_SCHEMA,
        handle_google_fonts,
        "🔤",
        check_google_fonts_ready,
        ["GOOGLE_FONTS_API_KEY"],
    ),
)
