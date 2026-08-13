"""Tests for the curated Ollama Cloud fallback (keeps Gemma 4 selectable)."""

from __future__ import annotations

import hermes_cli.models as models
from hermes_cli.models import _OLLAMA_CLOUD_CURATED, fetch_ollama_cloud_models


def test_gemma4_in_curated_list():
    assert "gemma4:31b" in _OLLAMA_CLOUD_CURATED
    assert "gemma4" in _OLLAMA_CLOUD_CURATED


def test_kimi_k3_in_curated_list():
    assert _OLLAMA_CLOUD_CURATED[0] == "kimi-k3"


def test_curated_fallback_when_discovery_empty(monkeypatch):
    monkeypatch.setattr(models, "_load_ollama_cloud_cache", lambda **kw: None)
    monkeypatch.setattr(models, "fetch_api_models", lambda *a, **k: [])
    monkeypatch.setattr("agent.models_dev.list_agentic_models", lambda *a, **k: [])
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

    result = fetch_ollama_cloud_models(force_refresh=True)
    assert result == list(_OLLAMA_CLOUD_CURATED)
    assert "gemma4" in result


def test_curated_not_appended_when_discovery_succeeds(monkeypatch):
    # Curated is a fallback only — successful discovery is returned untouched.
    saved = {}
    monkeypatch.setattr(models, "_load_ollama_cloud_cache", lambda **kw: None)
    monkeypatch.setattr(models, "fetch_api_models", lambda *a, **k: ["kimi-k2.6"])
    monkeypatch.setattr("agent.models_dev.list_agentic_models", lambda *a, **k: [])
    monkeypatch.setattr(models, "_save_ollama_cloud_cache", lambda m: saved.update(models=m))
    monkeypatch.setenv("OLLAMA_API_KEY", "key")

    result = fetch_ollama_cloud_models(force_refresh=True)
    assert result == ["kimi-k2.6"]
    assert "gemma4" not in result
    assert saved.get("models") == ["kimi-k2.6"]
