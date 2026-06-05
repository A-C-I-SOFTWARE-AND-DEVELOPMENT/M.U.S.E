"""branding plugin — registration, key gating, handlers (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.branding as plugin_pkg
import plugins.branding.tools as tools
from plugins.branding import config as branding_config
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        branding_config,
        "load_config",
        lambda: branding_config.BrandingConfig(enabled=True),
    )


def test_register_emits_five_tools_with_two_key_gates():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    by_name = {c["name"]: c for c in captured}
    assert set(by_name) == {
        "color_info",
        "color_scheme",
        "placeholder_image",
        "stock_photo_search",
        "google_fonts",
    }
    assert by_name["stock_photo_search"]["requires_env"] == ["UNSPLASH_ACCESS_KEY"]
    assert by_name["google_fonts"]["requires_env"] == ["GOOGLE_FONTS_API_KEY"]
    assert by_name["color_info"]["requires_env"] == []


def test_key_gates(enabled, monkeypatch):
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_FONTS_API_KEY", raising=False)
    assert tools.check_branding_enabled() is True
    assert tools.check_unsplash_ready() is False
    assert tools.check_google_fonts_ready() is False
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "uk-123456")
    monkeypatch.setenv("GOOGLE_FONTS_API_KEY", "gk-123456")
    assert tools.check_unsplash_ready() is True
    assert tools.check_google_fonts_ready() is True


def test_color_info_slims(enabled, monkeypatch):
    fake = MagicMock()
    fake.color.return_value = {
        "name": {"value": "Flamingo"},
        "hex": {"value": "#FF5733"},
        "rgb": {"value": "rgb(255, 87, 51)"},
        "hsl": {"value": "hsl(11, 100%, 60%)"},
    }
    monkeypatch.setattr(tools, "ColorClient", lambda: fake)
    out = _parse(tools.handle_color_info({"hex": "#FF5733"}))
    assert out["color"]["name"] == "Flamingo"
    assert out["color"]["hex"] == "#FF5733"


def test_color_info_rejects_bad_hex(enabled):
    out = _parse(tools.handle_color_info({"hex": "nothex"}))
    assert out["error"] == "bad_args"


def test_color_scheme_slims(enabled, monkeypatch):
    fake = MagicMock()
    fake.scheme.return_value = {
        "colors": [
            {"hex": {"value": "#FF5733"}, "name": {"value": "Flamingo"}},
            {"hex": {"value": "#33FF57"}, "name": {"value": "Malachite"}},
        ]
    }
    monkeypatch.setattr(tools, "ColorClient", lambda: fake)
    out = _parse(tools.handle_color_scheme({"hex": "FF5733", "mode": "analogic"}))
    assert len(out["colors"]) == 2
    assert out["base"] == "#FF5733"


def test_placeholder_image_builds_url_no_network(enabled):
    out = _parse(
        tools.handle_placeholder_image({
            "width": 400,
            "height": 300,
            "seed": "logo",
            "grayscale": True,
            "blur": 2,
        })
    )
    assert out["success"] is True
    assert out["url"] == "https://picsum.photos/seed/logo/400/300?grayscale&blur=2"


def test_placeholder_image_rejects_bad_size(enabled):
    out = _parse(tools.handle_placeholder_image({"width": 0, "height": 10}))
    assert out["error"] == "bad_args"


def test_stock_photo_hidden_without_key(enabled, monkeypatch):
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    out = _parse(tools.handle_stock_photo_search({"query": "mountains"}))
    assert out["error"] == "no_key"


def test_stock_photo_slims_with_key(enabled, monkeypatch):
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "uk-123456")
    fake = MagicMock()
    fake.has_key.return_value = True
    fake.search.return_value = {
        "total": 1,
        "results": [
            {
                "id": "abc",
                "description": "a mountain",
                "urls": {"regular": "https://img/r", "thumb": "https://img/t"},
                "links": {"html": "https://unsplash/p"},
                "user": {"name": "Jane"},
            }
        ],
    }
    monkeypatch.setattr(tools, "UnsplashClient", lambda: fake)
    out = _parse(tools.handle_stock_photo_search({"query": "mountains"}))
    assert out["photos"][0]["photographer"] == "Jane"


def test_google_fonts_hidden_without_key(enabled, monkeypatch):
    monkeypatch.delenv("GOOGLE_FONTS_API_KEY", raising=False)
    out = _parse(tools.handle_google_fonts({}))
    assert out["error"] == "no_key"


def test_google_fonts_slims_with_key(enabled, monkeypatch):
    monkeypatch.setenv("GOOGLE_FONTS_API_KEY", "gk-123456")
    fake = MagicMock()
    fake.has_key.return_value = True
    fake.fonts.return_value = {
        "items": [
            {
                "family": "Roboto",
                "category": "sans-serif",
                "variants": ["regular", "italic"],
                "subsets": ["latin"],
            }
        ]
    }
    monkeypatch.setattr(tools, "GoogleFontsClient", lambda: fake)
    out = _parse(tools.handle_google_fonts({"sort": "popularity"}))
    assert out["fonts"][0]["family"] == "Roboto"
    assert out["fonts"][0]["variants"] == 2


def test_color_http_error_envelope(enabled, monkeypatch):
    fake = MagicMock()
    fake.color.side_effect = HttpClientError("http_error", "500", status=500)
    monkeypatch.setattr(tools, "ColorClient", lambda: fake)
    out = _parse(tools.handle_color_info({"hex": "FFFFFF"}))
    assert out["error"] == "http_error"
