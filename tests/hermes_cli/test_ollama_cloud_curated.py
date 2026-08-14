"""Tests for the curated Ollama Cloud fallback (keeps Gemma 4 selectable)."""

from __future__ import annotations

import hermes_cli.models as models
from hermes_cli.models import (
    _OLLAMA_CLOUD_CURATED,
    _OLLAMA_CLOUD_RETIRED,
    fetch_ollama_cloud_models,
)


def test_gemma4_in_curated_list():
    assert "gemma4:31b" in _OLLAMA_CLOUD_CURATED
    assert "gemma4" in _OLLAMA_CLOUD_CURATED


def test_curated_has_current_cloud_headlines():
    # Live catalog as of 2026-08 — retired IDs must not be in the fallback.
    for required in (
        "qwen3.5:397b",
        "gpt-oss:120b",
        "deepseek-v4-pro",
        "glm-5.2",
        "minimax-m3",
        "kimi-k3",
        "nemotron-3-ultra",
    ):
        assert required in _OLLAMA_CLOUD_CURATED, required
    for retired in (
        "qwen3-coder:480b",
        "deepseek-v3.1:671b",
        "kimi-k2.5",
        "minimax-m2.5",
        "deepseek-v4-flash",
    ):
        assert retired not in _OLLAMA_CLOUD_CURATED, retired
        assert retired in _OLLAMA_CLOUD_RETIRED, retired


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


def test_retired_models_stripped_from_merge(monkeypatch):
    saved = {}
    monkeypatch.setattr(models, "_load_ollama_cloud_cache", lambda **kw: None)
    monkeypatch.setattr(
        models,
        "fetch_api_models",
        lambda *a, **k: ["kimi-k3", "minimax-m2.5", "deepseek-v4-flash"],
    )
    monkeypatch.setattr(
        "agent.models_dev.list_agentic_models",
        lambda *a, **k: ["qwen3-coder:480b-cloud", "glm-5.2:cloud"],
    )
    monkeypatch.setattr(models, "_save_ollama_cloud_cache", lambda m: saved.update(models=m))
    monkeypatch.setenv("OLLAMA_API_KEY", "key")

    result = fetch_ollama_cloud_models(force_refresh=True)
    assert result == ["kimi-k3", "glm-5.2"]
    assert "minimax-m2.5" not in result
    assert "deepseek-v4-flash" not in result
    assert "qwen3-coder:480b" not in result
    assert saved.get("models") == ["kimi-k3", "glm-5.2"]


def test_retired_models_stripped_from_stale_cache(monkeypatch):
    monkeypatch.setattr(
        models,
        "_load_ollama_cloud_cache",
        lambda **kw: {"models": ["kimi-k3", "kimi-k2.5", "minimax-m2.5"]},
    )
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

    result = fetch_ollama_cloud_models(force_refresh=False)
    assert result == ["kimi-k3"]
