"""
3D Asset Generation Provider ABC
================================

Defines the pluggable-backend interface for **text-to-3D mesh** generation —
the muse Game Studio's first-class asset surface. Providers register instances
via ``PluginContext.register_asset3d_gen_provider()``; the active one (selected
via ``asset3d_gen.provider`` in ``config.yaml``) services every
``asset3d_generate`` tool call.

This mirrors :mod:`agent.image_gen_provider` and :mod:`agent.video_gen_provider`
exactly so the three media surfaces (image / video / 3D) behave identically —
same registration shape, same response envelope, same fallback semantics.

Providers live in ``<repo>/plugins/asset3d_gen/<name>/`` (built-in, auto-loaded
as ``kind: backend``) or ``~/.hermes/plugins/asset3d_gen/<name>/`` (user, opt-in
via ``plugins.enabled``).

Response shape
--------------
All providers return a dict that :func:`success_response` / :func:`error_response`
produce. The tool wrapper JSON-serializes it. Keys:

    success        bool
    mesh           str | None       URL or absolute file path to the mesh
    format         str              "glb" | "fbx" | "obj" | "usdz" | "ply"
    textures       list[str]        absolute paths / URLs to PBR texture maps
    model          str              provider-specific model identifier
    prompt         str              echoed prompt
    provider       str              provider name (for diagnostics)
    poly_count     int | None       triangle/face count, when known
    est_cost_usd   float | None     estimated spend, when known (owner gate)
    error          str              only when success=False
    error_type     str              only when success=False
"""

from __future__ import annotations

import abc
import datetime
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


VALID_FORMATS: Tuple[str, ...] = ("glb", "fbx", "obj", "usdz", "ply")
DEFAULT_FORMAT = "glb"


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------


class Asset3DGenProvider(abc.ABC):
    """Abstract base class for a text-to-3D mesh generation backend.

    Subclasses must implement :meth:`generate`. Everything else has sane
    defaults — override only what your provider needs.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Stable short identifier used in ``asset3d_gen.provider`` config.

        Lowercase, no spaces. Examples: ``meshy``, ``hunyuan3d``, ``tripo``.
        """

    @property
    def display_name(self) -> str:
        """Human-readable label shown in ``hermes tools``. Defaults to ``name.title()``."""
        return self.name.title()

    def is_available(self) -> bool:
        """Return True when this provider can service calls.

        Typically checks for a required API key. Default: True
        (providers with no external dependencies are always available).
        """
        return True

    def list_models(self) -> List[Dict[str, Any]]:
        """Return catalog entries for the ``hermes tools`` model picker.

        Each entry::

            {
                "id": "meshy-5",                     # required
                "display": "Meshy 5",                # optional; defaults to id
                "speed": "~60s",                     # optional
                "strengths": "PBR textures, retopo", # optional
                "price": "$0.10/mesh",               # optional
            }

        Default: empty list (provider has no user-selectable models).
        """
        return []

    def get_setup_schema(self) -> Dict[str, Any]:
        """Return provider metadata for the ``hermes tools`` picker.

        Shape mirrors :meth:`agent.image_gen_provider.ImageGenProvider.get_setup_schema`::

            {
                "name": "Meshy",
                "badge": "paid",
                "tag": "One-line description...",
                "env_vars": [
                    {"key": "MESHY_API_KEY",
                     "prompt": "Meshy API key",
                     "url": "https://www.meshy.ai/api-keys"},
                ],
            }

        Default: minimal entry derived from ``display_name``.
        """
        return {
            "name": self.display_name,
            "badge": "",
            "tag": "",
            "env_vars": [],
        }

    def default_model(self) -> Optional[str]:
        """Return the default model id, or None if not applicable."""
        models = self.list_models()
        if models:
            return models[0].get("id")
        return None

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        fmt: str = DEFAULT_FORMAT,
        textured: bool = True,
        image: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate a 3D mesh.

        Parameters
        ----------
        prompt:
            Natural-language description of the asset.
        fmt:
            Desired mesh container format (``glb``/``fbx``/``obj``/…).
        textured:
            Whether to request PBR textures alongside the mesh.
        image:
            Optional reference image (URL or path) for image-to-3D backends.
        kwargs:
            Forward-compat parameters future versions of the schema expose.
            Implementations should ignore unknown keys.

        Implementations should return the dict from :func:`success_response`
        or :func:`error_response`.
        """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def resolve_format(value: Optional[str]) -> str:
    """Clamp a format value to the valid set, defaulting to ``glb``.

    Invalid values are coerced rather than rejected so the tool surface is
    forgiving of agent mistakes (mirrors ``resolve_aspect_ratio``).
    """
    if not isinstance(value, str):
        return DEFAULT_FORMAT
    v = value.strip().lower().lstrip(".")
    if v in VALID_FORMATS:
        return v
    return DEFAULT_FORMAT


def _meshes_cache_dir() -> Path:
    """Return ``$HERMES_HOME/cache/meshes/``, creating parents as needed."""
    from hermes_constants import get_hermes_home

    path = get_hermes_home() / "cache" / "meshes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_mesh_bytes(
    data: bytes,
    *,
    prefix: str = "mesh",
    extension: str = DEFAULT_FORMAT,
) -> Path:
    """Write raw mesh bytes under ``$HERMES_HOME/cache/meshes/``.

    Returns the absolute :class:`Path` to the saved file. Mirrors
    :func:`agent.image_gen_provider.save_b64_image` (sans base64 decode —
    mesh APIs typically hand back binary or a download URL).

    Filename format: ``<prefix>_<YYYYMMDD_HHMMSS>_<short-uuid>.<ext>``.
    """
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    ext = str(extension).lstrip(".") or DEFAULT_FORMAT
    path = _meshes_cache_dir() / f"{prefix}_{ts}_{short}.{ext}"
    path.write_bytes(data)
    return path


def success_response(
    *,
    mesh: str,
    model: str,
    prompt: str,
    fmt: str,
    provider: str,
    textures: Optional[List[str]] = None,
    poly_count: Optional[int] = None,
    est_cost_usd: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a uniform success response dict.

    ``mesh`` may be an HTTP URL or an absolute filesystem path. Callers that
    need to pass through additional backend-specific fields can supply
    ``extra``.
    """
    payload: Dict[str, Any] = {
        "success": True,
        "mesh": mesh,
        "format": resolve_format(fmt),
        "textures": list(textures) if textures else [],
        "model": model,
        "prompt": prompt,
        "provider": provider,
        "poly_count": poly_count,
        "est_cost_usd": est_cost_usd,
    }
    if extra:
        for k, v in extra.items():
            payload.setdefault(k, v)
    return payload


def error_response(
    *,
    error: str,
    error_type: str = "provider_error",
    provider: str = "",
    model: str = "",
    prompt: str = "",
    fmt: str = DEFAULT_FORMAT,
) -> Dict[str, Any]:
    """Build a uniform error response dict."""
    return {
        "success": False,
        "mesh": None,
        "error": error,
        "error_type": error_type,
        "format": resolve_format(fmt),
        "textures": [],
        "model": model,
        "prompt": prompt,
        "provider": provider,
        "poly_count": None,
        "est_cost_usd": None,
    }
