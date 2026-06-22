"""Tests for the LM Studio lifecycle agent tools (tools/lmstudio_tools.py).

Hermetic — the underlying hermes_cli.models helpers are monkeypatched; no
network. Handlers are exercised directly and via the global tool registry.
"""

from __future__ import annotations

import json

import pytest

from tools import lmstudio_tools as lt


# ---------------------------------------------------------------------------
# connection resolution
# ---------------------------------------------------------------------------

class TestResolveConnection:
    def test_default_when_nothing_set(self, monkeypatch):
        monkeypatch.delenv("LM_BASE_URL", raising=False)
        monkeypatch.delenv("LM_API_KEY", raising=False)
        base_url, api_key = lt._resolve_lmstudio_connection({})
        assert base_url == "http://127.0.0.1:1234/v1"
        assert api_key == ""

    def test_env_overrides_default(self, monkeypatch):
        monkeypatch.setenv("LM_BASE_URL", "http://10.0.0.5:1234/v1")
        monkeypatch.setenv("LM_API_KEY", "secret")
        base_url, api_key = lt._resolve_lmstudio_connection({})
        assert base_url == "http://10.0.0.5:1234/v1"
        assert api_key == "secret"

    def test_arg_base_url_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("LM_BASE_URL", "http://10.0.0.5:1234/v1")
        base_url, _ = lt._resolve_lmstudio_connection({"base_url": "http://host:9999/v1"})
        assert base_url == "http://host:9999/v1"

    def test_api_key_never_from_args(self, monkeypatch):
        # A model-supplied api_key must be ignored — keys come from env only.
        monkeypatch.delenv("LM_API_KEY", raising=False)
        _, api_key = lt._resolve_lmstudio_connection({"api_key": "injected"})
        assert api_key == ""


# ---------------------------------------------------------------------------
# check_fn gating
# ---------------------------------------------------------------------------

class TestCheckAvailable:
    def test_true_when_reachable(self, monkeypatch):
        monkeypatch.setattr("hermes_cli.models.probe_lmstudio_models", lambda **kw: [])
        assert lt.check_lmstudio_available() is True

    def test_false_when_unreachable(self, monkeypatch):
        monkeypatch.setattr("hermes_cli.models.probe_lmstudio_models", lambda **kw: None)
        assert lt.check_lmstudio_available() is False

    def test_false_when_probe_raises(self, monkeypatch):
        def boom(**kw):
            raise RuntimeError("auth")
        monkeypatch.setattr("hermes_cli.models.probe_lmstudio_models", boom)
        assert lt.check_lmstudio_available() is False


# ---------------------------------------------------------------------------
# download handler
# ---------------------------------------------------------------------------

class TestDownloadHandler:
    def test_success(self, monkeypatch):
        calls = {}

        def fake_dl(model, base_url, api_key, quantization=None):
            calls.update(model=model, base_url=base_url, api_key=api_key, quant=quantization)
            return {"job_id": "job_1", "status": "downloading"}

        monkeypatch.setattr("hermes_cli.models.download_lmstudio_model", fake_dl)
        monkeypatch.delenv("LM_BASE_URL", raising=False)
        out = json.loads(lt.handle_download_model({"model": "ibm/granite-4-micro"}))
        assert out["success"] is True
        assert out["result"] == {"job_id": "job_1", "status": "downloading"}
        assert calls["model"] == "ibm/granite-4-micro"
        assert calls["base_url"] == "http://127.0.0.1:1234/v1"
        assert calls["quant"] is None

    def test_quantization_passed_through(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            "hermes_cli.models.download_lmstudio_model",
            lambda model, base_url, api_key, quantization=None: seen.update(q=quantization) or {"status": "downloading"},
        )
        lt.handle_download_model({"model": "https://huggingface.co/x/y", "quantization": "Q4_K_M"})
        assert seen["q"] == "Q4_K_M"

    def test_missing_model_is_error(self):
        out = json.loads(lt.handle_download_model({}))
        assert "error" in out

    def test_helper_failure_is_error(self, monkeypatch):
        monkeypatch.setattr("hermes_cli.models.download_lmstudio_model", lambda *a, **k: None)
        out = json.loads(lt.handle_download_model({"model": "m"}))
        assert "error" in out


# ---------------------------------------------------------------------------
# status handler
# ---------------------------------------------------------------------------

class TestStatusHandler:
    def test_success(self, monkeypatch):
        monkeypatch.setattr(
            "hermes_cli.models.lmstudio_download_status",
            lambda job_id, base_url, api_key: {"status": "downloading", "progress": 0.5},
        )
        out = json.loads(lt.handle_download_status({"job_id": "job_1"}))
        assert out == {"success": True, "result": {"status": "downloading", "progress": 0.5}}

    def test_missing_job_id_is_error(self):
        assert "error" in json.loads(lt.handle_download_status({}))

    def test_helper_failure_is_error(self, monkeypatch):
        monkeypatch.setattr("hermes_cli.models.lmstudio_download_status", lambda *a, **k: None)
        assert "error" in json.loads(lt.handle_download_status({"job_id": "x"}))


# ---------------------------------------------------------------------------
# unload handler
# ---------------------------------------------------------------------------

class TestUnloadHandler:
    def test_success(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            "hermes_cli.models.unload_lmstudio_model",
            lambda model, base_url, api_key: seen.update(model=model) or True,
        )
        out = json.loads(lt.handle_unload_model({"model": "qwen/q3"}))
        assert out == {"success": True, "model": "qwen/q3"}
        assert seen["model"] == "qwen/q3"

    def test_unload_failure_reports_false(self, monkeypatch):
        monkeypatch.setattr("hermes_cli.models.unload_lmstudio_model", lambda *a, **k: False)
        out = json.loads(lt.handle_unload_model({"model": "m"}))
        assert out == {"success": False, "model": "m"}

    def test_missing_model_is_error(self):
        assert "error" in json.loads(lt.handle_unload_model({}))


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

class TestRegistration:
    @pytest.mark.parametrize(
        "name",
        ["lmstudio_download_model", "lmstudio_download_status", "lmstudio_unload_model"],
    )
    def test_tool_registered_with_gate(self, name):
        from tools.registry import registry

        entry = registry.get_entry(name)
        assert entry is not None
        assert entry.toolset == "lmstudio"
        assert entry.check_fn is lt.check_lmstudio_available

    def test_dispatch_routes_to_handler(self, monkeypatch):
        from tools.registry import registry

        monkeypatch.setattr("hermes_cli.models.unload_lmstudio_model", lambda *a, **k: True)
        out = json.loads(registry.dispatch("lmstudio_unload_model", {"model": "m"}))
        assert out == {"success": True, "model": "m"}
