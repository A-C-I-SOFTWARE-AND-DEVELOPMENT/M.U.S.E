"""Thin ESPN public-JSON client used by the sports tools.

ESPN exposes free, unauthenticated scoreboard/standings JSON under
``site.api.espn.com``. The host is pinned in :data:`ALLOWED_HOSTS` and enforced
by the shared :class:`~tools.http_client.PublicApiClient` allowlist. Methods raise
:class:`~tools.http_client.HttpClientError` on failure; the tools layer catches
once and returns a uniform JSON envelope.
"""

from __future__ import annotations

from typing import Any, Optional

from tools.http_client import PublicApiClient

ESPN_HOST = "site.api.espn.com"
ALLOWED_HOSTS = (ESPN_HOST,)

# Friendly league key -> (ESPN sport, ESPN league path).
LEAGUES: dict[str, tuple[str, str]] = {
    "nfl": ("football", "nfl"),
    "ncaafb": ("football", "college-football"),
    "nba": ("basketball", "nba"),
    "wnba": ("basketball", "wnba"),
    "ncaamb": ("basketball", "mens-college-basketball"),
    "ncaawb": ("basketball", "womens-college-basketball"),
    "mlb": ("baseball", "mlb"),
    "nhl": ("hockey", "nhl"),
    "epl": ("soccer", "eng.1"),
    "la_liga": ("soccer", "esp.1"),
    "serie_a": ("soccer", "ita.1"),
    "bundesliga": ("soccer", "ger.1"),
    "ligue_1": ("soccer", "fra.1"),
    "mls": ("soccer", "usa.1"),
    "champions_league": ("soccer", "uefa.champions"),
}

_USER_AGENT = (
    "hermes-sports-plugin/1.0 "
    "(+https://github.com/NousResearch/hermes-agent)"
)


class EspnClient:
    """Read-only ESPN public-JSON client."""

    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(
            allowed_hosts=ALLOWED_HOSTS, user_agent=_USER_AGENT
        )

    def scoreboard(self, league: str) -> Any:
        sport, path = LEAGUES[league]
        return self._http.get_json(
            f"https://{ESPN_HOST}/apis/site/v2/sports/{sport}/{path}/scoreboard"
        )

    def standings(self, league: str) -> Any:
        sport, path = LEAGUES[league]
        return self._http.get_json(
            f"https://{ESPN_HOST}/apis/v2/sports/{sport}/{path}/standings"
        )
