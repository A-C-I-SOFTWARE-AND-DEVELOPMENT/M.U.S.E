"""Clients for the two news sources.

  * Hacker News Firebase API — free, key-less  (hacker-news.firebaseio.com)
  * NewsAPI.org              — optional, needs NEWSAPI_KEY  (newsapi.org)

Both read-only and host-pinned. The NewsAPI key is read from the
environment at call time, sent as the ``X-Api-Key`` request header (so it
never lands in a URL/query string), passed to the shared client's
``secrets`` list for redaction, and never returned to the model.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from tools.http_client import HttpClientError, PublicApiClient

HN_HOST = "hacker-news.firebaseio.com"
NEWSAPI_HOST = "newsapi.org"

HN_TOPSTORIES_URL = f"https://{HN_HOST}/v0/topstories.json"
HN_ITEM_URL = f"https://{HN_HOST}/v0/item/{{id}}.json"
NEWSAPI_HEADLINES_URL = f"https://{NEWSAPI_HOST}/v2/top-headlines"
NEWSAPI_EVERYTHING_URL = f"https://{NEWSAPI_HOST}/v2/everything"

NEWSAPI_ENV_VAR = "NEWSAPI_KEY"


def newsapi_key() -> Optional[str]:
    """Return NEWSAPI_KEY from the environment (``~/.hermes/.env``) or None."""
    val = os.environ.get(NEWSAPI_ENV_VAR)
    return val.strip() if val and val.strip() else None


class HackerNewsClient:
    """Read-only Hacker News client (no key)."""

    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(allowed_hosts=(HN_HOST,))

    def top_story_ids(self) -> list[int]:
        ids = self._http.get_json(HN_TOPSTORIES_URL)
        return [i for i in (ids or []) if isinstance(i, int)]

    def item(self, item_id: int) -> Any:
        return self._http.get_json(HN_ITEM_URL.format(id=item_id))


class NewsApiClient:
    """NewsAPI.org client. Requires NEWSAPI_KEY; refuses cleanly without it."""

    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._key = newsapi_key()
        self._http = http or PublicApiClient(
            allowed_hosts=(NEWSAPI_HOST,),
            secrets=[self._key] if self._key else [],
        )

    def has_key(self) -> bool:
        return bool(self._key)

    def _headers(self) -> dict[str, str]:
        # NewsAPI accepts the key as a header — keeps it out of the URL.
        return {"X-Api-Key": self._key} if self._key else {}

    def top_headlines(
        self, *, country: Optional[str], category: Optional[str], page_size: int
    ) -> Any:
        if not self._key:
            raise HttpClientError(
                "no_key",
                f"{NEWSAPI_ENV_VAR} is not configured. Set it in ~/.hermes/.env.",
            )
        params: dict[str, Any] = {"pageSize": page_size}
        if country:
            params["country"] = country
        if category:
            params["category"] = category
        if not country and not category:
            # NewsAPI requires at least one selector for top-headlines.
            params["country"] = "us"
        return self._http.get_json(
            NEWSAPI_HEADLINES_URL, params=params, headers=self._headers()
        )

    def search(self, query: str, *, page_size: int) -> Any:
        if not self._key:
            raise HttpClientError(
                "no_key",
                f"{NEWSAPI_ENV_VAR} is not configured. Set it in ~/.hermes/.env.",
            )
        return self._http.get_json(
            NEWSAPI_EVERYTHING_URL,
            params={"q": query, "pageSize": page_size, "sortBy": "publishedAt"},
            headers=self._headers(),
        )
