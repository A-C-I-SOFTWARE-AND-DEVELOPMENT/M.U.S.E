"""devtools plugin — registration, gating, handlers (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.devtools as plugin_pkg
import plugins.devtools.tools as tools
from plugins.devtools import config as devtools_config
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        devtools_config,
        "load_config",
        lambda: devtools_config.DevtoolsConfig(enabled=True),
    )


@pytest.fixture
def mock_client(monkeypatch):
    m = MagicMock()
    instance = MagicMock()
    m.return_value = instance
    monkeypatch.setattr(tools, "DevtoolsClient", m)
    return instance


def test_register_emits_four_tools():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    assert [c["name"] for c in captured] == [
        "pypi_package",
        "npm_package",
        "crates_package",
        "stackoverflow_search",
    ]
    assert all(c["toolset"] == "devtools" for c in captured)
    assert all(c["requires_env"] == [] for c in captured)


def test_disabled_blocks(monkeypatch, mock_client):
    monkeypatch.setattr(
        devtools_config,
        "load_config",
        lambda: devtools_config.DevtoolsConfig(enabled=False),
    )
    out = _parse(tools.handle_pypi_package({"name": "requests"}))
    assert out["error"] == "plugin_disabled"
    mock_client.pypi.assert_not_called()


def test_pypi_slims_info(enabled, mock_client):
    mock_client.pypi.return_value = {
        "info": {
            "name": "requests",
            "version": "2.32.0",
            "summary": "HTTP for Humans",
            "license": "Apache-2.0",
            "requires_python": ">=3.8",
            "home_page": "https://requests.readthedocs.io",
        },
        "releases": {"2.31.0": [], "2.32.0": []},
    }
    out = _parse(tools.handle_pypi_package({"name": "requests"}))
    assert out["success"] is True
    assert out["package"]["version"] == "2.32.0"
    assert out["package"]["release_count"] == 2


def test_npm_uses_dist_tags_latest(enabled, mock_client):
    mock_client.npm.return_value = {
        "name": "express",
        "dist-tags": {"latest": "5.0.0"},
        "description": "web framework",
        "license": "MIT",
        "versions": {"4.0.0": {}, "5.0.0": {}},
    }
    out = _parse(tools.handle_npm_package({"name": "express"}))
    assert out["package"]["version"] == "5.0.0"
    assert out["package"]["version_count"] == 2


def test_crates_pulls_license_from_versions(enabled, mock_client):
    mock_client.crates.return_value = {
        "crate": {
            "name": "serde",
            "max_stable_version": "1.0.200",
            "description": "serialization",
            "downloads": 999,
            "repository": "https://github.com/serde-rs/serde",
        },
        "versions": [{"license": "MIT OR Apache-2.0"}],
    }
    out = _parse(tools.handle_crates_package({"name": "serde"}))
    assert out["crate"]["max_version"] == "1.0.200"
    assert out["crate"]["license"] == "MIT OR Apache-2.0"


def test_stackoverflow_slims_items(enabled, mock_client):
    mock_client.stackoverflow.return_value = {
        "quota_remaining": 295,
        "items": [
            {
                "title": "How to X?",
                "score": 42,
                "is_answered": True,
                "answer_count": 3,
                "tags": ["python"],
                "link": "https://stackoverflow.com/q/1",
                "owner": {"display_name": "noise"},
            }
        ],
    }
    out = _parse(tools.handle_stackoverflow_search({"query": "how to x", "limit": 1}))
    assert out["success"] is True
    assert out["questions"][0]["score"] == 42
    assert "owner" not in out["questions"][0]


def test_bad_args(enabled, mock_client):
    assert _parse(tools.handle_pypi_package({}))["error"] == "bad_args"
    assert _parse(tools.handle_stackoverflow_search({}))["error"] == "bad_args"


def test_http_error_envelope(enabled, mock_client):
    mock_client.pypi.side_effect = HttpClientError("http_error", "404", status=404)
    out = _parse(tools.handle_pypi_package({"name": "nope"}))
    assert out["error"] == "http_error"
    assert out["status"] == 404
