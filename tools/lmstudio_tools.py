"""Agent tools for LM Studio model lifecycle management.

Thin wrappers over the native v1 REST helpers in ``hermes_cli.models``
(`download_lmstudio_model`, `lmstudio_download_status`, `unload_lmstudio_model`)
so the agent can pull models and free VRAM on the user's behalf.

Gated via ``check_lmstudio_available`` so these only appear in the model's tool
schema when an LM Studio server is actually reachable — they're hidden in
cloud-only sessions. Connection settings resolve the same way the ``lmstudio``
provider overlay does: an explicit ``base_url`` argument, else ``$LM_BASE_URL``,
else the default ``http://127.0.0.1:1234/v1``; the API key is read from
``$LM_API_KEY`` only (never a model-supplied argument).
"""

from __future__ import annotations

import json
import os
from typing import Any

from tools.registry import registry

_DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"


def _resolve_lmstudio_connection(args: dict[str, Any]) -> tuple[str, str]:
    """Resolve (base_url, api_key) for an LM Studio request.

    ``base_url`` honours an explicit tool argument, then ``$LM_BASE_URL``, then
    the default localhost endpoint. ``api_key`` comes from ``$LM_API_KEY`` only
    — the model never supplies credentials.
    """
    base_url = (
        str(args.get("base_url") or "").strip()
        or os.environ.get("LM_BASE_URL", "").strip()
        or _DEFAULT_BASE_URL
    )
    api_key = os.environ.get("LM_API_KEY", "").strip()
    return base_url, api_key


def check_lmstudio_available() -> bool:
    """True when an LM Studio server is reachable (gates the lifecycle tools).

    Localhost-down is rejected near-instantly (connection refused); the short
    timeout only bounds the unreachable-remote case, and the registry caches
    this result for ~30s so it isn't re-probed every turn.
    """
    try:
        from hermes_cli.models import probe_lmstudio_models

        base_url, api_key = _resolve_lmstudio_connection({})
        return probe_lmstudio_models(base_url=base_url, api_key=api_key, timeout=1.5) is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def handle_download_model(args: dict[str, Any], **_kw) -> str:
    from hermes_cli.models import download_lmstudio_model

    model = str(args.get("model") or "").strip()
    if not model:
        return json.dumps({"error": "model is required"})
    base_url, api_key = _resolve_lmstudio_connection(args)
    quantization = str(args.get("quantization") or "").strip() or None
    result = download_lmstudio_model(model, base_url, api_key, quantization=quantization)
    if result is None:
        return json.dumps(
            {"error": f"download request failed (is LM Studio reachable at {base_url}?)"}
        )
    return json.dumps({"success": True, "result": result}, ensure_ascii=False)


def handle_download_status(args: dict[str, Any], **_kw) -> str:
    from hermes_cli.models import lmstudio_download_status

    job_id = str(args.get("job_id") or "").strip()
    if not job_id:
        return json.dumps({"error": "job_id is required"})
    base_url, api_key = _resolve_lmstudio_connection(args)
    result = lmstudio_download_status(job_id, base_url, api_key)
    if result is None:
        return json.dumps({"error": f"status request failed for job {job_id!r}"})
    return json.dumps({"success": True, "result": result}, ensure_ascii=False)


def handle_unload_model(args: dict[str, Any], **_kw) -> str:
    from hermes_cli.models import unload_lmstudio_model

    model = str(args.get("model") or "").strip()
    if not model:
        return json.dumps({"error": "model is required"})
    base_url, api_key = _resolve_lmstudio_connection(args)
    ok = unload_lmstudio_model(model, base_url, api_key)
    return json.dumps({"success": ok, "model": model})


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_BASE_URL_PARAM = {
    "type": "string",
    "description": (
        "Optional LM Studio base URL (e.g. 'http://127.0.0.1:1234/v1'). Omit to "
        "use $LM_BASE_URL or the local default."
    ),
}

LMSTUDIO_DOWNLOAD_MODEL_SCHEMA = {
    "name": "lmstudio_download_model",
    "description": (
        "Start downloading a model into LM Studio via its native API. The "
        "download runs in the background — poll lmstudio_download_status with the "
        "returned job_id. Returns immediately with the job status "
        "(downloading/already_downloaded/...)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": (
                    "Catalog id (e.g. 'ibm/granite-4-micro') or a Hugging Face "
                    "link to the model to download."
                ),
            },
            "quantization": {
                "type": "string",
                "description": (
                    "Optional quantization level (e.g. 'Q4_K_M'). Only honoured "
                    "for Hugging Face links."
                ),
            },
            "base_url": _BASE_URL_PARAM,
        },
        "required": ["model"],
    },
}

LMSTUDIO_DOWNLOAD_STATUS_SCHEMA = {
    "name": "lmstudio_download_status",
    "description": (
        "Check the progress of an in-flight LM Studio model download by job_id "
        "(returned from lmstudio_download_model)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "The download job id returned by lmstudio_download_model.",
            },
            "base_url": _BASE_URL_PARAM,
        },
        "required": ["job_id"],
    },
}

LMSTUDIO_UNLOAD_MODEL_SCHEMA = {
    "name": "lmstudio_unload_model",
    "description": (
        "Unload a model from LM Studio to free VRAM. Idempotent — unloading a "
        "model that isn't loaded still succeeds."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": "The model key to unload (e.g. 'qwen/qwen3-coder-30b').",
            },
            "base_url": _BASE_URL_PARAM,
        },
        "required": ["model"],
    },
}


# ---------------------------------------------------------------------------
# Registration (auto-discovered at import time)
# ---------------------------------------------------------------------------

registry.register(
    name="lmstudio_download_model",
    toolset="lmstudio",
    schema=LMSTUDIO_DOWNLOAD_MODEL_SCHEMA,
    handler=handle_download_model,
    check_fn=check_lmstudio_available,
    emoji="📥",
)

registry.register(
    name="lmstudio_download_status",
    toolset="lmstudio",
    schema=LMSTUDIO_DOWNLOAD_STATUS_SCHEMA,
    handler=handle_download_status,
    check_fn=check_lmstudio_available,
    emoji="📊",
)

registry.register(
    name="lmstudio_unload_model",
    toolset="lmstudio",
    schema=LMSTUDIO_UNLOAD_MODEL_SCHEMA,
    handler=handle_unload_model,
    check_fn=check_lmstudio_available,
    emoji="🧹",
)
