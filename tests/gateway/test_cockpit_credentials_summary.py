"""Tests for multi-provider credentials summary + new provider plugins."""

from __future__ import annotations

import pytest

from gateway.cockpit.handlers import Request, credentials_summary
from hermes_cli.auth import PROVIDER_REGISTRY


@pytest.fixture(autouse=True)
def _clear_keys(monkeypatch):
    for key in (
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "TOGETHER_API_KEY",
        "FIREWORKS_API_KEY",
        "PERPLEXITY_API_KEY",
        "MISTRAL_API_KEY",
        "NIM_API_KEY",
        "NVIDIA_API_KEY",
        "ZHIPU_API_KEY",
        "GLM_API_KEY",
        "MOONSHOT_API_KEY",
        "KIMI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("hermes_cli.auth._load_auth_store", lambda: {})


class TestNewProviderPlugins:
    @pytest.mark.parametrize(
        "provider_id",
        ["groq", "together", "fireworks", "perplexity", "mistral"],
    )
    def test_registered(self, provider_id):
        assert provider_id in PROVIDER_REGISTRY
        assert PROVIDER_REGISTRY[provider_id].auth_type == "api_key"
        assert PROVIDER_REGISTRY[provider_id].inference_base_url

    def test_groq_env(self):
        assert "GROQ_API_KEY" in PROVIDER_REGISTRY["groq"].api_key_env_vars

    def test_mistral_env(self):
        assert "MISTRAL_API_KEY" in PROVIDER_REGISTRY["mistral"].api_key_env_vars


class TestCredentialsSummary:
    def test_summary_lists_providers_without_secrets(self):
        resp = credentials_summary(
            Request(method="GET", path="/v1/cockpit/credentials/summary")
        )
        assert resp.status == 200
        body = resp.payload
        assert "providers" in body
        assert body["total"] >= 5
        # Never leak secret values — only configured bool + env var *names*.
        for row in body["providers"]:
            assert "configured" in row
            assert isinstance(row.get("env_vars"), list)
            assert "api_key" not in row
            assert "token" not in row
            assert "secret" not in row

    def test_summary_marks_configured(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_value")
        resp = credentials_summary(
            Request(method="GET", path="/v1/cockpit/credentials/summary")
        )
        body = resp.payload
        groq = next(p for p in body["providers"] if p["id"] == "groq")
        assert groq["configured"] is True
        assert body["configured_count"] >= 1
