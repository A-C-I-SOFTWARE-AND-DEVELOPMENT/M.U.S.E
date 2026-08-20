"""Thin Openverse client used by the image_search tool.

Openverse (https://openverse.org) indexes openly-licensed (Creative Commons /
public-domain) images and exposes a free JSON API. The single host is pinned in
:data:`ALLOWED_HOSTS` and enforced by the shared
:class:`~tools.http_client.PublicApiClient` allowlist. Methods raise
:class:`~tools.http_client.HttpClientError` on failure; the tools layer catches
once and returns a uniform JSON envelope.
"""

from __future__ import annotations

from typing import Any, Optional

from tools.http_client import PublicApiClient

OPENVERSE_HOST = "api.openverse.org"
ALLOWED_HOSTS = (OPENVERSE_HOST,)

SEARCH_URL = f"https://{OPENVERSE_HOST}/v1/images/"

_USER_AGENT = (
    "hermes-image-search-plugin/1.0 "
    "(+https://github.com/NousResearch/hermes-agent)"
)


class OpenverseClient:
    """Read-only Openverse image-search client."""

    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(
            allowed_hosts=ALLOWED_HOSTS, user_agent=_USER_AGENT
        )

    def search(self, query: str, *, limit: int = 4) -> Any:
        return self._http.get_json(
            SEARCH_URL,
            params={"q": query, "page_size": max(1, min(limit, 20))},
        )
