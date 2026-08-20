"""Thin OpenStreetMap Nominatim client used by the places tools.

Nominatim (https://nominatim.openstreetmap.org) is free and key-less. The single
host is pinned in :data:`ALLOWED_HOSTS` and enforced by the shared
:class:`~tools.http_client.PublicApiClient` allowlist, so a tool can never be
redirected at another host. A descriptive ``User-Agent`` is sent per the
Nominatim usage policy. Methods raise
:class:`~tools.http_client.HttpClientError` on failure; the tools layer catches
once and returns a uniform JSON envelope.
"""

from __future__ import annotations

from typing import Any, Optional

from tools.http_client import PublicApiClient

NOMINATIM_HOST = "nominatim.openstreetmap.org"
ALLOWED_HOSTS = (NOMINATIM_HOST,)

SEARCH_URL = f"https://{NOMINATIM_HOST}/search"

# Nominatim's usage policy asks for a descriptive UA identifying the application.
_USER_AGENT = (
    "hermes-places-plugin/1.0 "
    "(+https://github.com/NousResearch/hermes-agent)"
)


class PlacesClient:
    """Read-only Nominatim search client."""

    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(
            allowed_hosts=ALLOWED_HOSTS, user_agent=_USER_AGENT
        )

    def search(self, query: str, *, limit: int = 5) -> Any:
        return self._http.get_json(
            SEARCH_URL,
            params={
                "q": query,
                "format": "jsonv2",
                "limit": max(1, min(limit, 25)),
                "addressdetails": 1,
            },
        )
