"""Three agent-facing time/calendar tools (TimeAPI.io, Nager.Date).

  time_now        — current time + offset for one timezone
  world_clock     — current time across several timezones at once
  public_holidays — public holidays for a country/year

Uniform envelope ``{"success": bool, ...}``. Read-only GETs, no API key.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Any, Dict

from plugins.timeutil import config as timeutil_config
from plugins.timeutil.client import TimeClient
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


def check_timeutil_requirements() -> bool:
    return timeutil_config.load_config().enabled


def _enabled_or_error() -> str | None:
    if not timeutil_config.load_config().enabled:
        return _err("plugin_disabled", "timeutil.enabled is false")
    return None


def _slim_time(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "timezone": payload.get("timeZone"),
        "datetime": payload.get("dateTime"),
        "date": payload.get("date"),
        "time": payload.get("time"),
        "day_of_week": payload.get("dayOfWeek"),
        "dst_active": payload.get("dstActive"),
    }


# ── schemas ──────────────────────────────────────────────────────────────────

_TZ_PROP = {
    "type": "string",
    "description": "IANA timezone name, e.g. 'America/Chicago' or 'Europe/London'.",
}

TIME_NOW_SCHEMA: Dict[str, Any] = {
    "name": "time_now",
    "description": (
        "Current date and time in a given IANA timezone (TimeAPI.io, free, "
        "no key). Returns date, time, day of week, and whether DST is "
        "active. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {"time_zone": _TZ_PROP},
        "required": ["time_zone"],
        "additionalProperties": False,
    },
}

WORLD_CLOCK_SCHEMA: Dict[str, Any] = {
    "name": "world_clock",
    "description": (
        "Current time across several IANA timezones at once — a world clock. "
        "Pass a list of zone names; returns the current time in each. Useful "
        "for scheduling across regions. Read-only, no key."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "time_zones": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 10,
                "description": "IANA zone names, e.g. ['America/New_York','Asia/Tokyo'].",
            }
        },
        "required": ["time_zones"],
        "additionalProperties": False,
    },
}

PUBLIC_HOLIDAYS_SCHEMA: Dict[str, Any] = {
    "name": "public_holidays",
    "description": (
        "Public holidays for a country and year (Nager.Date, free, no key). "
        "Pass a 2-letter country code (e.g. 'US', 'GB'); `year` defaults to "
        "the current year. Returns each holiday's date, local + English name. "
        "Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country": {"type": "string", "description": "ISO 3166-1 alpha-2 code."},
            "year": {"type": "integer", "minimum": 1975, "maximum": 2100},
        },
        "required": ["country"],
        "additionalProperties": False,
    },
}


# ── handlers ─────────────────────────────────────────────────────────────────


def handle_time_now(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    tz = args.get("time_zone")
    if not isinstance(tz, str) or not tz.strip():
        return _err("bad_args", "time_zone is required")
    try:
        payload = TimeClient().current_zone(tz.strip())
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    return _ok(**_slim_time(payload if isinstance(payload, dict) else {}))


def handle_world_clock(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    zones = args.get("time_zones")
    if not isinstance(zones, list) or not zones:
        return _err("bad_args", "time_zones must be a non-empty list")
    zones = [z.strip() for z in zones if isinstance(z, str) and z.strip()][:10]
    if not zones:
        return _err("bad_args", "time_zones must contain at least one zone name")
    client = TimeClient()
    clocks = []
    for tz in zones:
        try:
            payload = client.current_zone(tz)
            clocks.append(_slim_time(payload if isinstance(payload, dict) else {}))
        except HttpClientError as exc:
            clocks.append({"timezone": tz, "error": exc.error, "message": exc.message})
    return _ok(clocks=clocks)


def handle_public_holidays(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    country = args.get("country")
    if not isinstance(country, str) or len(country.strip()) != 2:
        return _err("bad_args", "country must be a 2-letter ISO code")
    year = args.get("year")
    if not isinstance(year, int):
        year = _dt.datetime.now(_dt.timezone.utc).year
    try:
        payload = TimeClient().holidays(year, country.strip())
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    holidays = [
        {
            "date": h.get("date"),
            "local_name": h.get("localName"),
            "name": h.get("name"),
            "global": h.get("global"),
            "types": h.get("types"),
        }
        for h in (payload or [])
        if isinstance(h, dict)
    ]
    return _ok(country=country.strip().upper(), year=year, holidays=holidays)


TOOL_REGISTRATIONS = (
    ("time_now", TIME_NOW_SCHEMA, handle_time_now, "🕐"),
    ("world_clock", WORLD_CLOCK_SCHEMA, handle_world_clock, "🌍"),
    ("public_holidays", PUBLIC_HOLIDAYS_SCHEMA, handle_public_holidays, "📅"),
)
