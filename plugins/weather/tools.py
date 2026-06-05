"""Three agent-facing weather tools (Open-Meteo, no API key).

Every tool returns a JSON string with the uniform envelope
``{"success": bool, ...}`` so the agent's structured-output parsing is
the same across plugins. The only gate is ``weather.enabled`` — there is
no key and every call is a read-only GET.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from plugins.weather import config as weather_config
from plugins.weather.client import WeatherClient
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


def check_weather_requirements() -> bool:
    """Offer the tools only when ``weather.enabled`` is True (no key needed)."""
    return weather_config.load_config().enabled


def _enabled_or_error() -> str | None:
    if not weather_config.load_config().enabled:
        return _err("plugin_disabled", "weather.enabled is false")
    return None


# ── schemas ──────────────────────────────────────────────────────────────────

_LAT = {"type": "number", "minimum": -90, "maximum": 90, "description": "Latitude."}
_LON = {"type": "number", "minimum": -180, "maximum": 180, "description": "Longitude."}
_UNITS = {
    "type": "string",
    "enum": ["metric", "imperial"],
    "description": "Unit system; defaults to metric (°C, km/h).",
}

GEOCODE_SCHEMA: Dict[str, Any] = {
    "name": "weather_geocode",
    "description": (
        "Resolve a place name (city, town, landmark) to coordinates using "
        "Open-Meteo geocoding. Returns up to `count` candidates with "
        "latitude, longitude, country, and admin region. Call this first, "
        "then pass the chosen lat/lon to weather_current or weather_forecast."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Place name to look up."},
            "count": {"type": "integer", "minimum": 1, "maximum": 20},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
}

CURRENT_SCHEMA: Dict[str, Any] = {
    "name": "weather_current",
    "description": (
        "Current weather conditions at a latitude/longitude: temperature, "
        "apparent temperature, humidity, precipitation, wind, and a "
        "human-readable condition. Read-only, no API key."
    ),
    "parameters": {
        "type": "object",
        "properties": {"latitude": _LAT, "longitude": _LON, "units": _UNITS},
        "required": ["latitude", "longitude"],
        "additionalProperties": False,
    },
}

FORECAST_SCHEMA: Dict[str, Any] = {
    "name": "weather_forecast",
    "description": (
        "Daily weather forecast at a latitude/longitude for the next `days` "
        "days (default 7, max 16): high/low temperature, precipitation, and "
        "max wind. Read-only, no API key."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "latitude": _LAT,
            "longitude": _LON,
            "days": {"type": "integer", "minimum": 1, "maximum": 16},
            "units": _UNITS,
        },
        "required": ["latitude", "longitude"],
        "additionalProperties": False,
    },
}


# ── WMO weather-code → text (so the agent doesn't have to memorise codes) ─────
_WMO = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def _describe(code: Any) -> str | None:
    try:
        return _WMO.get(int(code))
    except (TypeError, ValueError):
        return None


# ── handlers ─────────────────────────────────────────────────────────────────


def handle_geocode(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    name = args.get("name")
    if not isinstance(name, str) or not name.strip():
        return _err("bad_args", "name is required")
    count = int(args.get("count") or 5)
    try:
        payload = WeatherClient().geocode(name.strip(), count=count)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    results = [
        {
            "name": r.get("name"),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "country": r.get("country"),
            "admin1": r.get("admin1"),
            "timezone": r.get("timezone"),
        }
        for r in (payload.get("results") or [])
        if isinstance(r, dict)
    ]
    return _ok(results=results)


def handle_current(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    lat, lon = args.get("latitude"), args.get("longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return _err("bad_args", "latitude and longitude are required numbers")
    units = "imperial" if args.get("units") == "imperial" else "metric"
    try:
        payload = WeatherClient().current(float(lat), float(lon), units=units)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    cur = payload.get("current") or {}
    return _ok(
        current={
            "time": cur.get("time"),
            "temperature": cur.get("temperature_2m"),
            "apparent_temperature": cur.get("apparent_temperature"),
            "relative_humidity": cur.get("relative_humidity_2m"),
            "precipitation": cur.get("precipitation"),
            "wind_speed": cur.get("wind_speed_10m"),
            "wind_direction": cur.get("wind_direction_10m"),
            "condition": _describe(cur.get("weather_code")),
        },
        units=payload.get("current_units") or {},
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        timezone=payload.get("timezone"),
    )


def handle_forecast(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    lat, lon = args.get("latitude"), args.get("longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return _err("bad_args", "latitude and longitude are required numbers")
    days = int(args.get("days") or 7)
    units = "imperial" if args.get("units") == "imperial" else "metric"
    try:
        payload = WeatherClient().forecast(
            float(lat), float(lon), days=days, units=units
        )
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    codes = daily.get("weather_code") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    psum = daily.get("precipitation_sum") or []
    pprob = daily.get("precipitation_probability_max") or []
    wmax = daily.get("wind_speed_10m_max") or []
    out = []
    for i, day in enumerate(times):
        out.append({
            "date": day,
            "temp_max": tmax[i] if i < len(tmax) else None,
            "temp_min": tmin[i] if i < len(tmin) else None,
            "precipitation_sum": psum[i] if i < len(psum) else None,
            "precipitation_probability_max": pprob[i] if i < len(pprob) else None,
            "wind_speed_max": wmax[i] if i < len(wmax) else None,
            "condition": _describe(codes[i] if i < len(codes) else None),
        })
    return _ok(
        days=out,
        units=payload.get("daily_units") or {},
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        timezone=payload.get("timezone"),
    )


TOOL_REGISTRATIONS = (
    ("weather_geocode", GEOCODE_SCHEMA, handle_geocode, "📍"),
    ("weather_current", CURRENT_SCHEMA, handle_current, "🌡️"),
    ("weather_forecast", FORECAST_SCHEMA, handle_forecast, "🌦️"),
)
