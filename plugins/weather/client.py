"""Thin Open-Meteo client used by the weather tools.

Open-Meteo (https://open-meteo.com) is free and key-less. Two hosts:

  * ``geocoding-api.open-meteo.com`` — place name → lat/lon.
  * ``api.open-meteo.com``          — current conditions + daily forecast.

Both are pinned in :data:`ALLOWED_HOSTS` and enforced by the shared
:class:`~tools.http_client.PublicApiClient` allowlist, so a tool can
never be redirected at another host. Methods raise
:class:`~tools.http_client.HttpClientError` on failure; the tools layer
catches once and returns a uniform JSON envelope.
"""

from __future__ import annotations

from typing import Any, Optional

from tools.http_client import PublicApiClient

GEOCODE_HOST = "geocoding-api.open-meteo.com"
FORECAST_HOST = "api.open-meteo.com"
ALLOWED_HOSTS = (GEOCODE_HOST, FORECAST_HOST)

GEOCODE_URL = f"https://{GEOCODE_HOST}/v1/search"
FORECAST_URL = f"https://{FORECAST_HOST}/v1/forecast"

# What we ask Open-Meteo to return for "current conditions".
_CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "precipitation,weather_code,wind_speed_10m,wind_direction_10m"
)
_DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_sum,precipitation_probability_max,wind_speed_10m_max"
)


class WeatherClient:
    """Read-only Open-Meteo client."""

    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(allowed_hosts=ALLOWED_HOSTS)

    def geocode(self, name: str, *, count: int = 5) -> Any:
        return self._http.get_json(
            GEOCODE_URL,
            params={"name": name, "count": max(1, min(count, 20)), "format": "json"},
        )

    def current(
        self, latitude: float, longitude: float, *, units: str = "metric"
    ) -> Any:
        temp_unit = "fahrenheit" if units == "imperial" else "celsius"
        speed_unit = "mph" if units == "imperial" else "kmh"
        return self._http.get_json(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": _CURRENT_FIELDS,
                "temperature_unit": temp_unit,
                "wind_speed_unit": speed_unit,
                "timezone": "auto",
            },
        )

    def forecast(
        self, latitude: float, longitude: float, *, days: int = 7, units: str = "metric"
    ) -> Any:
        temp_unit = "fahrenheit" if units == "imperial" else "celsius"
        speed_unit = "mph" if units == "imperial" else "kmh"
        return self._http.get_json(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": _DAILY_FIELDS,
                "forecast_days": max(1, min(days, 16)),
                "temperature_unit": temp_unit,
                "wind_speed_unit": speed_unit,
                "timezone": "auto",
            },
        )
