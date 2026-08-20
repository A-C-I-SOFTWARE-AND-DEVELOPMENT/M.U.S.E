"""webutils plugin — registration, gating, handlers (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.webutils as plugin_pkg
import plugins.webutils.tools as tools
from plugins.webutils import config as webutils_config
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        webutils_config,
        "load_config",
        lambda: webutils_config.WebutilsConfig(enabled=True),
    )


@pytest.fixture
def mock_client(monkeypatch):
    m = MagicMock()
    instance = MagicMock()
    m.return_value = instance
    monkeypatch.setattr(tools, "WebutilsClient", m)
    return instance


def test_register_emits_four_tools():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    assert [c["name"] for c in captured] == [
        "qr_code",
        "ip_info",
        "public_ip",
        "sunrise_sunset",
    ]
    assert all(c["toolset"] == "webutils" for c in captured)


def test_disabled_blocks(monkeypatch, mock_client):
    monkeypatch.setattr(
        webutils_config,
        "load_config",
        lambda: webutils_config.WebutilsConfig(enabled=False),
    )
    out = _parse(tools.handle_public_ip({}))
    assert out["error"] == "plugin_disabled"
    mock_client.public_ip.assert_not_called()


def test_qr_code_builds_url_no_network(enabled, mock_client):
    out = _parse(tools.handle_qr_code({"data": "https://example.com", "size": 300}))
    assert out["success"] is True
    # Assert the exact constructed URL (the data is percent-encoded).
    assert out["url"] == (
        "https://api.qrserver.com/v1/create-qr-code/"
        "?size=300x300&data=https%3A%2F%2Fexample.com"
    )
    assert out["size"] == 300
    # qr_code must not touch the network client.
    mock_client.public_ip.assert_not_called()


def test_qr_code_rejects_empty_data(enabled, mock_client):
    out = _parse(tools.handle_qr_code({"data": ""}))
    assert out["error"] == "bad_args"


def test_ip_info_slims(enabled, mock_client):
    mock_client.ip_info.return_value = {
        "ip": "8.8.8.8",
        "city": "Mountain View",
        "region": "California",
        "country_name": "United States",
        "country_code": "US",
        "org": "AS15169 Google LLC",
        "latitude": 37.4,
        "longitude": -122.0,
        "timezone": "America/Los_Angeles",
    }
    out = _parse(tools.handle_ip_info({"ip": "8.8.8.8"}))
    assert out["city"] == "Mountain View"
    assert out["country"] == "United States"


def test_ip_info_error_payload_is_not_found(enabled, mock_client):
    mock_client.ip_info.return_value = {"error": True, "reason": "invalid IP"}
    out = _parse(tools.handle_ip_info({"ip": "999.999"}))
    assert out["error"] == "not_found"


def test_public_ip(enabled, mock_client):
    mock_client.public_ip.return_value = {"ip": "203.0.113.5"}
    out = _parse(tools.handle_public_ip({}))
    assert out["ip"] == "203.0.113.5"


def test_sunrise_sunset_slims(enabled, mock_client):
    mock_client.sunrise_sunset.return_value = {
        "results": {
            "date": "2026-06-05",
            "sunrise": "6:00:00 AM",
            "sunset": "8:30:00 PM",
            "day_length": "14:30:00",
            "timezone": "America/Chicago",
        }
    }
    out = _parse(tools.handle_sunrise_sunset({"latitude": 30.27, "longitude": -97.74}))
    assert out["results"]["sunrise"] == "6:00:00 AM"


def test_sunrise_sunset_requires_coords(enabled, mock_client):
    out = _parse(tools.handle_sunrise_sunset({"latitude": 1}))
    assert out["error"] == "bad_args"
    mock_client.sunrise_sunset.assert_not_called()


def test_http_error_envelope(enabled, mock_client):
    mock_client.public_ip.side_effect = HttpClientError("timeout", "request timed out")
    out = _parse(tools.handle_public_ip({}))
    assert out["error"] == "timeout"
