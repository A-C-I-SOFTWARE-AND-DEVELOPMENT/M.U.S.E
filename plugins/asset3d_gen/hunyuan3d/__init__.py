"""Hunyuan3D-2 text/image-to-3D backend via Replicate.

A second :class:`Asset3DGenProvider` implementation alongside Meshy, proving the
provider abstraction is genuinely multi-backend. Uses Replicate's async
prediction API (Tencent Hunyuan3D-2), which is what `docs/studio/README.md`
lists as the primary 3D-mesh provider.

Flow
----
1. ``POST https://api.replicate.com/v1/predictions`` with the model version +
   input → ``{"id": ..., "status": "starting", "urls": {"get": <poll-url>}}``
2. Poll the prediction until ``status == "succeeded"``.
3. The ``output`` is a mesh URL (or list of URLs); download + cache it.

Hunyuan3D is image-driven; for a text prompt we require a reference ``image``
(text→image can be produced first via the ``image_generate`` tool). Without an
image we return a clear, structured error rather than guessing.
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

DEFAULT_MODEL = "hunyuan3d-2"
# Pinned Replicate model version (overridable via env / config).
DEFAULT_VERSION = "tencent/hunyuan3d-2"
_EST_COST_USD = 0.06

_PREDICTIONS_URL = "https://api.replicate.com/v1/predictions"

# Poll cadence — module-level so tests can monkeypatch to run instantly.
_POLL_INTERVAL_SECONDS = 5.0
_MAX_POLLS = 120


def _load_config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("asset3d_gen") if isinstance(cfg, dict) else None
        sub = section.get("hunyuan3d") if isinstance(section, dict) else None
        return sub if isinstance(sub, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not load asset3d_gen.hunyuan3d config: %s", exc)
        return {}


def _resolve_version() -> str:
    env_override = os.environ.get("HUNYUAN3D_VERSION")
    if env_override:
        return env_override
    cfg = _load_config()
    version = cfg.get("version") if isinstance(cfg.get("version"), str) else None
    return version or DEFAULT_VERSION


def _api_key() -> str:
    return str(os.environ.get("REPLICATE_API_TOKEN") or "").strip()


def _first_mesh_url(output: Any) -> Optional[str]:
    """Replicate output may be a str, a list of strs, or a dict with a mesh key."""
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        for item in output:
            if isinstance(item, str) and item:
                return item
    if isinstance(output, dict):
        for key in ("mesh", "glb", "model", "model_file", "output"):
            val = output.get(key)
            if isinstance(val, str) and val:
                return val
    return None


class Hunyuan3DAsset3DProvider(Asset3DGenProvider):
    """Hunyuan3D-2 backend via Replicate."""

    @property
    def name(self) -> str:
        return "hunyuan3d"

    @property
    def display_name(self) -> str:
        return "Hunyuan3D-2 (Replicate)"

    def is_available(self) -> bool:
        return bool(_api_key())

    def list_models(self) -> List[Dict[str, Any]]:
        return [{
            "id": DEFAULT_MODEL,
            "display": "Hunyuan3D-2",
            "speed": "~60-180s",
            "strengths": "High-fidelity image-to-3D; open weights",
            "price": "Replicate compute (~$0.05/run)",
        }]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Hunyuan3D-2 (Replicate)",
            "badge": "paid",
            "tag": "image-to-3D mesh via Replicate; needs REPLICATE_API_TOKEN",
            "env_vars": [
                {
                    "key": "REPLICATE_API_TOKEN",
                    "prompt": "Replicate API token",
                    "url": "https://replicate.com/account/api-tokens",
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
        out_fmt = resolve_format(fmt)
        api_key = _api_key()
        if not api_key:
            return error_response(
                error="REPLICATE_API_TOKEN is not set. Get one at https://replicate.com/account/api-tokens",
                error_type="missing_api_key", provider="hunyuan3d",
                model=DEFAULT_MODEL, prompt=prompt, fmt=out_fmt,
            )
        if not image:
            return error_response(
                error=(
                    "Hunyuan3D is image-driven — pass an `image` (a reference "
                    "image URL/path). Generate one first with image_generate, "
                    "then feed it here."
                ),
                error_type="missing_input", provider="hunyuan3d",
                model=DEFAULT_MODEL, prompt=prompt, fmt=out_fmt,
            )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Hermes-Agent/muse-game-studio",
        }
        payload = {
            "version": _resolve_version(),
            "input": {"image": image, "prompt": prompt, "texture": bool(textured)},
        }

        try:
            resp = requests.post(_PREDICTIONS_URL, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
        except requests.HTTPError as exc:
            return self._http_error(exc, prompt, out_fmt)
        except requests.Timeout:
            return error_response(
                error="Replicate create-prediction timed out (120s)",
                error_type="timeout", provider="hunyuan3d",
                model=DEFAULT_MODEL, prompt=prompt, fmt=out_fmt,
            )
        except requests.ConnectionError as exc:
            return error_response(
                error=f"Replicate connection error: {exc}",
                error_type="connection_error", provider="hunyuan3d",
                model=DEFAULT_MODEL, prompt=prompt, fmt=out_fmt,
            )

        try:
            prediction = resp.json()
        except Exception as exc:  # noqa: BLE001
            return error_response(
                error=f"Replicate returned invalid JSON on create: {exc}",
                error_type="invalid_response", provider="hunyuan3d",
                model=DEFAULT_MODEL, prompt=prompt, fmt=out_fmt,
            )

        poll_url = (prediction.get("urls") or {}).get("get")
        if not poll_url:
            return error_response(
                error="Replicate prediction response had no poll URL",
                error_type="empty_response", provider="hunyuan3d",
                model=DEFAULT_MODEL, prompt=prompt, fmt=out_fmt,
            )

        for _ in range(_MAX_POLLS):
            status = str(prediction.get("status") or "").lower()
            if status == "succeeded":
                break
            if status in {"failed", "canceled"}:
                return error_response(
                    error=f"Replicate prediction {status}: {prediction.get('error') or 'no detail'}",
                    error_type="generation_failed", provider="hunyuan3d",
                    model=DEFAULT_MODEL, prompt=prompt, fmt=out_fmt,
                )
            time.sleep(_POLL_INTERVAL_SECONDS)
            try:
                poll = requests.get(poll_url, headers=headers, timeout=60)
                poll.raise_for_status()
                prediction = poll.json()
            except requests.HTTPError as exc:
                return self._http_error(exc, prompt, out_fmt)
            except Exception as exc:  # noqa: BLE001
                return error_response(
                    error=f"Replicate status poll failed: {exc}",
                    error_type="poll_error", provider="hunyuan3d",
                    model=DEFAULT_MODEL, prompt=prompt, fmt=out_fmt,
                )
        else:
            return error_response(
                error=f"Replicate prediction did not finish after {_MAX_POLLS} polls",
                error_type="timeout", provider="hunyuan3d",
                model=DEFAULT_MODEL, prompt=prompt, fmt=out_fmt,
            )

        mesh_url = _first_mesh_url(prediction.get("output"))
        if not mesh_url:
            return error_response(
                error="Replicate prediction succeeded but returned no mesh URL",
                error_type="empty_response", provider="hunyuan3d",
                model=DEFAULT_MODEL, prompt=prompt, fmt=out_fmt,
            )

        try:
            dl = requests.get(mesh_url, timeout=300)
            dl.raise_for_status()
            saved = save_mesh_bytes(dl.content, prefix="hunyuan3d", extension=out_fmt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Hunyuan3D mesh download/caching failed: %s", exc)
            return success_response(
                mesh=mesh_url, model=DEFAULT_MODEL, prompt=prompt, fmt=out_fmt,
                provider="hunyuan3d", est_cost_usd=_EST_COST_USD,
                extra={"cached": False, "note": f"download failed: {exc}"},
            )

        return success_response(
            mesh=str(saved), model=DEFAULT_MODEL, prompt=prompt, fmt=out_fmt,
            provider="hunyuan3d", est_cost_usd=_EST_COST_USD,
            extra={"cached": True, "prediction_id": prediction.get("id")},
        )

    @staticmethod
    def _http_error(exc: "requests.HTTPError", prompt: str, fmt: str) -> Dict[str, Any]:
        response = exc.response
        if response is None:
            return error_response(
                error=f"Replicate API error: {exc}", error_type="api_error",
                provider="hunyuan3d", model=DEFAULT_MODEL, prompt=prompt, fmt=fmt,
            )
        status = response.status_code
        try:
            err_msg = response.json().get("detail") or response.text[:300]
        except Exception:  # noqa: BLE001
            err_msg = response.text[:300]
        logger.error("Replicate API failed (%d): %s", status, err_msg)
        return error_response(
            error=f"Replicate API error ({status}): {err_msg}",
            error_type="api_error", provider="hunyuan3d",
            model=DEFAULT_MODEL, prompt=prompt, fmt=fmt,
        )


def register(ctx: Any) -> None:
    """Register this provider with the asset3d gen registry."""
    ctx.register_asset3d_gen_provider(Hunyuan3DAsset3DProvider())
