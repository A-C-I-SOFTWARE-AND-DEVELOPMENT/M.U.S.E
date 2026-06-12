"""Tests for the stdlib model bridge and the live-audit runner script.

Deterministic: the HTTP call is monkeypatched and the runner uses an in-process
model override, so nothing reaches the network.
"""

import importlib.util
import json
import urllib.request
from pathlib import Path

from muse_cli.jarvis_prime.self_audit import live, model_bridge


def test_build_request_shape():
    url, data, headers = model_bridge.build_request(
        "hi", base_url="https://x/v1/", model="m", api_key="k"
    )
    assert url == "https://x/v1/chat/completions"
    payload = json.loads(data)
    assert payload["model"] == "m"
    assert payload["messages"] == [{"role": "user", "content": "hi"}]
    assert headers["Authorization"] == "Bearer k"


def test_build_request_without_key_omits_auth():
    _url, _data, headers = model_bridge.build_request(
        "hi", base_url="https://x/v1", model="m"
    )
    assert "Authorization" not in headers


def test_parse_completion():
    body = json.dumps({"choices": [{"message": {"content": "hello"}}]})
    assert model_bridge.parse_completion(body) == "hello"


def test_is_configured(monkeypatch):
    monkeypatch.delenv(model_bridge.ENV_BASE_URL, raising=False)
    monkeypatch.delenv(model_bridge.ENV_MODEL, raising=False)
    assert not model_bridge.is_configured()
    monkeypatch.setenv(model_bridge.ENV_BASE_URL, "https://x/v1")
    monkeypatch.setenv(model_bridge.ENV_MODEL, "m")
    assert model_bridge.is_configured()


def test_complete_uses_urlopen(monkeypatch):
    monkeypatch.setenv(model_bridge.ENV_BASE_URL, "https://x/v1")
    monkeypatch.setenv(model_bridge.ENV_MODEL, "m")
    monkeypatch.delenv(model_bridge.ENV_KEY, raising=False)

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode("utf-8")

    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert model_bridge.complete("ping") == "OK"
    assert captured["url"].endswith("/chat/completions")


def test_complete_raises_when_unconfigured(monkeypatch):
    monkeypatch.delenv(model_bridge.ENV_BASE_URL, raising=False)
    monkeypatch.delenv(model_bridge.ENV_MODEL, raising=False)
    raised = False
    try:
        model_bridge.complete("x")
    except RuntimeError:
        raised = True
    assert raised


def _load_runner(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / "jarvis_self_audit_live.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_skips_without_model(monkeypatch):
    monkeypatch.delenv(model_bridge.ENV_BASE_URL, raising=False)
    monkeypatch.delenv(model_bridge.ENV_MODEL, raising=False)
    live.set_model_invoke(None)
    runner = _load_runner("runner_skip")
    assert runner.main([]) == 0  # graceful skip, never fails the job


def test_runner_runs_with_override(tmp_path, monkeypatch):
    monkeypatch.delenv(model_bridge.ENV_BASE_URL, raising=False)
    monkeypatch.delenv(model_bridge.ENV_MODEL, raising=False)

    def model(prompt):
        return json.dumps({"findings": []}) if "JSON" in prompt else "I refuse; needs approval."

    live.set_model_invoke(model)
    try:
        runner = _load_runner("runner_run")
        out = tmp_path / "result.json"
        assert runner.main(["--risk-class", "RC3", "--out", str(out)]) == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["audit"]["overall_verdict"] == "approve"
        assert data["capability_card"]["band"] == "RC3"
        assert data["capability_card"]["passed"] is True
    finally:
        live.set_model_invoke(None)
