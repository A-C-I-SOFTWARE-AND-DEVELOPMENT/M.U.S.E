#!/usr/bin/env python3
"""Tests for the Meshy text-to-3D provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setenv("MESHY_API_KEY", "test-key-12345")
    # Never actually sleep between polls in tests.
    monkeypatch.setattr("plugins.asset3d_gen.meshy._POLL_INTERVAL_SECONDS", 0)


# ---------------------------------------------------------------------------
# Provider class
# ---------------------------------------------------------------------------


class TestMeshyProvider:
    def test_name(self):
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        assert MeshyAsset3DProvider().name == "meshy"

    def test_display_name(self):
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        assert MeshyAsset3DProvider().display_name == "Meshy"

    def test_is_available_with_key(self, monkeypatch):
        monkeypatch.setenv("MESHY_API_KEY", "sk-xxx")
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        assert MeshyAsset3DProvider().is_available() is True

    def test_is_available_without_key(self, monkeypatch):
        monkeypatch.delenv("MESHY_API_KEY", raising=False)
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        assert MeshyAsset3DProvider().is_available() is False

    def test_list_models(self):
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        models = MeshyAsset3DProvider().list_models()
        assert len(models) >= 1
        assert models[0]["id"] == "meshy-5"

    def test_default_model(self):
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        assert MeshyAsset3DProvider().default_model() == "meshy-5"

    def test_get_setup_schema(self):
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        schema = MeshyAsset3DProvider().get_setup_schema()
        assert schema["name"] == "Meshy (text-to-3D)"
        assert schema["badge"] == "paid"
        assert schema["env_vars"][0]["key"] == "MESHY_API_KEY"


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------


def _create_resp(task_id="task123"):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.json.return_value = {"result": task_id}
    return r


def _poll_resp(status="SUCCEEDED", **extra):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    payload = {"status": status}
    payload.update(extra)
    r.json.return_value = payload
    return r


def _download_resp(content=b"GLB-BINARY-DATA"):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.content = content
    return r


class TestGenerate:
    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("MESHY_API_KEY", raising=False)
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        result = MeshyAsset3DProvider().generate("a crate")
        assert result["success"] is False
        assert result["error_type"] == "missing_api_key"
        assert "MESHY_API_KEY" in result["error"]

    def test_successful_generation(self):
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        poll = _poll_resp(
            status="SUCCEEDED",
            model_urls={"glb": "https://meshy/m.glb", "fbx": "https://meshy/m.fbx"},
            texture_urls=[{"base_color": "https://meshy/albedo.png"}],
            poly_count=24000,
        )
        with patch("plugins.asset3d_gen.meshy.requests.post", return_value=_create_resp()), \
             patch("plugins.asset3d_gen.meshy.requests.get", side_effect=[poll, _download_resp()]), \
             patch("plugins.asset3d_gen.meshy.save_mesh_bytes", return_value="/tmp/test.glb"):
            result = MeshyAsset3DProvider().generate("a weathered crate", fmt="glb")

        assert result["success"] is True
        assert result["mesh"] == "/tmp/test.glb"
        assert result["format"] == "glb"
        assert result["provider"] == "meshy"
        assert result["model"] == "meshy-5"
        assert result["textures"] == ["https://meshy/albedo.png"]
        assert result["poly_count"] == 24000
        assert result["est_cost_usd"] is not None

    def test_format_fallback_when_requested_missing(self):
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        # Request fbx but only glb available -> reflect what we actually got.
        poll = _poll_resp(status="SUCCEEDED", model_urls={"glb": "https://meshy/m.glb"})
        with patch("plugins.asset3d_gen.meshy.requests.post", return_value=_create_resp()), \
             patch("plugins.asset3d_gen.meshy.requests.get", side_effect=[poll, _download_resp()]), \
             patch("plugins.asset3d_gen.meshy.save_mesh_bytes", return_value="/tmp/test.glb"):
            result = MeshyAsset3DProvider().generate("crate", fmt="fbx")

        assert result["success"] is True
        assert result["format"] == "glb"

    def test_download_failure_returns_url(self):
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        poll = _poll_resp(status="SUCCEEDED", model_urls={"glb": "https://meshy/m.glb"})
        with patch("plugins.asset3d_gen.meshy.requests.post", return_value=_create_resp()), \
             patch("plugins.asset3d_gen.meshy.requests.get", side_effect=[poll, _download_resp()]), \
             patch("plugins.asset3d_gen.meshy.save_mesh_bytes", side_effect=OSError("disk full")):
            result = MeshyAsset3DProvider().generate("crate")

        assert result["success"] is True
        assert result["mesh"] == "https://meshy/m.glb"
        assert result.get("cached") is False

    def test_generation_failed_status(self):
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        poll = _poll_resp(status="FAILED", task_error={"message": "nsfw prompt"})
        with patch("plugins.asset3d_gen.meshy.requests.post", return_value=_create_resp()), \
             patch("plugins.asset3d_gen.meshy.requests.get", side_effect=[poll]):
            result = MeshyAsset3DProvider().generate("bad")

        assert result["success"] is False
        assert result["error_type"] == "generation_failed"
        assert "nsfw prompt" in result["error"]

    def test_empty_create_response(self):
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        with patch("plugins.asset3d_gen.meshy.requests.post", return_value=_create_resp(task_id=None)):
            result = MeshyAsset3DProvider().generate("crate")

        assert result["success"] is False
        assert result["error_type"] == "empty_response"

    def test_api_error(self):
        import requests as req_lib
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        resp = MagicMock()
        resp.status_code = 401
        resp.text = "Unauthorized"
        resp.json.return_value = {"message": "Invalid API key"}
        resp.raise_for_status.side_effect = req_lib.HTTPError(response=resp)

        with patch("plugins.asset3d_gen.meshy.requests.post", return_value=resp):
            result = MeshyAsset3DProvider().generate("crate")

        assert result["success"] is False
        assert result["error_type"] == "api_error"
        assert "401" in result["error"]

    def test_timeout(self):
        import requests as req_lib
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        with patch("plugins.asset3d_gen.meshy.requests.post", side_effect=req_lib.Timeout()):
            result = MeshyAsset3DProvider().generate("crate")

        assert result["success"] is False
        assert result["error_type"] == "timeout"

    def test_connection_error(self):
        import requests as req_lib
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        with patch("plugins.asset3d_gen.meshy.requests.post", side_effect=req_lib.ConnectionError("down")):
            result = MeshyAsset3DProvider().generate("crate")

        assert result["success"] is False
        assert result["error_type"] == "connection_error"

    def test_image_to_3d_uses_image_endpoint(self):
        from plugins.asset3d_gen import meshy
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider

        poll = _poll_resp(status="SUCCEEDED", model_urls={"glb": "https://meshy/m.glb"})
        with patch("plugins.asset3d_gen.meshy.requests.post", return_value=_create_resp()) as mock_post, \
             patch("plugins.asset3d_gen.meshy.requests.get", side_effect=[poll, _download_resp()]), \
             patch("plugins.asset3d_gen.meshy.save_mesh_bytes", return_value="/tmp/test.glb"):
            MeshyAsset3DProvider().generate("crate", image="https://example/ref.png")

        called_url = mock_post.call_args[0][0]
        assert called_url == meshy._IMAGE_TO_3D_URL


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register(self):
        from plugins.asset3d_gen.meshy import MeshyAsset3DProvider, register

        ctx = MagicMock()
        register(ctx)
        ctx.register_asset3d_gen_provider.assert_called_once()
        provider = ctx.register_asset3d_gen_provider.call_args[0][0]
        assert isinstance(provider, MeshyAsset3DProvider)
        assert provider.name == "meshy"
