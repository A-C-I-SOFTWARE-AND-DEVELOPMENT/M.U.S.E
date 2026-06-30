"""The studio mesh3d stage unifies with the muse Asset3DGenProvider registry.

Default behaviour (no asset3d_gen.provider configured) is unchanged — the legacy
Replicate path runs. When the operator explicitly selects a provider, the studio
stage delegates to it.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.studio.adapters import Mesh3DAdapter, _explicit_asset3d_provider


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("AXIOM_STUDIO_OFFLINE", "REPLICATE_API_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    yield


def test_explicit_provider_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {})
    assert _explicit_asset3d_provider() is None


def test_explicit_provider_none_when_offline(monkeypatch):
    monkeypatch.setenv("AXIOM_STUDIO_OFFLINE", "1")
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {"asset3d_gen": {"provider": "meshy"}})
    assert _explicit_asset3d_provider() is None


def test_unconfigured_stays_stub_without_token(monkeypatch):
    # No token, no explicit provider → adapter is not "available" → stub path.
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {})
    assert Mesh3DAdapter().available() is False


def test_explicit_provider_makes_adapter_available(monkeypatch):
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {"asset3d_gen": {"provider": "meshy"}})
    stub = MagicMock()
    with patch("agent.asset3d_gen_registry.get_active_provider", return_value=stub), \
         patch("hermes_cli.plugins._ensure_plugins_discovered", lambda *a, **k: None):
        assert Mesh3DAdapter().available() is True


def test_real_delegates_to_provider(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {"asset3d_gen": {"provider": "meshy"}})
    fake = MagicMock()
    fake.name = "meshy"
    fake.generate.return_value = {
        "success": True, "mesh": "/tmp/none.glb", "format": "glb",
        "provider": "meshy", "textures": [], "poly_count": 1234, "est_cost_usd": 0.1,
    }
    with patch("agent.asset3d_gen_registry.get_active_provider", return_value=fake), \
         patch("hermes_cli.plugins._ensure_plugins_discovered", lambda *a, **k: None):
        artifacts, notes = Mesh3DAdapter()._real("a crate", tmp_path)
    fake.generate.assert_called_once()
    assert "meshy" in notes
    # A manifest is always written; mesh path only surfaced if it exists on disk.
    assert any(a.endswith(".json") for a in artifacts)


def test_real_raises_on_provider_failure(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {"asset3d_gen": {"provider": "meshy"}})
    fake = MagicMock()
    fake.name = "meshy"
    fake.generate.return_value = {"success": False, "error": "no credits", "mesh": None}
    with patch("agent.asset3d_gen_registry.get_active_provider", return_value=fake), \
         patch("hermes_cli.plugins._ensure_plugins_discovered", lambda *a, **k: None):
        with pytest.raises(RuntimeError, match="no credits"):
            Mesh3DAdapter()._real("a crate", tmp_path)


def test_legacy_path_used_without_explicit_provider(tmp_path: Path, monkeypatch):
    # Token set, no explicit provider → legacy Replicate path (mock the HTTP).
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_x")
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {})
    with patch("agent.studio.adapters._post_json", return_value={"id": "p1"}) as mock_post:
        artifacts, notes = Mesh3DAdapter()._real("a crate", tmp_path)
    mock_post.assert_called_once()
    assert "hunyuan3d-2 mesh queued" in notes
