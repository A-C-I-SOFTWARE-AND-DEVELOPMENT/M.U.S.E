"""image_search plugin — registration, gating, and handler behaviour (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.image_search as plugin_pkg
import plugins.image_search.tools as tools
import plugins.image_search.config as image_config
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        image_config,
        "load_config",
        lambda: image_config.ImageSearchConfig(enabled=True),
    )


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.setattr(
        image_config,
        "load_config",
        lambda: image_config.ImageSearchConfig(enabled=False),
    )


@pytest.fixture
def mock_client(monkeypatch):
    m = MagicMock()
    instance = MagicMock()
    m.return_value = instance
    monkeypatch.setattr(tools, "OpenverseClient", m)
    return instance


def test_register_emits_one_tool():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    assert [c["name"] for c in captured] == ["image_search"]
    assert captured[0]["toolset"] == "image_search"
    assert captured[0]["requires_env"] == []


def test_check_fn_enabled(enabled):
    assert tools.check_image_search_requirements() is True


def test_check_fn_disabled(disabled):
    assert tools.check_image_search_requirements() is False


def test_blocked_when_disabled(disabled):
    assert _parse(tools.handle_image_search({"query": "cat"}))["error"] == "plugin_disabled"


def test_requires_query(enabled):
    assert _parse(tools.handle_image_search({"query": "  "}))["error"] == "bad_args"


def test_parses_openverse_results(enabled, mock_client):
    mock_client.search.return_value = {
        "result_count": 1234,
        "results": [
            {
                "title": "A Pangolin",
                "url": "https://example.org/pangolin.jpg",
                "thumbnail": "https://example.org/pangolin_t.jpg",
                "source": "flickr",
                "creator": "Jane Doe",
                "license": "by",
                "license_version": "2.0",
                "license_url": "https://creativecommons.org/licenses/by/2.0/",
                "foreign_landing_url": "https://flickr.com/photo/1",
                "attribution": "A Pangolin by Jane Doe, CC BY 2.0",
                "width": 1024,
                "height": 768,
            }
        ],
    }
    out = _parse(tools.handle_image_search({"query": "pangolin", "limit": 4}))
    assert out["success"] is True
    assert out["count"] == 1
    assert out["total"] == 1234
    img = out["results"][0]
    assert img["image_url"] == "https://example.org/pangolin.jpg"
    assert img["creator"] == "Jane Doe"
    assert img["license"] == "CC BY 2.0"
    assert img["landing_url"] == "https://flickr.com/photo/1"
    assert img["attribution"].startswith("A Pangolin")
    mock_client.search.assert_called_once_with("pangolin", limit=4)


def test_public_domain_license_label(enabled, mock_client):
    mock_client.search.return_value = {
        "results": [
            {"title": "Old map", "url": "u", "license": "cc0", "license_version": "1.0"},
        ]
    }
    out = _parse(tools.handle_image_search({"query": "map"}))
    assert out["results"][0]["license"] == "CC0"


def test_surfaces_http_error(enabled, mock_client):
    mock_client.search.side_effect = HttpClientError("rate_limited", "slow down", status=429)
    out = _parse(tools.handle_image_search({"query": "x"}))
    assert out["success"] is False
    assert out["error"] == "rate_limited"
    assert out["status"] == 429
