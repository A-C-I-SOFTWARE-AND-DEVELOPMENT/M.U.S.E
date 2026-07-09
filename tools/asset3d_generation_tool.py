"""
3D Asset Generation Tool
========================

The ``asset3d_generate`` tool — text-to-3D mesh generation for the muse Game
Studio. Dispatches each call to the active backend resolved by
``asset3d_gen.provider`` in ``config.yaml`` (see
:mod:`agent.asset3d_gen_registry`).

Unlike ``image_generate``/``video_generate`` there is no in-tree default
backend; every provider ships as a plugin under ``plugins/asset3d_gen/<name>/``.
When no provider is configured/available the tool returns a helpful, structured
error rather than raising — identical to the unset-provider behaviour of the
image and video surfaces.

The owner gates that govern *spend* (a 3D mesh generation call costs money on
hosted backends) live in the ``game-studio`` skill and the provider's
``est_cost_usd`` field; this tool is the thin dispatch surface.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)


ASSET3D_GENERATE_SCHEMA = {
    "name": "asset3d_generate",
    "description": (
        "Generate a 3D mesh asset from a text prompt (optionally guided by a "
        "reference image). The underlying backend (Meshy, Hunyuan3D, etc.) is "
        "user-configured via `asset3d_gen.provider` and not selectable by the "
        "agent. Returns an absolute file path or URL in the `mesh` field, the "
        "container `format` (glb/fbx/obj), and any PBR `textures`. Hosted "
        "backends cost money per call — surface `est_cost_usd` to the owner "
        "before bulk generation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Natural-language description of the asset to generate.",
            },
            "fmt": {
                "type": "string",
                "description": "Mesh container format.",
                "enum": ["glb", "fbx", "obj", "usdz", "ply"],
                "default": "glb",
            },
            "textured": {
                "type": "boolean",
                "description": "Request PBR textures alongside the mesh.",
                "default": True,
            },
            "image": {
                "type": "string",
                "description": (
                    "Optional reference image (URL or absolute path) for "
                    "image-to-3D backends."
                ),
            },
        },
        "required": ["prompt"],
    },
}


def check_asset3d_generation_requirements() -> bool:
    """True if any plugin-registered asset3d backend is available.

    Discovery is idempotent and cheap; the active selection among ready
    providers is resolved per-call by ``asset3d_gen.provider``.
    """
    try:
        from agent.asset3d_gen_registry import list_providers
        from hermes_cli.plugins import _ensure_plugins_discovered

        _ensure_plugins_discovered()
        for provider in list_providers():
            try:
                if provider.is_available():
                    return True
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    return False


def _handle_asset3d_generate(args: Dict[str, Any], **_kw: Any):
    prompt = args.get("prompt", "")
    if not prompt:
        return tool_error("prompt is required for 3D asset generation")

    fmt = args.get("fmt", "glb")
    textured = args.get("textured", True)
    image = args.get("image")

    try:
        from agent.asset3d_gen_registry import get_active_provider
        from hermes_cli.plugins import _ensure_plugins_discovered

        _ensure_plugins_discovered()
        provider = get_active_provider()
    except Exception as exc:  # noqa: BLE001
        logger.debug("asset3d dispatch could not resolve provider: %s", exc)
        provider = None

    if provider is None:
        return json.dumps({
            "success": False,
            "mesh": None,
            "error": (
                "No 3D asset generation backend is configured. Set "
                "`asset3d_gen.provider` (e.g. to 'meshy') and the matching "
                "API key, then run `hermes plugins list` to confirm it is "
                "registered."
            ),
            "error_type": "provider_not_registered",
        })

    try:
        result = provider.generate(
            prompt=prompt,
            fmt=fmt,
            textured=textured,
            image=image,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Asset3D provider '%s' raised: %s",
            getattr(provider, "name", "?"), exc,
        )
        return json.dumps({
            "success": False,
            "mesh": None,
            "error": f"Provider '{getattr(provider, 'name', '?')}' error: {exc}",
            "error_type": "provider_exception",
        })

    if not isinstance(result, dict):
        return json.dumps({
            "success": False,
            "mesh": None,
            "error": "Provider returned a non-dict result",
            "error_type": "provider_contract",
        })
    return json.dumps(result)


registry.register(
    name="asset3d_generate",
    toolset="asset3d_gen",
    schema=ASSET3D_GENERATE_SCHEMA,
    handler=_handle_asset3d_generate,
    check_fn=check_asset3d_generation_requirements,
    requires_env=[],
    is_async=False,
    emoji="🧊",
)
