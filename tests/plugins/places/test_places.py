"""places plugin — registration, gating, and handler behaviour (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.places as plugin_pkg
import plugins.places.tools as tools
import plugins.places.config as places_config
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        places_config, "load_config", lambda: places_config.PlacesConfig(enabled=True)
    )


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.setattr(
        places_config, "load_config", lambda: places_config.PlacesConfig(enabled=False)
    )


@pytest.fixture
def mock_client(monkeypatch):
    m = MagicMock()
    instance = MagicMock()
    m.return_value = instance
    monkeypatch.setattr(tools, "PlacesClient", m)
    return instance


# ── registration ─────────────────────────────────────────────────────────────


def test_register_emits_two_places_tools():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    assert [c["name"] for c in captured] == ["places_search", "places_map"]
    assert all(c["toolset"] == "places" for c in captured)
    assert all(c["requires_env"] == [] for c in captured)


# ── gating ───────────────────────────────────────────────────────────────────


def test_check_fn_follows_enabled(enabled):
    assert tools.check_places_requirements() is True


def test_check_fn_follows_disabled(disabled):
    assert tools.check_places_requirements() is False


def test_handlers_blocked_when_disabled(disabled):
    assert _parse(tools.handle_search({"query": "x"}))["error"] == "plugin_disabled"
    assert _parse(tools.handle_map({"locations": [{"latitude": 1, "longitude": 2}]}))[
        "error"
    ] == "plugin_disabled"


# ── places_search ─────────────────────────────────────────────────────────────


def test_search_parses_nominatim_results(enabled, mock_client):
    mock_client.search.return_value = [
        {
            "name": "Eiffel Tower",
            "display_name": "Eiffel Tower, Paris, France",
            "lat": "48.8584",
            "lon": "2.2945",
            "category": "tourism",
            "type": "attraction",
            "osm_type": "way",
            "osm_id": 5013364,
            "address": {"city": "Paris", "country": "France"},
            "importance": 0.8,
        }
    ]
    out = _parse(tools.handle_search({"query": "Eiffel Tower", "limit": 3}))
    assert out["success"] is True
    assert out["count"] == 1
    r = out["results"][0]
    assert r["name"] == "Eiffel Tower"
    assert r["latitude"] == pytest.approx(48.8584)
    assert r["longitude"] == pytest.approx(2.2945)
    assert r["osm_url"] == "https://www.openstreetmap.org/way/5013364"
    assert r["address"]["country"] == "France"
    mock_client.search.assert_called_once_with("Eiffel Tower", limit=3)


def test_search_skips_rows_without_coordinates(enabled, mock_client):
    mock_client.search.return_value = [
        {"display_name": "no coords"},
        {"display_name": "ok", "lat": "1.0", "lon": "2.0"},
    ]
    out = _parse(tools.handle_search({"query": "x"}))
    assert out["count"] == 1
    assert out["results"][0]["latitude"] == pytest.approx(1.0)


def test_search_requires_query(enabled):
    assert _parse(tools.handle_search({"query": "  "}))["error"] == "bad_args"


def test_search_surfaces_http_error(enabled, mock_client):
    mock_client.search.side_effect = HttpClientError("network", "down", status=503)
    out = _parse(tools.handle_search({"query": "x"}))
    assert out["success"] is False
    assert out["error"] == "network"
    assert out["status"] == 503


# ── places_map (pure, no network) ─────────────────────────────────────────────


def test_map_single_point_has_no_directions(enabled):
    out = _parse(tools.handle_map({"locations": [{"name": "A", "latitude": 10.0, "longitude": 20.0}]}))
    assert out["success"] is True
    assert out["directions_url"] is None
    assert len(out["markers"]) == 1
    assert out["markers"][0]["osm_url"].startswith("https://www.openstreetmap.org/?mlat=10.0")
    assert out["zoom"] == 15


def test_map_multi_point_builds_directions(enabled):
    out = _parse(
        tools.handle_map(
            {
                "locations": [
                    {"latitude": 1.0, "longitude": 2.0},
                    {"latitude": 3.0, "longitude": 4.0},
                ],
                "travel_mode": "walking",
            }
        )
    )
    assert out["center"]["latitude"] == pytest.approx(2.0)
    assert out["center"]["longitude"] == pytest.approx(3.0)
    assert "fossgis_osrm_foot" in out["directions_url"]
    assert "route=1.0,2.0;3.0,4.0" in out["directions_url"]


def test_map_defaults_to_driving_engine(enabled):
    out = _parse(
        tools.handle_map(
            {"locations": [{"latitude": 1.0, "longitude": 2.0}, {"latitude": 3.0, "longitude": 4.0}]}
        )
    )
    assert "fossgis_osrm_car" in out["directions_url"]


def test_map_requires_valid_locations(enabled):
    assert _parse(tools.handle_map({"locations": []}))["error"] == "bad_args"
    assert _parse(tools.handle_map({"locations": [{"name": "no coords"}]}))["error"] == "bad_args"
