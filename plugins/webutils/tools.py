"""Four agent-facing web-utility tools (QR, IP info, public IP, sun times).

Uniform envelope ``{"success": bool, ...}``. The only gate is
``webutils.enabled`` — every call is read-only, no API key. ``qr_code``
returns a URL and makes no network request.
"""

from __future__ import annotations

import json
from typing import Any, Dict
from urllib.parse import quote

from plugins.webutils import config as webutils_config
from plugins.webutils.client import WebutilsClient
from tools.http_client import HttpClientError

QR_HOST = "api.qrserver.com"


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


def check_webutils_requirements() -> bool:
    return webutils_config.load_config().enabled


def _enabled_or_error() -> str | None:
    if not webutils_config.load_config().enabled:
        return _err("plugin_disabled", "webutils.enabled is false")
    return None


# ── schemas ──────────────────────────────────────────────────────────────────

QR_SCHEMA: Dict[str, Any] = {
    "name": "qr_code",
    "description": (
        "Build a QR-code image URL for the given text/URL via goQR (no key, no "
        "network call). Returns a PNG URL you can share or embed. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "data": {"type": "string", "description": "Text or URL to encode."},
            "size": {"type": "integer", "minimum": 50, "maximum": 1000},
        },
        "required": ["data"],
        "additionalProperties": False,
    },
}

IP_INFO_SCHEMA: Dict[str, Any] = {
    "name": "ip_info",
    "description": (
        "Geolocate an IP address via ipapi.co (free, no key): city, region, "
        "country, org/ASN, coordinates, and timezone. Omit `ip` to look up the "
        "address the request originates from. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ip": {"type": "string", "description": "IPv4/IPv6 address (optional)."}
        },
        "additionalProperties": False,
    },
}

PUBLIC_IP_SCHEMA: Dict[str, Any] = {
    "name": "public_ip",
    "description": (
        "Return the public IP address of the host running Hermes via ipify "
        "(free, no key). Read-only."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

SUNRISE_SCHEMA: Dict[str, Any] = {
    "name": "sunrise_sunset",
    "description": (
        "Sunrise, sunset, dawn, dusk, and day length for a latitude/longitude "
        "via SunriseSunset.io (free, no key). Optional `date` (YYYY-MM-DD) "
        "defaults to today. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "latitude": {"type": "number", "minimum": -90, "maximum": 90},
            "longitude": {"type": "number", "minimum": -180, "maximum": 180},
            "date": {"type": "string", "description": "Optional YYYY-MM-DD."},
        },
        "required": ["latitude", "longitude"],
        "additionalProperties": False,
    },
}


# ── handlers ─────────────────────────────────────────────────────────────────


def handle_qr_code(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    data = args.get("data")
    if not isinstance(data, str) or not data:
        return _err("bad_args", "data is required")
    if len(data) > 900:
        return _err("bad_args", "data too long for a QR code (max 900 chars)")
    size = int(args.get("size") or 200)
    size = max(50, min(size, 1000))
    url = (
        f"https://{QR_HOST}/v1/create-qr-code/"
        f"?size={size}x{size}&data={quote(data, safe='')}"
    )
    return _ok(url=url, size=size)


def handle_ip_info(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    ip = args.get("ip") if isinstance(args.get("ip"), str) and args.get("ip") else None
    try:
        payload = WebutilsClient().ip_info(ip)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    payload = payload or {}
    if payload.get("error"):
        return _err("not_found", str(payload.get("reason") or "invalid IP"))
    return _ok(
        ip=payload.get("ip"),
        city=payload.get("city"),
        region=payload.get("region"),
        country=payload.get("country_name"),
        country_code=payload.get("country_code"),
        org=payload.get("org"),
        asn=payload.get("asn"),
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        timezone=payload.get("timezone"),
    )


def handle_public_ip(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    try:
        payload = WebutilsClient().public_ip()
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    return _ok(ip=(payload or {}).get("ip"))


def handle_sunrise_sunset(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    lat, lng = args.get("latitude"), args.get("longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return _err("bad_args", "latitude and longitude are required numbers")
    date = args.get("date") if isinstance(args.get("date"), str) else None
    try:
        payload = WebutilsClient().sunrise_sunset(float(lat), float(lng), date)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    results = (payload or {}).get("results") or {}
    return _ok(
        results={
            "date": results.get("date"),
            "sunrise": results.get("sunrise"),
            "sunset": results.get("sunset"),
            "dawn": results.get("dawn"),
            "dusk": results.get("dusk"),
            "day_length": results.get("day_length"),
            "solar_noon": results.get("solar_noon"),
            "timezone": results.get("timezone"),
        }
    )


TOOL_REGISTRATIONS = (
    ("qr_code", QR_SCHEMA, handle_qr_code, "🔳"),
    ("ip_info", IP_INFO_SCHEMA, handle_ip_info, "🌍"),
    ("public_ip", PUBLIC_IP_SCHEMA, handle_public_ip, "📡"),
    ("sunrise_sunset", SUNRISE_SCHEMA, handle_sunrise_sunset, "🌅"),
)
