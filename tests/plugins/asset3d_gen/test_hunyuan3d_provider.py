#!/usr/bin/env python3
"""Tests for the Hunyuan3D (Replicate) text/image-to-3D provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _fake_token(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_test")
    monkeypatch.setattr("plugins.asset3d_gen.hunyuan3d._POLL_INTERVAL_SECONDS", 0)


def _resp(payload, content=None):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    if payload is not None:
        r.json.return_value = payload
    if content is not None:
        r.content = content
    return r


class TestProvider:
    def test_name_and_display(self):
        from plugins.asset3d_gen.hunyuan3d import Hunyuan3DAsset3DProvider

        p = Hunyuan3DAsset3DProvider()
        assert p.name == "hunyuan3d"
        assert "Hunyuan3D" in p.display_name

    def test_available_requires_token(self, monkeypatch):
        from plugins.asset3d_gen.hunyuan3d import Hunyuan3DAsset3DProvider

        monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
        assert Hunyuan3DAsset3DProvider().is_available() is False

    def test_default_model(self):
        from plugins.asset3d_gen.hunyuan3d import Hunyuan3DAsset3DProvider

        assert Hunyuan3DAsset3DProvider().default_model() == "hunyuan3d-2"

    def test_setup_schema(self):
        from plugins.asset3d_gen.hunyuan3d import Hunyuan3DAsset3DProvider

        schema = Hunyuan3DAsset3DProvider().get_setup_schema()
        assert schema["env_vars"][0]["key"] == "REPLICATE_API_TOKEN"


class TestGenerate:
    def test_missing_token(self, monkeypatch):
        from plugins.asset3d_gen.hunyuan3d import Hunyuan3DAsset3DProvider

        monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
        out = Hunyuan3DAsset3DProvider().generate("crate", image="http://x/ref.png")
        assert out["success"] is False
        assert out["error_type"] == "missing_api_key"

    def test_missing_image(self):
        from plugins.asset3d_gen.hunyuan3d import Hunyuan3DAsset3DProvider

        out = Hunyuan3DAsset3DProvider().generate("crate")
        assert out["success"] is False
        assert out["error_type"] == "missing_input"

    def test_success_via_polling(self):
        from plugins.asset3d_gen.hunyuan3d import Hunyuan3DAsset3DProvider

        create = _resp({"id": "p1", "status": "starting", "urls": {"get": "http://poll"}})
        poll = _resp({"id": "p1", "status": "succeeded", "output": "http://mesh.glb"})
        download = _resp(None, content=b"GLB")
        with patch("plugins.asset3d_gen.hunyuan3d.requests.post", return_value=create), \
             patch("plugins.asset3d_gen.hunyuan3d.requests.get", side_effect=[poll, download]), \
             patch("plugins.asset3d_gen.hunyuan3d.save_mesh_bytes", return_value="/tmp/h.glb"):
            out = Hunyuan3DAsset3DProvider().generate("crate", image="http://x/ref.png")
        assert out["success"] is True
        assert out["mesh"] == "/tmp/h.glb"
        assert out["provider"] == "hunyuan3d"

    def test_failed_status(self):
        from plugins.asset3d_gen.hunyuan3d import Hunyuan3DAsset3DProvider

        create = _resp({"id": "p1", "status": "starting", "urls": {"get": "http://poll"}})
        poll = _resp({"id": "p1", "status": "failed", "error": "bad input"})
        with patch("plugins.asset3d_gen.hunyuan3d.requests.post", return_value=create), \
             patch("plugins.asset3d_gen.hunyuan3d.requests.get", side_effect=[poll]):
            out = Hunyuan3DAsset3DProvider().generate("crate", image="http://x/ref.png")
        assert out["success"] is False
        assert out["error_type"] == "generation_failed"

    def test_output_list_form(self):
        from plugins.asset3d_gen.hunyuan3d import Hunyuan3DAsset3DProvider

        create = _resp({"id": "p1", "status": "succeeded", "output": ["http://mesh.glb"],
                        "urls": {"get": "http://poll"}})
        download = _resp(None, content=b"GLB")
        with patch("plugins.asset3d_gen.hunyuan3d.requests.post", return_value=create), \
             patch("plugins.asset3d_gen.hunyuan3d.requests.get", side_effect=[download]), \
             patch("plugins.asset3d_gen.hunyuan3d.save_mesh_bytes", return_value="/tmp/h.glb"):
            out = Hunyuan3DAsset3DProvider().generate("crate", image="http://x/ref.png")
        assert out["success"] is True


class TestRegistration:
    def test_register(self):
        from plugins.asset3d_gen.hunyuan3d import Hunyuan3DAsset3DProvider, register

        ctx = MagicMock()
        register(ctx)
        ctx.register_asset3d_gen_provider.assert_called_once()
        provider = ctx.register_asset3d_gen_provider.call_args[0][0]
        assert isinstance(provider, Hunyuan3DAsset3DProvider)
