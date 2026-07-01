"""Meshy text-to-3D mesh generation backend.

Exposes Meshy's text-to-3D (and image-to-3D) API as an
:class:`Asset3DGenProvider` implementation. Meshy is a hosted service, so no
local GPU is required — which makes it the default 3D backend for the muse
Game Studio in environments (like CI) that have no graphics hardware.

Alternatives that fit the same provider interface (documented, not bundled):
Hunyuan3D-2 (Replicate), Tripo3D, TRELLIS. To add one, copy this directory and
swap the HTTP calls.

Flow
----
Meshy text-to-3D is an async job:

1. ``POST /openapi/v2/text-to-3d`` (mode=preview) → ``{"result": "<task_id>"}``
2. Poll ``GET  /openapi/v2/text-to-3d/<task_id>`` until ``status == SUCCEEDED``
3. Download the mesh for the requested format from ``model_urls`` and cache it.

Selection precedence for the model/art-style (first hit wins):
1. ``MESHY_*`` env vars
2. ``asset3d_gen.meshy.*`` in ``config.yaml``
3. module defaults
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

from agent.asset3d_gen_provider import (
    Asset3DGenProvider,
    DEFAULT_FORMAT,
    error_response,
    resolve_format,
    save_mesh_bytes,
    success_response,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Catalog / config
# ---------------------------------------------------------------------------

_MODELS: Dict[str, Dict[str, Any]] = {
    "meshy-5": {
        "display": "Meshy 5",
        "speed": "~60-120s",
        "strengths": "PBR textures, auto-retopology, game-ready meshes",
        "price": "~$0.10/mesh (credits)",
    },
    "meshy-4": {
        "display": "Meshy 4",
        "speed": "~60s",
        "strengths": "Fast previews, lower cost",
        "price": "~$0.05/mesh (credits)",
    },
}

DEFAULT_MODEL = "meshy-5"
DEFAULT_ART_STYLE = "realistic"
# Rough per-mesh estimate surfaced to the owner gate; real cost is credit-based.
_EST_COST_USD = 0.10

_TEXT_TO_3D_URL = "https://api.meshy.ai/openapi/v2/text-to-3d"
_IMAGE_TO_3D_URL = "https://api.meshy.ai/openapi/v1/image-to-3d"

# Poll cadence — module-level so tests can monkeypatch to run instantly.
_POLL_INTERVAL_SECONDS = 5.0
_MAX_POLLS = 120  # ~10 minutes at 5s


def _load_meshy_config() -> Dict[str, Any]:
    """Read ``asset3d_gen.meshy`` from config.yaml."""
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("asset3d_gen") if isinstance(cfg, dict) else None
        meshy_section = section.get("meshy") if isinstance(section, dict) else None
        return meshy_section if isinstance(meshy_section, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not load asset3d_gen.meshy config: %s", exc)
        return {}


def _resolve_model() -> str:
    env_override = os.environ.get("MESHY_MODEL")
    if env_override and env_override in _MODELS:
        return env_override
    cfg = _load_meshy_config()
    candidate = cfg.get("model") if isinstance(cfg.get("model"), str) else None
    if candidate and candidate in _MODELS:
        return candidate
    return DEFAULT_MODEL


def _resolve_art_style() -> str:
    # Precedence matches _resolve_model() and the module docstring: env first,
    # then config.yaml, then the default.
    env_override = os.environ.get("MESHY_ART_STYLE")
    if env_override:
        return env_override
    cfg = _load_meshy_config()
    style = cfg.get("art_style") if isinstance(cfg.get("art_style"), str) else None
    return style or DEFAULT_ART_STYLE


def _api_key() -> str:
    return str(os.environ.get("MESHY_API_KEY") or "").strip()


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class MeshyAsset3DProvider(Asset3DGenProvider):
    """Meshy text-to-3D backend."""

    @property
    def name(self) -> str:
        return "meshy"

    @property
    def display_name(self) -> str:
        return "Meshy"

    def is_available(self) -> bool:
        return bool(_api_key())

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": model_id,
                "display": meta.get("display", model_id),
                "speed": meta.get("speed", ""),
                "strengths": meta.get("strengths", ""),
                "price": meta.get("price", ""),
            }
            for model_id, meta in _MODELS.items()
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Meshy (text-to-3D)",
            "badge": "paid",
            "tag": "meshy-5 — game-ready meshes with PBR textures; needs MESHY_API_KEY",
            "env_vars": [
                {
                    "key": "MESHY_API_KEY",
                    "prompt": "Meshy API key",
                    "url": "https://www.meshy.ai/api-keys",
                },
            ],
        }

    def generate(
        self,
        prompt: str,
        *,
        fmt: str = DEFAULT_FORMAT,
        textured: bool = True,
        image: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate a 3D mesh via Meshy's async API."""
        api_key = _api_key()
        out_fmt = resolve_format(fmt)
        model_id = _resolve_model()

        if not api_key:
            return error_response(
                error="MESHY_API_KEY is not set. Get a key at https://www.meshy.ai/api-keys",
                error_type="missing_api_key",
                provider="meshy",
                model=model_id,
                prompt=prompt,
                fmt=out_fmt,
            )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Hermes-Agent/muse-game-studio",
        }

        # --- 1. create the job ------------------------------------------------
        if image:
            create_url = _IMAGE_TO_3D_URL
            payload: Dict[str, Any] = {
                "image_url": image,
                "enable_pbr": bool(textured),
            }
        else:
            create_url = _TEXT_TO_3D_URL
            payload = {
                "mode": "preview",
                "prompt": prompt,
                "art_style": _resolve_art_style(),
                "should_texture": bool(textured),
            }

        try:
            resp = requests.post(create_url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
        except requests.HTTPError as exc:
            return self._http_error(exc, model_id, prompt, out_fmt)
        except requests.Timeout:
            return error_response(
                error="Meshy create-task request timed out (120s)",
                error_type="timeout", provider="meshy",
                model=model_id, prompt=prompt, fmt=out_fmt,
            )
        except requests.ConnectionError as exc:
            return error_response(
                error=f"Meshy connection error: {exc}",
                error_type="connection_error", provider="meshy",
                model=model_id, prompt=prompt, fmt=out_fmt,
            )

        try:
            task_id = resp.json().get("result")
        except Exception as exc:  # noqa: BLE001
            return error_response(
                error=f"Meshy returned invalid JSON on create: {exc}",
                error_type="invalid_response", provider="meshy",
                model=model_id, prompt=prompt, fmt=out_fmt,
            )
        if not task_id:
            return error_response(
                error="Meshy create-task response contained no task id",
                error_type="empty_response", provider="meshy",
                model=model_id, prompt=prompt, fmt=out_fmt,
            )

        # --- 2. poll for completion ------------------------------------------
        status_url = f"{create_url}/{task_id}"
        task: Dict[str, Any] = {}
        for _ in range(_MAX_POLLS):
            try:
                poll = requests.get(status_url, headers=headers, timeout=60)
                poll.raise_for_status()
                task = poll.json()
            except requests.HTTPError as exc:
                return self._http_error(exc, model_id, prompt, out_fmt)
            except requests.Timeout:
                return error_response(
                    error="Meshy status poll timed out (60s)",
                    error_type="timeout", provider="meshy",
                    model=model_id, prompt=prompt, fmt=out_fmt,
                )
            except Exception as exc:  # noqa: BLE001
                return error_response(
                    error=f"Meshy status poll failed: {exc}",
                    error_type="poll_error", provider="meshy",
                    model=model_id, prompt=prompt, fmt=out_fmt,
                )

            status = str(task.get("status") or "").upper()
            if status == "SUCCEEDED":
                break
            if status in {"FAILED", "CANCELED", "EXPIRED"}:
                err = task.get("task_error") or {}
                msg = err.get("message") if isinstance(err, dict) else str(err)
                return error_response(
                    error=f"Meshy task {status.lower()}: {msg or 'no detail'}",
                    error_type="generation_failed", provider="meshy",
                    model=model_id, prompt=prompt, fmt=out_fmt,
                )
            time.sleep(_POLL_INTERVAL_SECONDS)
        else:
            return error_response(
                error=f"Meshy task did not finish after {_MAX_POLLS} polls",
                error_type="timeout", provider="meshy",
                model=model_id, prompt=prompt, fmt=out_fmt,
            )

        # --- 3. resolve the mesh URL + download ------------------------------
        model_urls = task.get("model_urls") or {}
        mesh_url = model_urls.get(out_fmt) if isinstance(model_urls, dict) else None
        if not mesh_url and isinstance(model_urls, dict):
            # Fall back to any available format; reflect what we actually got.
            for cand_fmt in ("glb", "fbx", "obj", "usdz", "ply"):
                if model_urls.get(cand_fmt):
                    mesh_url = model_urls[cand_fmt]
                    out_fmt = cand_fmt
                    break
        if not mesh_url:
            return error_response(
                error="Meshy task succeeded but returned no model URL",
                error_type="empty_response", provider="meshy",
                model=model_id, prompt=prompt, fmt=out_fmt,
            )

        try:
            dl = requests.get(mesh_url, timeout=300)
            dl.raise_for_status()
            saved = save_mesh_bytes(dl.content, prefix=f"meshy_{model_id}", extension=out_fmt)
        except Exception as exc:  # noqa: BLE001
            # Download/caching failed — still hand back the URL so the asset
            # isn't lost; the caller can fetch it directly.
            logger.warning("Meshy mesh download/caching failed: %s", exc)
            return success_response(
                mesh=mesh_url, model=model_id, prompt=prompt, fmt=out_fmt,
                provider="meshy",
                textures=_extract_textures(task),
                poly_count=task.get("poly_count"),
                est_cost_usd=_EST_COST_USD,
                extra={"cached": False, "note": f"download failed: {exc}"},
            )

        return success_response(
            mesh=str(saved), model=model_id, prompt=prompt, fmt=out_fmt,
            provider="meshy",
            textures=_extract_textures(task),
            poly_count=task.get("poly_count"),
            est_cost_usd=_EST_COST_USD,
            extra={"cached": True, "task_id": task_id},
        )

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _http_error(exc: "requests.HTTPError", model_id: str, prompt: str, fmt: str) -> Dict[str, Any]:
        response = exc.response
        if response is None:
            return error_response(
                error=f"Meshy API error: {exc}", error_type="api_error",
                provider="meshy", model=model_id, prompt=prompt, fmt=fmt,
            )
        status = response.status_code
        try:
            err_msg = response.json().get("message") or response.text[:300]
        except Exception:  # noqa: BLE001
            err_msg = response.text[:300]
        logger.error("Meshy API failed (%d): %s", status, err_msg)
        return error_response(
            error=f"Meshy API error ({status}): {err_msg}",
            error_type="api_error", provider="meshy",
            model=model_id, prompt=prompt, fmt=fmt,
        )


def _extract_textures(task: Dict[str, Any]) -> List[str]:
    """Pull texture map URLs from a Meshy task payload (best-effort)."""
    out: List[str] = []
    tex = task.get("texture_urls")
    if isinstance(tex, list):
        for entry in tex:
            if isinstance(entry, dict):
                for v in entry.values():
                    if isinstance(v, str) and v:
                        out.append(v)
            elif isinstance(entry, str):
                out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------


def register(ctx: Any) -> None:
    """Register this provider with the asset3d gen registry."""
    ctx.register_asset3d_gen_provider(MeshyAsset3DProvider())
