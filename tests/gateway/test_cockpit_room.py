"""Tests for AI room-item generation ('type Victorian desk → generate it')."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from agent import image_gen_registry
from agent.image_gen_provider import ImageGenProvider
from gateway.cockpit import handlers as h
from gateway.cockpit import room_store as rs

# A 1x1 PNG.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class _FakeProvider(ImageGenProvider):
    """Minimal registry provider: writes the 1x1 PNG and records prompts."""

    def __init__(self, name: str = "fake", available: bool = True, out_dir: Path | None = None):
        self._name = name
        self._available = available
        self._out_dir = out_dir
        self.prompts: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def generate(self, prompt, aspect_ratio="landscape", **kw):
        self.prompts.append(prompt)
        out = (self._out_dir or Path(".")) / f"{self._name}_out.png"
        out.write_bytes(_PNG)
        return {
            "success": True,
            "image": str(out),
            "model": "fake-model",
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "provider": self._name,
        }


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    # Isolate the image-gen registry so providers registered by other tests
    # (or plugin loading) never leak into the "no backend" assertions.
    with image_gen_registry._lock:
        snapshot = dict(image_gen_registry._providers)
    image_gen_registry._reset_for_tests()
    yield tmp_path
    with image_gen_registry._lock:
        image_gen_registry._providers.clear()
        image_gen_registry._providers.update(snapshot)


def test_generate_persists_and_lists_with_image(home) -> None:
    item = rs.generate_item("a Victorian desk", generator=lambda p: _PNG)
    assert item["prompt"] == "a Victorian desk"
    assert item["image_b64"] and base64.b64decode(item["image_b64"]) == _PNG
    listed = rs.list_items()
    assert len(listed) == 1 and listed[0]["id"] == item["id"]


def test_generate_requires_image_key_when_no_generator(home) -> None:
    with pytest.raises(RuntimeError):
        rs.generate_item("a lamp")  # no GEMINI_API_KEY → honest failure


def test_delete_item(home) -> None:
    item = rs.generate_item("a plant", generator=lambda p: _PNG)
    assert rs.delete_item(item["id"]) is True
    assert rs.list_items() == []
    assert rs.delete_item("nope") is False


def test_handler_503_without_image_model(home) -> None:
    resp = h.room_generate(h.Request(method="POST", path="x", body={"prompt": "a chair"}))
    assert resp.status == 503
    assert "image model" in resp.payload["error"]


def test_set_and_persist_position(home) -> None:
    item = rs.generate_item("a rug", generator=lambda p: _PNG)
    assert item["x"] == 0.5 and 0.0 <= item["y"] <= 1.0
    assert rs.set_position(item["id"], 0.2, 0.9) is True
    placed = next(i for i in rs.list_items() if i["id"] == item["id"])
    assert placed["x"] == 0.2 and placed["y"] == 0.9
    # clamps + unknown id
    assert rs.set_position(item["id"], 5.0, -1.0) is True
    placed = next(i for i in rs.list_items() if i["id"] == item["id"])
    assert placed["x"] == 1.0 and placed["y"] == 0.0
    assert rs.set_position("nope", 0.5, 0.5) is False


def test_handler_list_reports_availability(home) -> None:
    resp = h.room_list(h.Request(method="GET", path="x"))
    assert resp.status == 200
    assert resp.payload["image_generation"] is False
    assert resp.payload["items"] == []


# ---------------------------------------------------------------------------
# Registry dispatch (P1-01) — any wired ImageGenProvider unblocks the editor.
# ---------------------------------------------------------------------------


def test_generate_dispatches_through_registry(home) -> None:
    provider = _FakeProvider(out_dir=home)
    image_gen_registry.register_provider(provider)
    item = rs.generate_item("a Victorian desk")  # no GEMINI key set
    assert item["prompt"] == "a Victorian desk"
    assert base64.b64decode(item["image_b64"]) == _PNG
    # The pixel-art style framing is applied before dispatch.
    assert provider.prompts == [
        "Generate a single crisp pixel-art game asset (transparent or plain "
        "background, centered, no text): a Victorian desk"
    ]


def test_registry_provider_makes_generation_available(home) -> None:
    image_gen_registry.register_provider(_FakeProvider(out_dir=home))
    assert rs.image_generation_available() is True
    resp = h.room_list(h.Request(method="GET", path="x"))
    assert resp.status == 200 and resp.payload["image_generation"] is True


def test_unavailable_registry_provider_stays_honest(home) -> None:
    image_gen_registry.register_provider(_FakeProvider(available=False, out_dir=home))
    assert rs.image_generation_available() is False
    with pytest.raises(RuntimeError):
        rs.generate_item("a lamp")
    resp = h.room_generate(h.Request(method="POST", path="x", body={"prompt": "a chair"}))
    assert resp.status == 503


def test_registry_provider_failure_raises(home) -> None:
    class _Failing(_FakeProvider):
        def generate(self, prompt, aspect_ratio="landscape", **kw):
            return {"success": False, "image": None, "error": "boom", "provider": self.name}

    image_gen_registry.register_provider(_Failing(out_dir=home))
    with pytest.raises(RuntimeError, match="boom"):
        rs.generate_item("a lamp")


def test_gemini_env_fallback_without_registry_provider(home, monkeypatch) -> None:
    """A plain GEMINI_API_KEY (no registered provider) still works — the
    pre-seam direct-Gemini path is intact for existing users."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls: list[tuple[str, str]] = []

    def fake_gemini(prompt: str, *, api_key: str, timeout: float = 60.0) -> bytes:
        calls.append((prompt, api_key))
        return _PNG

    monkeypatch.setattr(rs, "_gemini_image", fake_gemini)
    assert rs.image_generation_available() is True
    item = rs.generate_item("a globe")
    assert base64.b64decode(item["image_b64"]) == _PNG
    assert calls == [("a globe", "test-key")]
