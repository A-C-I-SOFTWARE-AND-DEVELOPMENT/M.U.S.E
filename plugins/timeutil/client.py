"""Clients for the two free time/calendar sources.

  * TimeAPI.io   — current time + zone metadata  (timeapi.io)
  * Nager.Date   — public holidays by country/year  (date.nager.at)

Both key-less, read-only, and host-pinned. Methods raise
:class:`~tools.http_client.HttpClientError` on failure.
"""

from __future__ import annotations

from typing import Any, Optional

from tools.http_client import PublicApiClient

TIMEAPI_HOST = "timeapi.io"
NAGER_HOST = "date.nager.at"
ALLOWED_HOSTS = (TIMEAPI_HOST, NAGER_HOST)

TIMEAPI_CURRENT_ZONE_URL = f"https://{TIMEAPI_HOST}/api/time/current/zone"
NAGER_HOLIDAYS_URL = f"https://{NAGER_HOST}/api/v3/PublicHolidays/{{year}}/{{country}}"
NAGER_NEXT_URL = f"https://{NAGER_HOST}/api/v3/NextPublicHolidays/{{country}}"


class TimeClient:
    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(allowed_hosts=ALLOWED_HOSTS)

    def current_zone(self, time_zone: str) -> Any:
        return self._http.get_json(
            TIMEAPI_CURRENT_ZONE_URL, params={"timeZone": time_zone}
        )

    def holidays(self, year: int, country: str) -> Any:
        return self._http.get_json(
            NAGER_HOLIDAYS_URL.format(year=year, country=country.upper())
        )

    def next_holidays(self, country: str) -> Any:
        return self._http.get_json(NAGER_NEXT_URL.format(country=country.upper()))
