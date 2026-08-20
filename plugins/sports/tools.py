"""Two agent-facing sports tools (ESPN public JSON, no API key).

``sports_scores`` returns recent/live/upcoming games for a league;
``sports_standings`` returns the league table. Both use the uniform
``{"success": bool, ...}`` envelope. The only gate is ``sports.enabled``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from plugins.sports import config as sports_config
from plugins.sports.client import LEAGUES, EspnClient
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


def check_sports_requirements() -> bool:
    """Offer the tools only when ``sports.enabled`` is True (no key needed)."""
    return sports_config.load_config().enabled


def _enabled_or_error() -> str | None:
    if not sports_config.load_config().enabled:
        return _err("plugin_disabled", "sports.enabled is false")
    return None


_LEAGUE = {
    "type": "string",
    "enum": sorted(LEAGUES.keys()),
    "description": "League key, e.g. nfl, nba, mlb, nhl, epl, la_liga, mls.",
}

SCORES_SCHEMA: Dict[str, Any] = {
    "name": "sports_scores",
    "description": (
        "Recent, live, and upcoming games for a league (scores, status, and "
        "matchups) from ESPN. Read-only, no API key. Optionally filter by team "
        "name/abbreviation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "league": _LEAGUE,
            "team": {
                "type": "string",
                "description": "Optional team name or abbreviation to filter by.",
            },
        },
        "required": ["league"],
        "additionalProperties": False,
    },
}

STANDINGS_SCHEMA: Dict[str, Any] = {
    "name": "sports_standings",
    "description": (
        "Current standings / league table for a league from ESPN, grouped by "
        "conference/division where applicable. Read-only, no API key."
    ),
    "parameters": {
        "type": "object",
        "properties": {"league": _LEAGUE},
        "required": ["league"],
        "additionalProperties": False,
    },
}


def _valid_league_or_error(league: Any) -> str:
    """Return an error envelope when ``league`` is not a known league key.

    The ``isinstance``/membership check at each call site (not here) is what
    lets the type checker narrow ``league`` to ``str`` before it reaches the
    ESPN client, so this helper is only the shared error message.
    """
    return _err(
        "bad_args",
        f"unknown league {league!r}; valid: {', '.join(sorted(LEAGUES))}",
    )


def _competitor(c: Dict[str, Any]) -> Dict[str, Any]:
    team = c.get("team") or {}
    return {
        "team": team.get("displayName"),
        "abbreviation": team.get("abbreviation"),
        "score": c.get("score"),
        "winner": c.get("winner"),
    }


def handle_scores(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    league = args.get("league")
    if not isinstance(league, str) or league not in LEAGUES:
        return _valid_league_or_error(league)
    try:
        payload = EspnClient().scoreboard(league)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)

    games: List[Dict[str, Any]] = []
    for e in (payload.get("events") or []) if isinstance(payload, dict) else []:
        if not isinstance(e, dict):
            continue
        comp = (e.get("competitions") or [{}])[0] or {}
        home = away = None
        for c in comp.get("competitors") or []:
            if not isinstance(c, dict):
                continue
            side = _competitor(c)
            if c.get("homeAway") == "home":
                home = side
            elif c.get("homeAway") == "away":
                away = side
        status_type = ((e.get("status") or {}).get("type")) or {}
        games.append({
            "name": e.get("name"),
            "short_name": e.get("shortName"),
            "date": e.get("date"),
            "state": status_type.get("state"),
            "completed": status_type.get("completed"),
            "detail": status_type.get("detail"),
            "home": home,
            "away": away,
        })

    team = args.get("team")
    if isinstance(team, str) and team.strip():
        needle = team.strip().lower()

        def _match(g: Dict[str, Any]) -> bool:
            for side in (g.get("home"), g.get("away")):
                if not side:
                    continue
                for field in ("team", "abbreviation"):
                    val = side.get(field)
                    if isinstance(val, str) and needle in val.lower():
                        return True
            return False

        games = [g for g in games if _match(g)]

    return _ok(league=league, games=games, count=len(games))


def _parse_entries(entries: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for en in entries or []:
        if not isinstance(en, dict):
            continue
        team = (en.get("team") or {}).get("displayName")
        stats: Dict[str, Any] = {}
        for s in en.get("stats") or []:
            if not isinstance(s, dict):
                continue
            name = s.get("name") or s.get("type")
            if name is None:
                continue
            stats[name] = s.get("displayValue", s.get("value"))
        out.append({"team": team, "stats": stats})
    return out


def handle_standings(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    league = args.get("league")
    if not isinstance(league, str) or league not in LEAGUES:
        return _valid_league_or_error(league)
    try:
        payload = EspnClient().standings(league)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)

    groups: List[Dict[str, Any]] = []
    if isinstance(payload, dict):
        std = payload.get("standings")
        if isinstance(std, dict) and std.get("entries"):
            groups.append({
                "name": payload.get("name") or league,
                "entries": _parse_entries(std.get("entries")),
            })
        for child in payload.get("children") or []:
            if not isinstance(child, dict):
                continue
            cstd = child.get("standings") or {}
            groups.append({
                "name": child.get("name"),
                "entries": _parse_entries(cstd.get("entries")),
            })
    return _ok(league=league, groups=groups, count=len(groups))


TOOL_REGISTRATIONS = (
    ("sports_scores", SCORES_SCHEMA, handle_scores, "🏟️"),
    ("sports_standings", STANDINGS_SCHEMA, handle_standings, "📊"),
)
