"""Tests for the asset3d_generate tool dispatcher.

Covers the dispatch surface in tools/asset3d_generation_tool.py independently of
any concrete backend: prompt validation, no-provider error, provider dispatch,
provider exception, and non-dict provider result.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from agent.asset3d_gen_provider import Asset3DGenProvider, success_response


class _StubProvider(Asset3DGenProvider):
    def __init__(self, result=None, raises=False):
        self._result = result
        self._raises = raises
        self.calls = []

    @property
    def name(self) -> str:
        return "stub"

    def generate(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        if self._raises:
            raise RuntimeError("boom")
        if self._result is not None:
            return self._result
        return success_response(
            mesh="/tmp/x.glb", model="stub", prompt=prompt, fmt="glb", provider="stub"
        )


@pytest.fixture(autouse=True)
def _no_discovery():
    # The handler calls _ensure_plugins_discovered(); make it a no-op.
    with patch("hermes_cli.plugins._ensure_plugins_discovered", lambda *a, **k: None):
        yield


def _handle(args):
    from tools.asset3d_generation_tool import _handle_asset3d_generate

    return _handle_asset3d_generate(args)


def test_missing_prompt_is_error():
    out = _handle({})
    # tool_error returns a JSON string; just assert it signals failure.
    assert "prompt is required" in out


def test_no_provider_configured():
    with patch("agent.asset3d_gen_registry.get_active_provider", return_value=None):
        out = json.loads(_handle({"prompt": "a crate"}))
    assert out["success"] is False
    assert out["error_type"] == "provider_not_registered"


def test_dispatches_to_active_provider():
    stub = _StubProvider()
    with patch("agent.asset3d_gen_registry.get_active_provider", return_value=stub):
        out = json.loads(_handle({"prompt": "a crate", "fmt": "glb", "textured": True}))
    assert out["success"] is True
    assert out["mesh"] == "/tmp/x.glb"
    assert out["provider"] == "stub"
    # Args forwarded to the provider.
    assert stub.calls[0]["prompt"] == "a crate"
    assert stub.calls[0]["fmt"] == "glb"
    assert stub.calls[0]["textured"] is True


def test_provider_exception_is_caught():
    stub = _StubProvider(raises=True)
    with patch("agent.asset3d_gen_registry.get_active_provider", return_value=stub):
        out = json.loads(_handle({"prompt": "a crate"}))
    assert out["success"] is False
    assert out["error_type"] == "provider_exception"
    assert "boom" in out["error"]


def test_non_dict_result_is_rejected():
    stub = _StubProvider(result="not-a-dict")
    with patch("agent.asset3d_gen_registry.get_active_provider", return_value=stub):
        out = json.loads(_handle({"prompt": "a crate"}))
    assert out["success"] is False
    assert out["error_type"] == "provider_contract"


def test_image_arg_forwarded():
    stub = _StubProvider()
    with patch("agent.asset3d_gen_registry.get_active_provider", return_value=stub):
        _handle({"prompt": "crate", "image": "https://x/ref.png"})
    assert stub.calls[0]["image"] == "https://x/ref.png"
