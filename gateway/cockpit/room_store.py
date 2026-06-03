"""AI-generated room items — "type *Victorian desk* → generate it".

Backs the companion's room editor. Given a text prompt, ask **Gemini** (the
owner's flagged image brain) to generate a small pixel-art asset, persist it,
and serve it back so the Den can place it. Honest when no image key is set.

Stdlib-only (``urllib``) so it loads under Termux; the network call is guarded.
Items live under ``${HERMES_HOME}/jarvis_prime/room/`` with a ``manifest.json``.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

DEFAULT_IMAGE_MODEL = "gemini-2.0-flash-preview-image-generation"


def room_dir() -> Path:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    d = Path(base) / "jarvis_prime" / "room"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _manifest_path() -> Path:
    return room_dir() / "manifest.json"


def _load_manifest() -> list[dict]:
    try:
        return json.loads(_manifest_path().read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_manifest(items: list[dict]) -> None:
    _manifest_path().write_text(json.dumps(items, indent=2), encoding="utf-8")


def _image_key() -> Optional[str]:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or None


def image_generation_available() -> bool:
    return _image_key() is not None


def _gemini_image(prompt: str, *, api_key: str, timeout: float = 60.0) -> bytes:
    """Generate one image with Gemini; returns raw PNG bytes. Raises on failure."""
    model = os.environ.get("HERMES_IMAGE_MODEL", DEFAULT_IMAGE_MODEL)
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    styled = (
        "Generate a single crisp pixel-art game asset (transparent or plain "
        f"background, centered, no text): {prompt}"
    )
    payload = {
        "contents": [{"parts": [{"text": styled}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        body = json.loads(resp.read().decode("utf-8"))
    for cand in body.get("candidates", []):
        for part in (cand.get("content", {}) or {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise RuntimeError("no image returned by the model")


def generate_item(prompt: str, *, generator=None) -> dict:
    """Generate + persist a room item from ``prompt``. ``generator`` overrides the
    image backend (tests). Raises RuntimeError when no image model is available."""
    text = (prompt or "").strip()
    if not text:
        raise ValueError("a prompt is required")

    if generator is not None:
        png = generator(text)
    else:
        key = _image_key()
        if not key:
            raise RuntimeError(
                "no image model configured — set GEMINI_API_KEY to generate room items"
            )
        png = _gemini_image(text, api_key=key)

    item_id = "room_" + uuid.uuid4().hex[:8]
    file = room_dir() / f"{item_id}.png"
    file.write_bytes(png)
    item = {
        "id": item_id,
        "prompt": text,
        "file": file.name,
        "created_at": time.time(),
    }
    items = _load_manifest()
    items.append(item)
    _save_manifest(items)
    return _with_image(item)


def _with_image(item: dict) -> dict:
    """Attach base64 PNG so the JSON API can ship the image to the app."""
    try:
        raw = (room_dir() / item["file"]).read_bytes()
        return {**item, "image_b64": base64.b64encode(raw).decode("ascii")}
    except Exception:
        return {**item, "image_b64": None}


def list_items() -> list[dict]:
    return [_with_image(it) for it in _load_manifest()]


def delete_item(item_id: str) -> bool:
    items = _load_manifest()
    kept = [it for it in items if it.get("id") != item_id]
    if len(kept) == len(items):
        return False
    for it in items:
        if it.get("id") == item_id:
            try:
                (room_dir() / it["file"]).unlink()
            except Exception:
                pass
    _save_manifest(kept)
    return True


__all__ = [
    "delete_item",
    "generate_item",
    "image_generation_available",
    "list_items",
    "room_dir",
]
