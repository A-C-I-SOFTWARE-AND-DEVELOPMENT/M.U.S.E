"""Thin clients for the developer-reference sources.

  * PyPI            — Python package metadata   (pypi.org)
  * npm registry    — Node package metadata     (registry.npmjs.org)
  * crates.io       — Rust crate metadata        (crates.io)
  * Stack Exchange  — Q&A search                 (api.stackexchange.com)

All key-less, read-only, and host-pinned via the shared
:class:`~tools.http_client.PublicApiClient`. Methods raise
:class:`~tools.http_client.HttpClientError` on failure.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from tools.http_client import PublicApiClient

PYPI_HOST = "pypi.org"
NPM_HOST = "registry.npmjs.org"
CRATES_HOST = "crates.io"
STACKEX_HOST = "api.stackexchange.com"
ALLOWED_HOSTS = (PYPI_HOST, NPM_HOST, CRATES_HOST, STACKEX_HOST)


class DevtoolsClient:
    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(allowed_hosts=ALLOWED_HOSTS)

    def pypi(self, name: str) -> Any:
        return self._http.get_json(f"https://{PYPI_HOST}/pypi/{quote(name)}/json")

    def npm(self, name: str) -> Any:
        # npm package names can contain '/' for scopes (@scope/pkg); keep it.
        return self._http.get_json(f"https://{NPM_HOST}/{quote(name, safe='@/')}")

    def crates(self, name: str) -> Any:
        return self._http.get_json(f"https://{CRATES_HOST}/api/v1/crates/{quote(name)}")

    def stackoverflow(self, query: str, *, limit: int) -> Any:
        return self._http.get_json(
            f"https://{STACKEX_HOST}/2.3/search/advanced",
            params={
                "order": "desc",
                "sort": "relevance",
                "q": query,
                "site": "stackoverflow",
                "pagesize": max(1, min(limit, 30)),
            },
        )
