"""Clients for the small web-utility sources.

  * ipapi.co          — IP geolocation     (ipapi.co)
  * ipify             — caller public IP    (api.ipify.org)
  * SunriseSunset.io  — sun times           (api.sunrisesunset.io)

The QR code is a goQR URL built locally (no request), so it lives in
tools.py. All key-less, read-only, host-pinned via the shared
:class:`~tools.http_client.PublicApiClient`. Methods raise
:class:`~tools.http_client.HttpClientError` on failure.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from tools.http_client import PublicApiClient

IPAPI_HOST = "ipapi.co"
IPIFY_HOST = "api.ipify.org"
SUNRISE_HOST = "api.sunrisesunset.io"
ALLOWED_HOSTS = (IPAPI_HOST, IPIFY_HOST, SUNRISE_HOST)


class WebutilsClient:
    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(allowed_hosts=ALLOWED_HOSTS)

    def ip_info(self, ip: Optional[str]) -> Any:
        if ip:
            return self._http.get_json(
                f"https://{IPAPI_HOST}/{quote(ip, safe='')}/json/"
            )
        return self._http.get_json(f"https://{IPAPI_HOST}/json/")

    def public_ip(self) -> Any:
        return self._http.get_json(f"https://{IPIFY_HOST}/", params={"format": "json"})

    def sunrise_sunset(self, lat: float, lng: float, date: Optional[str]) -> Any:
        params: dict[str, Any] = {"lat": lat, "lng": lng}
        if date:
            params["date"] = date
        return self._http.get_json(f"https://{SUNRISE_HOST}/json", params=params)
