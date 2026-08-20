"""weather plugin — registration, gating, and handler behaviour (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.weather as plugin_pkg
import plugins.weather.tools as tools
from plugins.weather import config as weather_config
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        weather_config,
        "load_config",
        lambda: weather_config.WeatherConfig(enabled=True),
    )


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.setattr(
        weather_config,
        "load_config",
        lambda: weather_config.WeatherConfig(enabled=False),
    )


@pytest.fixture
def mock_client(monkeypatch):
    m = MagicMock()
    instance = MagicMock()
    m.return_value = instance
    monkeypatch.setattr(tools, "WeatherClient", m)
    return instance


# ── registration ─────────────────────────────────────────────────────────────


def test_register_emits_three_weather_tools():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    assert [c["name"] for c in captured] == [
        "weather_geocode",
        "weather_current",
        "weather_forecast",
    ]
    assert all(c["toolset"] == "weather" for c in captured)
    assert all(c["requires_env"] == [] for c in captured)


# ── gating ───────────────────────────────────────────────────────────────────


def test_check_fn_follows_enabled(enabled):
    assert tools.check_weather_requirements() is True


def test_check_fn_false_when_disabled(disabled):
    assert tools.check_weather_requirements() is False


def test_geocode_refused_when_disabled(disabled, mock_client):
    out = _parse(tools.handle_geocode({"name": "Austin"}))
    assert out["error"] == "plugin_disabled"
    mock_client.geocode.assert_not_called()


# ── happy paths ──────────────────────────────────────────────────────────────


def test_geocode_slims_results(enabled, mock_client):
    mock_client.geocode.return_value = {
        "results": [
            {
                "name": "Austin",
                "latitude": 30.27,
                "longitude": -97.74,
                "country": "United States",
                "admin1": "Texas",
                "timezone": "America/Chicago",
                "population": 931830,
            }
        ]
    }
    out = _parse(tools.handle_geocode({"name": "Austin"}))
    assert out["success"] is True
    assert out["results"][0]["latitude"] == 30.27
    assert "population" not in out["results"][0]


def test_current_maps_weather_code_to_text(enabled, mock_client):
    mock_client.current.return_value = {
        "current": {
            "time": "2026-06-05T12:00",
            "temperature_2m": 31.2,
            "apparent_temperature": 34.0,
            "relative_humidity_2m": 44,
            "precipitation": 0.0,
            "wind_speed_10m": 12.0,
            "wind_direction_10m": 180,
            "weather_code": 2,
        },
        "current_units": {"temperature_2m": "°C"},
        "latitude": 30.27,
        "longitude": -97.74,
        "timezone": "America/Chicago",
    }
    out = _parse(tools.handle_current({"latitude": 30.27, "longitude": -97.74}))
    assert out["success"] is True
    assert out["current"]["temperature"] == 31.2
    assert out["current"]["condition"] == "partly cloudy"


def test_forecast_zips_daily_arrays(enabled, mock_client):
    mock_client.forecast.return_value = {
        "daily": {
            "time": ["2026-06-05", "2026-06-06"],
            "weather_code": [0, 61],
            "temperature_2m_max": [33.0, 28.0],
            "temperature_2m_min": [22.0, 20.0],
            "precipitation_sum": [0.0, 5.2],
            "precipitation_probability_max": [0, 70],
            "wind_speed_10m_max": [15.0, 22.0],
        },
        "daily_units": {"temperature_2m_max": "°C"},
        "latitude": 30.27,
        "longitude": -97.74,
        "timezone": "America/Chicago",
    }
    out = _parse(tools.handle_forecast({"latitude": 30.27, "longitude": -97.74}))
    assert len(out["days"]) == 2
    assert out["days"][0]["condition"] == "clear sky"
    assert out["days"][1]["condition"] == "slight rain"
    assert out["days"][1]["precipitation_probability_max"] == 70


# ── bad args + error propagation ─────────────────────────────────────────────


def test_current_rejects_missing_coords(enabled, mock_client):
    out = _parse(tools.handle_current({"latitude": 30.27}))
    assert out["error"] == "bad_args"
    mock_client.current.assert_not_called()


def test_http_error_is_returned_as_envelope(enabled, mock_client):
    mock_client.geocode.side_effect = HttpClientError(
        "http_error", "open-meteo returned 429: rate limited", status=429
    )
    out = _parse(tools.handle_geocode({"name": "Austin"}))
    assert out["success"] is False
    assert out["error"] == "http_error"
    assert out["status"] == 429
