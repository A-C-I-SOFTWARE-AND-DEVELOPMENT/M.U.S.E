"""Two agent-facing places tools (OpenStreetMap, no API key).

``places_search`` resolves a name/query to matching places with coordinates via
Nominatim. ``places_map`` is a pure URL builder (no network): given coordinates,
it returns a shareable OpenStreetMap map link, per-marker links, and — for two or
more stops — an OSRM directions URL. Every tool returns the uniform
``{"success": bool, ...}`` JSON envelope. The only gate is ``places.enabled``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from plugins.places import config as places_config
from plugins.places.client import PlacesClient
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


def check_places_requirements() -> bool:
    """Offer the tools only when ``places.enabled`` is True (no key needed)."""
    return places_config.load_config().enabled


def _enabled_or_error() -> str | None:
    if not places_config.load_config().enabled:
        return _err("plugin_disabled", "places.enabled is false")
    return None


# ── schemas ──────────────────────────────────────────────────────────────────

SEARCH_SCHEMA: Dict[str, Any] = {
    "name": "places_search",
    "description": (
        "Search for places, businesses, and landmarks by name or free-text "
        "query using OpenStreetMap. Returns up to `limit` matches, each with a "
        "display name, latitude/longitude, category, address, and an "
        "openstreetmap.org link. Read-only, no API key. Pass the chosen "
        "coordinates to places_map to build a shareable map."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Place name or query, e.g. 'Eiffel Tower' or 'coffee in Shibuya'.",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 25},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

_LOCATION = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Label for this stop."},
        "latitude": {"type": "number", "minimum": -90, "maximum": 90},
        "longitude": {"type": "number", "minimum": -180, "maximum": 180},
    },
    "required": ["latitude", "longitude"],
    "additionalProperties": False,
}

MAP_SCHEMA: Dict[str, Any] = {
    "name": "places_map",
    "description": (
        "Build a shareable OpenStreetMap map from coordinates (pure URL builder, "
        "no network). Returns a map link centered on the stops, a marker link per "
        "stop, and — for two or more stops — an OSRM directions URL for the chosen "
        "travel mode. Get coordinates from places_search first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "locations": {
                "type": "array",
                "items": _LOCATION,
                "minItems": 1,
                "maxItems": 25,
                "description": "Ordered stops (lat/lon, optional name).",
            },
            "travel_mode": {
                "type": "string",
                "enum": ["driving", "walking", "cycling"],
                "description": "Routing profile for the directions URL; default driving.",
            },
        },
        "required": ["locations"],
        "additionalProperties": False,
    },
}


# ── handlers ─────────────────────────────────────────────────────────────────

def handle_search(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return _err("bad_args", "query is required")
    limit = int(args.get("limit") or 5)
    try:
        payload = PlacesClient().search(query.strip(), limit=limit)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)

    rows = payload if isinstance(payload, list) else []
    results: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            lat = float(r.get("lat"))
            lon = float(r.get("lon"))
        except (TypeError, ValueError):
            continue
        osm_type = r.get("osm_type")
        osm_id = r.get("osm_id")
        osm_url = (
            f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
            if osm_type and osm_id is not None
            else None
        )
        results.append({
            "name": r.get("name") or (r.get("display_name") or "").split(",")[0],
            "display_name": r.get("display_name"),
            "latitude": lat,
            "longitude": lon,
            "category": r.get("category") or r.get("class"),
            "type": r.get("type"),
            "address": r.get("address") or {},
            "osm_url": osm_url,
            "importance": r.get("importance"),
        })
    return _ok(results=results, count=len(results))


_OSRM_ENGINE = {
    "driving": "fossgis_osrm_car",
    "walking": "fossgis_osrm_foot",
    "cycling": "fossgis_osrm_bike",
}


def handle_map(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    raw = args.get("locations")
    if not isinstance(raw, list) or not raw:
        return _err("bad_args", "locations must be a non-empty array")

    pts: List[Dict[str, Any]] = []
    for loc in raw:
        if not isinstance(loc, dict):
            continue
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        pts.append({"name": loc.get("name"), "lat": float(lat), "lon": float(lon)})
    if not pts:
        return _err("bad_args", "no valid {latitude, longitude} locations")

    clat = sum(p["lat"] for p in pts) / len(pts)
    clon = sum(p["lon"] for p in pts) / len(pts)
    zoom = 15 if len(pts) == 1 else 12

    markers = [
        {
            "name": p["name"],
            "latitude": p["lat"],
            "longitude": p["lon"],
            "osm_url": (
                f"https://www.openstreetmap.org/?mlat={p['lat']}&mlon={p['lon']}"
                f"#map=15/{p['lat']}/{p['lon']}"
            ),
        }
        for p in pts
    ]
    map_url = f"https://www.openstreetmap.org/#map={zoom}/{clat:.5f}/{clon:.5f}"

    directions_url = None
    if len(pts) >= 2:
        mode = args.get("travel_mode")
        engine = _OSRM_ENGINE.get(mode, _OSRM_ENGINE["driving"])
        route = ";".join(f"{p['lat']},{p['lon']}" for p in pts)
        directions_url = (
            f"https://www.openstreetmap.org/directions?engine={engine}&route={route}"
        )

    return _ok(
        center={"latitude": round(clat, 6), "longitude": round(clon, 6)},
        zoom=zoom,
        map_url=map_url,
        markers=markers,
        directions_url=directions_url,
    )


TOOL_REGISTRATIONS = (
    ("places_search", SEARCH_SCHEMA, handle_search, "📍"),
    ("places_map", MAP_SCHEMA, handle_map, "🗺️"),
)
