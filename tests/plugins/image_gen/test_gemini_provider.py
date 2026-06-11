#!/usr/bin/env python3
"""Tests for the Google Gemini image generation provider."""

from __future__ import annotations

import base64
import io
import json
from unittest.mock import MagicMock, patch

import pytest

# A 1x1 PNG.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    """Ensure GEMINI_API_KEY is set (and the Google alias unset) for all tests."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-12345")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("HERMES_IMAGE_MODEL", raising=False)


def _gemini_http_response(parts: list[dict]) -> MagicMock:
    """A context-manager mock mimicking urlopen() returning a Gemini body."""
    body = json.dumps({"candidates": [{"content": {"parts": parts}}]}).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value = io.BytesIO(body)
    cm.__exit__.return_value = False
    return cm


# ---------------------------------------------------------------------------
# Provider class tests
# ---------------------------------------------------------------------------


class TestGeminiImageGenProvider:
    def test_name(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        assert GeminiImageGenProvider().name == "gemini"

    def test_display_name(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        assert GeminiImageGenProvider().display_name == "Google Gemini"

    def test_is_available_with_key(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        assert GeminiImageGenProvider().is_available() is True

    def test_is_available_with_google_alias(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "alias-key")
        from plugins.image_gen.gemini import GeminiImageGenProvider

        assert GeminiImageGenProvider().is_available() is True

    def test_is_available_without_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        from plugins.image_gen.gemini import GeminiImageGenProvider

        assert GeminiImageGenProvider().is_available() is False

    def test_default_model(self):
        from plugins.image_gen.gemini import DEFAULT_MODEL, GeminiImageGenProvider

        assert GeminiImageGenProvider().default_model() == DEFAULT_MODEL

    def test_list_models(self):
        from plugins.image_gen.gemini import DEFAULT_MODEL, GeminiImageGenProvider

        models = GeminiImageGenProvider().list_models()
        assert len(models) == 1 and models[0]["id"] == DEFAULT_MODEL

    def test_get_setup_schema(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        schema = GeminiImageGenProvider().get_setup_schema()
        assert schema["name"] == "Google Gemini"
        assert schema["env_vars"][0]["key"] == "GEMINI_API_KEY"


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestConfig:
    def test_default_model(self):
        from plugins.image_gen.gemini import DEFAULT_MODEL, _resolve_model

        assert _resolve_model() == DEFAULT_MODEL

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("GEMINI_IMAGE_MODEL", "gemini-custom")
        from plugins.image_gen.gemini import _resolve_model

        assert _resolve_model() == "gemini-custom"

    def test_legacy_hermes_image_model_env(self, monkeypatch):
        """The room editor's historical knob keeps working through the plugin."""
        monkeypatch.setenv("HERMES_IMAGE_MODEL", "gemini-legacy")
        from plugins.image_gen.gemini import _resolve_model

        assert _resolve_model() == "gemini-legacy"


# ---------------------------------------------------------------------------
# Generate tests
# ---------------------------------------------------------------------------


class TestGenerate:
    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        from plugins.image_gen.gemini import GeminiImageGenProvider

        result = GeminiImageGenProvider().generate(prompt="test")
        assert result["success"] is False
        assert result["error_type"] == "auth_required"
        assert "GEMINI_API_KEY" in result["error"]

    def test_empty_prompt(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        result = GeminiImageGenProvider().generate(prompt="  ")
        assert result["success"] is False
        assert result["error_type"] == "invalid_argument"

    def test_successful_generation(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        parts = [{"inlineData": {"data": base64.b64encode(_PNG).decode("ascii")}}]
        with patch("plugins.image_gen.gemini.urllib.request.urlopen", return_value=_gemini_http_response(parts)):
            with patch("plugins.image_gen.gemini.save_b64_image", return_value="/tmp/gemini.png"):
                result = GeminiImageGenProvider().generate(prompt="a cat")

        assert result["success"] is True
        assert result["image"] == "/tmp/gemini.png"
        assert result["provider"] == "gemini"

    def test_snake_case_inline_data(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        parts = [{"inline_data": {"data": base64.b64encode(_PNG).decode("ascii")}}]
        with patch("plugins.image_gen.gemini.urllib.request.urlopen", return_value=_gemini_http_response(parts)):
            with patch("plugins.image_gen.gemini.save_b64_image", return_value="/tmp/gemini.png"):
                result = GeminiImageGenProvider().generate(prompt="a cat")

        assert result["success"] is True

    def test_request_shape(self):
        """The wire payload preserves the room editor's original request shape."""
        from plugins.image_gen.gemini import GeminiImageGenProvider

        parts = [{"inlineData": {"data": base64.b64encode(_PNG).decode("ascii")}}]
        with patch(
            "plugins.image_gen.gemini.urllib.request.urlopen",
            return_value=_gemini_http_response(parts),
        ) as mock_open:
            with patch("plugins.image_gen.gemini.save_b64_image", return_value="/tmp/x.png"):
                GeminiImageGenProvider().generate(prompt="a cat")

        request = mock_open.call_args[0][0]
        assert ":generateContent?key=test-key-12345" in request.full_url
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["contents"] == [{"parts": [{"text": "a cat"}]}]
        assert payload["generationConfig"] == {"responseModalities": ["TEXT", "IMAGE"]}

    def test_no_image_in_response(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        parts = [{"text": "sorry, no image"}]
        with patch("plugins.image_gen.gemini.urllib.request.urlopen", return_value=_gemini_http_response(parts)):
            result = GeminiImageGenProvider().generate(prompt="a cat")

        assert result["success"] is False
        assert result["error_type"] == "api_error"

    def test_http_error(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        with patch(
            "plugins.image_gen.gemini.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            result = GeminiImageGenProvider().generate(prompt="a cat")

        assert result["success"] is False
        assert result["error_type"] == "api_error"
        assert "connection refused" in result["error"]


# ---------------------------------------------------------------------------
# Registration test
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider, register

        mock_ctx = MagicMock()
        register(mock_ctx)
        mock_ctx.register_image_gen_provider.assert_called_once()
        provider = mock_ctx.register_image_gen_provider.call_args[0][0]
        assert isinstance(provider, GeminiImageGenProvider)
        assert provider.name == "gemini"
