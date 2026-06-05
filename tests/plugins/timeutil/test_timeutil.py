"""timeutil plugin — registration, gating, handlers (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.timeutil as plugin_pkg
import plugins.timeutil.tools as tools
from plugins.timeutil import config as timeutil_config
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        timeutil_config,
        "load_config",
        lambda: timeutil_config.TimeutilConfig(enabled=True),
    )


@pytest.fixture
def mock_client(monkeypatch):
    m = MagicMock()
    instance = MagicMock()
    m.return_value = instance
    monkeypatch.setattr(tools, "TimeClient", m)
    return instance


# ── registration ─────────────────────────────────────────────────────────────


def test_register_emits_three_tools():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    assert [c["name"] for c in captured] == [
        "time_now",
        "world_clock",
        "public_holidays",
    ]
    assert all(c["toolset"] == "timeutil" for c in captured)


# ── gating ───────────────────────────────────────────────────────────────────


def test_disabled_blocks(monkeypatch, mock_client):
    monkeypatch.setattr(
        timeutil_config,
        "load_config",
        lambda: timeutil_config.TimeutilConfig(enabled=False),
    )
    out = _parse(tools.handle_time_now({"time_zone": "UTC"}))
    assert out["error"] == "plugin_disabled"
    mock_client.current_zone.assert_not_called()


# ── time_now ─────────────────────────────────────────────────────────────────


def test_time_now_slims_payload(enabled, mock_client):
    mock_client.current_zone.return_value = {
        "timeZone": "America/Chicago",
        "dateTime": "2026-06-05T09:30:00",
        "date": "06/05/2026",
        "time": "09:30",
        "dayOfWeek": "Friday",
        "dstActive": True,
        "milliSeconds": 123,
    }
    out = _parse(tools.handle_time_now({"time_zone": "America/Chicago"}))
    assert out["success"] is True
    assert out["day_of_week"] == "Friday"
    assert "milliSeconds" not in out


def test_time_now_requires_zone(enabled, mock_client):
    out = _parse(tools.handle_time_now({}))
    assert out["error"] == "bad_args"


# ── world_clock ──────────────────────────────────────────────────────────────


def test_world_clock_collects_per_zone_including_errors(enabled, mock_client):
    def _side_effect(tz):
        if tz == "Bad/Zone":
            raise HttpClientError("http_error", "bad zone", status=400)
        return {"timeZone": tz, "time": "12:00", "dayOfWeek": "Monday"}

    mock_client.current_zone.side_effect = _side_effect
    out = _parse(tools.handle_world_clock({"time_zones": ["Asia/Tokyo", "Bad/Zone"]}))
    assert out["success"] is True
    assert out["clocks"][0]["timezone"] == "Asia/Tokyo"
    assert out["clocks"][1]["error"] == "http_error"


# ── public_holidays ──────────────────────────────────────────────────────────


def test_public_holidays_defaults_year_and_slims(enabled, mock_client):
    mock_client.holidays.return_value = [
        {
            "date": "2026-07-04",
            "localName": "Independence Day",
            "name": "Independence Day",
            "global": True,
            "types": ["Public"],
            "counties": None,
        }
    ]
    out = _parse(tools.handle_public_holidays({"country": "us"}))
    assert out["success"] is True
    assert out["country"] == "US"
    assert isinstance(out["year"], int)
    assert out["holidays"][0]["local_name"] == "Independence Day"
    assert "counties" not in out["holidays"][0]
    # year defaulted → client.holidays called with that year + uppercased code.
    assert mock_client.holidays.call_args.args[1] == "us"


def test_public_holidays_rejects_bad_country(enabled, mock_client):
    out = _parse(tools.handle_public_holidays({"country": "USA"}))
    assert out["error"] == "bad_args"
    mock_client.holidays.assert_not_called()
