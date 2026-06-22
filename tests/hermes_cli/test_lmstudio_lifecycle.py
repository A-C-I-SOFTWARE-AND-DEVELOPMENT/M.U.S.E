"""Tests for LM Studio native v1 model-lifecycle helpers in hermes_cli.models:
unload_lmstudio_model, download_lmstudio_model, lmstudio_download_status.

All hermetic — urllib.request.urlopen is monkeypatched; no network.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse

import pytest

from hermes_cli import models as models_mod


class _FakeResp:
    def __init__(self, body: bytes = b"{}"):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


def _capture_urlopen(monkeypatch, *, body: bytes = b"{}", error: Exception | None = None):
    """Patch models.urllib.request.urlopen; return a list that records requests."""
    seen: list[dict] = []

    def fake_urlopen(req, timeout=None):
        seen.append(
            {
                "url": req.full_url,
                "method": req.get_method(),
                "data": req.data,
                "headers": dict(req.header_items()),
                "timeout": timeout,
            }
        )
        if error is not None:
            raise error
        return _FakeResp(body)

    monkeypatch.setattr(models_mod.urllib.request, "urlopen", fake_urlopen)
    return seen


# ---------------------------------------------------------------------------
# unload_lmstudio_model
# ---------------------------------------------------------------------------

class TestUnloadLmStudioModel:
    def test_success_posts_unload_with_model_body(self, monkeypatch):
        seen = _capture_urlopen(monkeypatch)
        ok = models_mod.unload_lmstudio_model(
            "qwen/qwen3-coder-30b", "http://localhost:1234/v1", "tok"
        )
        assert ok is True
        assert len(seen) == 1
        assert seen[0]["url"] == "http://localhost:1234/api/v1/models/unload"
        assert seen[0]["method"] == "POST"
        assert json.loads(seen[0]["data"]) == {"model": "qwen/qwen3-coder-30b"}

    def test_404_is_idempotent_success(self, monkeypatch):
        err = urllib.error.HTTPError(
            "http://localhost:1234/api/v1/models/unload", 404, "Not Found", {}, None
        )
        _capture_urlopen(monkeypatch, error=err)
        assert models_mod.unload_lmstudio_model("m", "http://localhost:1234/v1", None) is True

    def test_http_500_is_false(self, monkeypatch):
        err = urllib.error.HTTPError(
            "http://localhost:1234/api/v1/models/unload", 500, "Server Error", {}, None
        )
        _capture_urlopen(monkeypatch, error=err)
        assert models_mod.unload_lmstudio_model("m", "http://localhost:1234/v1", None) is False

    def test_network_error_is_false(self, monkeypatch):
        _capture_urlopen(monkeypatch, error=OSError("connection refused"))
        assert models_mod.unload_lmstudio_model("m", "http://localhost:1234/v1", None) is False

    def test_empty_base_url_is_false_without_network(self, monkeypatch):
        seen = _capture_urlopen(monkeypatch)
        assert models_mod.unload_lmstudio_model("m", "", None) is False
        assert seen == []


# ---------------------------------------------------------------------------
# download_lmstudio_model
# ---------------------------------------------------------------------------

class TestDownloadLmStudioModel:
    def test_success_returns_status_dict(self, monkeypatch):
        body = json.dumps(
            {"job_id": "job_123", "status": "downloading", "total_size_bytes": 4096}
        ).encode()
        seen = _capture_urlopen(monkeypatch, body=body)
        result = models_mod.download_lmstudio_model(
            "ibm/granite-4-micro", "http://localhost:1234/v1", "tok"
        )
        assert result == {"job_id": "job_123", "status": "downloading", "total_size_bytes": 4096}
        assert seen[0]["url"] == "http://localhost:1234/api/v1/models/download"
        assert seen[0]["method"] == "POST"
        assert json.loads(seen[0]["data"]) == {"model": "ibm/granite-4-micro"}

    def test_quantization_included_when_given(self, monkeypatch):
        seen = _capture_urlopen(monkeypatch, body=b'{"status": "downloading"}')
        models_mod.download_lmstudio_model(
            "https://huggingface.co/x/y-GGUF",
            "http://localhost:1234/v1",
            None,
            quantization="Q4_K_M",
        )
        assert json.loads(seen[0]["data"]) == {
            "model": "https://huggingface.co/x/y-GGUF",
            "quantization": "Q4_K_M",
        }

    def test_already_downloaded_has_no_job_id(self, monkeypatch):
        _capture_urlopen(monkeypatch, body=b'{"status": "already_downloaded"}')
        result = models_mod.download_lmstudio_model("m", "http://localhost:1234/v1", None)
        assert result == {"status": "already_downloaded"}
        assert "job_id" not in result

    def test_empty_base_url_is_none(self, monkeypatch):
        seen = _capture_urlopen(monkeypatch)
        assert models_mod.download_lmstudio_model("m", "", None) is None
        assert seen == []

    def test_network_error_is_none(self, monkeypatch):
        _capture_urlopen(monkeypatch, error=OSError("boom"))
        assert models_mod.download_lmstudio_model("m", "http://localhost:1234/v1", None) is None


# ---------------------------------------------------------------------------
# lmstudio_download_status
# ---------------------------------------------------------------------------

class TestLmStudioDownloadStatus:
    def test_success_gets_status_with_job_id_query(self, monkeypatch):
        body = json.dumps({"status": "downloading", "progress": 0.42}).encode()
        seen = _capture_urlopen(monkeypatch, body=body)
        result = models_mod.lmstudio_download_status(
            "job_123", "http://localhost:1234/v1", "tok"
        )
        assert result == {"status": "downloading", "progress": 0.42}
        assert seen[0]["method"] == "GET"
        parsed = urllib.parse.urlparse(seen[0]["url"])
        assert parsed.path == "/api/v1/models/download/status"
        assert urllib.parse.parse_qs(parsed.query)["job_id"] == ["job_123"]

    def test_empty_job_id_is_none_without_network(self, monkeypatch):
        seen = _capture_urlopen(monkeypatch)
        assert models_mod.lmstudio_download_status("", "http://localhost:1234/v1", None) is None
        assert seen == []

    def test_empty_base_url_is_none(self, monkeypatch):
        seen = _capture_urlopen(monkeypatch)
        assert models_mod.lmstudio_download_status("job_1", "", None) is None
        assert seen == []

    def test_network_error_is_none(self, monkeypatch):
        _capture_urlopen(monkeypatch, error=OSError("boom"))
        assert models_mod.lmstudio_download_status("job_1", "http://localhost:1234/v1", None) is None
