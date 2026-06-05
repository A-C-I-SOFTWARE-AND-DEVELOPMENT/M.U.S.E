"""Clients for the branding / design sources.

  * TheColorAPI  — color naming + schemes  (www.thecolorapi.com)  [no key]
  * Unsplash     — stock photo search       (api.unsplash.com)     [key-gated]
  * Google Fonts — font catalogue           (www.googleapis.com)   [key-gated]

Lorem Picsum placeholder URLs and goQR codes are built locally (no request),
so they live in tools.py. Keys are read from the environment at call time,
passed to the shared client's ``secrets`` list for redaction, and never
returned to the model. Methods raise
:class:`~tools.http_client.HttpClientError` on failure.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from tools.http_client import HttpClientError, PublicApiClient

COLOR_HOST = "www.thecolorapi.com"
UNSPLASH_HOST = "api.unsplash.com"
GOOGLEAPIS_HOST = "www.googleapis.com"

UNSPLASH_ENV_VAR = "UNSPLASH_ACCESS_KEY"
GOOGLE_FONTS_ENV_VAR = "GOOGLE_FONTS_API_KEY"


def unsplash_key() -> Optional[str]:
    val = os.environ.get(UNSPLASH_ENV_VAR)
    return val.strip() if val and val.strip() else None


def google_fonts_key() -> Optional[str]:
    val = os.environ.get(GOOGLE_FONTS_ENV_VAR)
    return val.strip() if val and val.strip() else None


class ColorClient:
    """TheColorAPI — key-less colour naming and schemes."""

    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(allowed_hosts=(COLOR_HOST,))

    def color(self, hex_value: str) -> Any:
        return self._http.get_json(
            f"https://{COLOR_HOST}/id", params={"hex": hex_value}
        )

    def scheme(self, hex_value: str, *, mode: str, count: int) -> Any:
        return self._http.get_json(
            f"https://{COLOR_HOST}/scheme",
            params={"hex": hex_value, "mode": mode, "count": count},
        )


class UnsplashClient:
    """Unsplash photo search. Requires UNSPLASH_ACCESS_KEY."""

    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._key = unsplash_key()
        self._http = http or PublicApiClient(
            allowed_hosts=(UNSPLASH_HOST,),
            secrets=[self._key] if self._key else [],
        )

    def has_key(self) -> bool:
        return bool(self._key)

    def search(self, query: str, *, per_page: int) -> Any:
        if not self._key:
            raise HttpClientError(
                "no_key",
                f"{UNSPLASH_ENV_VAR} is not configured. Set it in ~/.hermes/.env.",
            )
        return self._http.get_json(
            f"https://{UNSPLASH_HOST}/search/photos",
            params={"query": query, "per_page": per_page},
            headers={"Authorization": f"Client-ID {self._key}"},
        )


class GoogleFontsClient:
    """Google Fonts catalogue. Requires GOOGLE_FONTS_API_KEY."""

    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._key = google_fonts_key()
        self._http = http or PublicApiClient(
            allowed_hosts=(GOOGLEAPIS_HOST,),
            secrets=[self._key] if self._key else [],
        )

    def has_key(self) -> bool:
        return bool(self._key)

    def fonts(self, *, sort: str) -> Any:
        if not self._key:
            raise HttpClientError(
                "no_key",
                f"{GOOGLE_FONTS_ENV_VAR} is not configured. Set it in ~/.hermes/.env.",
            )
        # Google Fonts only accepts the key as a query parameter.
        return self._http.get_json(
            f"https://{GOOGLEAPIS_HOST}/webfonts/v1/webfonts",
            params={"key": self._key, "sort": sort},
        )
