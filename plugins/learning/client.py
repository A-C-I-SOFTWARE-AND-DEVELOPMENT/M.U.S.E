"""Clients for the learning sources.

  * Open Library  — book search          (openlibrary.org)
  * Gutendex       — Project Gutenberg     (gutendex.com)
  * ZenQuotes      — random quotes         (zenquotes.io)
  * Wolfram|Alpha  — Short Answers API     (api.wolframalpha.com) [key-gated]

All read-only and host-pinned. The Wolfram app id is read from the
environment at call time, sent as a query parameter (its only supported
form), passed to the shared client's ``secrets`` list for redaction, and
never returned to the model. Methods raise
:class:`~tools.http_client.HttpClientError` on failure.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from tools.http_client import HttpClientError, PublicApiClient

OPENLIBRARY_HOST = "openlibrary.org"
GUTENDEX_HOST = "gutendex.com"
ZENQUOTES_HOST = "zenquotes.io"
WOLFRAM_HOST = "api.wolframalpha.com"
NO_KEY_HOSTS = (OPENLIBRARY_HOST, GUTENDEX_HOST, ZENQUOTES_HOST)

WOLFRAM_ENV_VAR = "WOLFRAM_APP_ID"


def wolfram_app_id() -> Optional[str]:
    val = os.environ.get(WOLFRAM_ENV_VAR)
    return val.strip() if val and val.strip() else None


class LearningClient:
    """Key-less learning sources (books, ebooks, quotes)."""

    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(allowed_hosts=NO_KEY_HOSTS)

    def books(self, query: str, *, limit: int) -> Any:
        return self._http.get_json(
            f"https://{OPENLIBRARY_HOST}/search.json",
            params={
                "q": query,
                "limit": max(1, min(limit, 30)),
                "fields": "title,author_name,first_publish_year,key,edition_count",
            },
        )

    def gutenberg(self, query: str) -> Any:
        return self._http.get_json(
            f"https://{GUTENDEX_HOST}/books", params={"search": query}
        )

    def quote(self) -> Any:
        return self._http.get_json(f"https://{ZENQUOTES_HOST}/api/random")


class WolframClient:
    """Wolfram|Alpha Short Answers. Requires WOLFRAM_APP_ID; text response."""

    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._app_id = wolfram_app_id()
        self._http = http or PublicApiClient(
            allowed_hosts=(WOLFRAM_HOST,),
            secrets=[self._app_id] if self._app_id else [],
        )

    def has_key(self) -> bool:
        return bool(self._app_id)

    def short_answer(self, query: str) -> str:
        if not self._app_id:
            raise HttpClientError(
                "no_key",
                f"{WOLFRAM_ENV_VAR} is not configured. Set it in ~/.hermes/.env.",
            )
        # Short Answers returns text/plain, not JSON.
        return self._http.get_text(
            f"https://{WOLFRAM_HOST}/v1/result",
            params={"appid": self._app_id, "i": query, "units": "metric"},
        )
