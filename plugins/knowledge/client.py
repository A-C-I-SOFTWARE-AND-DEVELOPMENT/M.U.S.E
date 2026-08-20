"""Clients for the general-knowledge sources.

  * Wikimedia REST + Action API — summaries & search  (en.wikipedia.org)
  * Free Dictionary             — word definitions     (api.dictionaryapi.dev)
  * REST Countries              — country facts         (restcountries.com)

All key-less, read-only, host-pinned via the shared
:class:`~tools.http_client.PublicApiClient`. Methods raise
:class:`~tools.http_client.HttpClientError` on failure.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from tools.http_client import PublicApiClient

WIKI_HOST = "en.wikipedia.org"
DICT_HOST = "api.dictionaryapi.dev"
COUNTRIES_HOST = "restcountries.com"
ALLOWED_HOSTS = (WIKI_HOST, DICT_HOST, COUNTRIES_HOST)

_COUNTRY_FIELDS = (
    "name,capital,region,subregion,population,area,currencies,"
    "languages,flags,cca2,cca3,timezones,tld"
)


class KnowledgeClient:
    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(allowed_hosts=ALLOWED_HOSTS)

    def wiki_summary(self, title: str) -> Any:
        # The REST summary endpoint wants the title path-encoded with spaces
        # as underscores.
        slug = quote(title.strip().replace(" ", "_"), safe="")
        return self._http.get_json(
            f"https://{WIKI_HOST}/api/rest_v1/page/summary/{slug}"
        )

    def wiki_search(self, query: str, *, limit: int) -> Any:
        return self._http.get_json(
            f"https://{WIKI_HOST}/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max(1, min(limit, 30)),
                "format": "json",
            },
        )

    def define(self, word: str) -> Any:
        return self._http.get_json(
            f"https://{DICT_HOST}/api/v2/entries/en/{quote(word.strip(), safe='')}"
        )

    def country(self, name: str) -> Any:
        return self._http.get_json(
            f"https://{COUNTRIES_HOST}/v3.1/name/{quote(name.strip(), safe='')}",
            params={"fields": _COUNTRY_FIELDS},
        )
