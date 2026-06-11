"""Google Gemini image generation backend.

Exposes Gemini's ``generateContent`` inline-image path as an
:class:`ImageGenProvider` implementation. This is the same HTTP call the
cockpit room editor historically made directly (``gateway/cockpit/room_store.py``)
ported onto the standard provider seam — stdlib ``urllib`` only, so it loads
under Termux with no extra dependencies.

Auth: ``GEMINI_API_KEY`` or ``GOOGLE_API_KEY`` (first hit wins).

Model selection precedence (first hit wins):

1. ``GEMINI_IMAGE_MODEL`` env var
2. ``HERMES_IMAGE_MODEL`` env var (legacy knob the room editor honored)
3. ``image_gen.gemini.model`` in ``config.yaml``
4. :data:`DEFAULT_MODEL`

Output: inline base64 image data → saved under ``$HERMES_HOME/cache/images/``.
Note: ``generateContent`` does not take a size/aspect parameter; the requested
``aspect_ratio`` is clamped and echoed for the uniform response shape only.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.request
from typing import Any, Dict, List, Optional

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_b64_image,
    success_response,
)

logger = logging.getLogger(__name__)


DEFAULT_MODEL = "gemini-2.0-flash-preview-image-generation"

_TIMEOUT_SECONDS = 60.0


def _api_key() -> Optional[str]:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or None


def _load_gemini_config() -> Dict[str, Any]:
    """Read ``image_gen.gemini`` from config.yaml (returns {} on any failure)."""
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        gemini_section = section.get("gemini") if isinstance(section, dict) else None
        return gemini_section if isinstance(gemini_section, dict) else {}
    except Exception as exc:
        logger.debug("Could not load image_gen.gemini config: %s", exc)
        return {}


def _resolve_model() -> str:
    """Decide which Gemini model to call (any non-empty string is accepted)."""
    for env_var in ("GEMINI_IMAGE_MODEL", "HERMES_IMAGE_MODEL"):
        value = os.environ.get(env_var)
        if value and value.strip():
            return value.strip()

    cfg = _load_gemini_config()
    candidate = cfg.get("model")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()

    return DEFAULT_MODEL


def _generate_content(prompt: str, *, model: str, api_key: str) -> bytes:
    """POST one ``generateContent`` request; return raw image bytes.

    Same URL + request shape the room editor used: ``contents/parts/text``
    plus ``responseModalities: ["TEXT", "IMAGE"]``. Raises on failure.
    """
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:  # noqa: S310
        body = json.loads(resp.read().decode("utf-8"))
    for cand in body.get("candidates", []):
        for part in (cand.get("content", {}) or {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise RuntimeError("no image returned by the model")


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class GeminiImageGenProvider(ImageGenProvider):
    """Gemini ``generateContent`` backend — inline base64 image output."""

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Google Gemini"

    def is_available(self) -> bool:
        return _api_key() is not None

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": DEFAULT_MODEL,
                "display": "Gemini 2.0 Flash (image generation)",
                "speed": "~10s",
                "strengths": "Fast inline image generation; free-tier keys work",
                "price": "free tier available",
            },
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Google Gemini",
            "badge": "free-tier",
            "tag": "Gemini generateContent inline images (GEMINI_API_KEY or GOOGLE_API_KEY)",
            "env_vars": [
                {
                    "key": "GEMINI_API_KEY",
                    "prompt": "Gemini API key",
                    "url": "https://aistudio.google.com/apikey",
                },
            ],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)

        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument",
                provider="gemini",
                aspect_ratio=aspect,
            )

        api_key = _api_key()
        if not api_key:
            return error_response(
                error=(
                    "GEMINI_API_KEY not set. Run `hermes tools` → Image "
                    "Generation → Google Gemini to configure, or set "
                    "GEMINI_API_KEY / GOOGLE_API_KEY in ~/.hermes/.env."
                ),
                error_type="auth_required",
                provider="gemini",
                aspect_ratio=aspect,
            )

        model = _resolve_model()

        try:
            raw = _generate_content(prompt, model=model, api_key=api_key)
        except Exception as exc:  # noqa: BLE001 — never raise out of generate
            logger.debug("Gemini image generation failed", exc_info=True)
            return error_response(
                error=f"Gemini image generation failed: {exc}",
                error_type="api_error",
                provider="gemini",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        try:
            saved_path = save_b64_image(
                base64.b64encode(raw).decode("ascii"), prefix="gemini"
            )
        except Exception as exc:
            return error_response(
                error=f"Could not save image to cache: {exc}",
                error_type="io_error",
                provider="gemini",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        return success_response(
            image=str(saved_path),
            model=model,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="gemini",
        )


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------


def register(ctx) -> None:
    """Plugin entry point — wire ``GeminiImageGenProvider`` into the registry."""
    ctx.register_image_gen_provider(GeminiImageGenProvider())
