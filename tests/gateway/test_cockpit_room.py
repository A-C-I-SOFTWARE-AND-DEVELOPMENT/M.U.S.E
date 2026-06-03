"""Tests for AI room-item generation ('type Victorian desk → generate it')."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from gateway.cockpit import handlers as h
from gateway.cockpit import room_store as rs

# A 1x1 PNG.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    return tmp_path


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
