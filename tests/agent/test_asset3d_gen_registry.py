"""Tests for the 3D asset generation provider registry.

Mirrors the image/video registry test shape: register / get / active-provider
resolution / single-provider fallback / reset.
"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from agent.asset3d_gen_provider import Asset3DGenProvider, success_response
from agent import asset3d_gen_registry as reg


class _StubProvider(Asset3DGenProvider):
    def __init__(self, name: str = "stub", available: bool = True) -> None:
        self._name = name
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def generate(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        return success_response(
            mesh="/tmp/stub.glb", model="stub", prompt=prompt, fmt="glb", provider=self._name
        )


@pytest.fixture(autouse=True)
def _clean_registry():
    reg._reset_for_tests()
    yield
    reg._reset_for_tests()


def test_register_and_get():
    p = _StubProvider("meshy")
    reg.register_provider(p)
    assert reg.get_provider("meshy") is p
    assert reg.get_provider("nope") is None


def test_register_rejects_non_provider():
    with pytest.raises(TypeError):
        reg.register_provider(object())  # ty: ignore[invalid-argument-type]  # intentional bad input


def test_list_providers_sorted():
    reg.register_provider(_StubProvider("zeta"))
    reg.register_provider(_StubProvider("alpha"))
    names = [p.name for p in reg.list_providers()]
    assert names == ["alpha", "zeta"]


def test_single_available_provider_is_active(monkeypatch):
    # No config -> single available provider wins.
    monkeypatch.setattr(reg, "_providers", {}, raising=False)
    reg._reset_for_tests()
    reg.register_provider(_StubProvider("meshy", available=True))
    active = reg.get_active_provider()
    assert active is not None and active.name == "meshy"


def test_single_unavailable_provider_is_not_active():
    reg.register_provider(_StubProvider("meshy", available=False))
    assert reg.get_active_provider() is None


def test_explicit_config_wins(monkeypatch):
    reg.register_provider(_StubProvider("meshy"))
    reg.register_provider(_StubProvider("hunyuan3d"))

    def fake_load_config():
        return {"asset3d_gen": {"provider": "hunyuan3d"}}

    monkeypatch.setattr("hermes_cli.config.load_config", fake_load_config)
    active = reg.get_active_provider()
    assert active is not None and active.name == "hunyuan3d"


def test_explicit_config_returns_even_if_unavailable(monkeypatch):
    # Explicit selection returns the provider even when unavailable so the
    # caller surfaces a precise missing-key error rather than silently switching.
    reg.register_provider(_StubProvider("meshy", available=False))
    reg.register_provider(_StubProvider("other", available=True))

    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"asset3d_gen": {"provider": "meshy"}},
    )
    active = reg.get_active_provider()
    assert active is not None and active.name == "meshy"


def test_multiple_available_no_config_is_ambiguous(monkeypatch):
    reg.register_provider(_StubProvider("meshy"))
    reg.register_provider(_StubProvider("hunyuan3d"))
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {})
    # Two available, no config -> ambiguous -> None.
    assert reg.get_active_provider() is None


def test_reset_clears():
    reg.register_provider(_StubProvider("meshy"))
    reg._reset_for_tests()
    assert reg.list_providers() == []
