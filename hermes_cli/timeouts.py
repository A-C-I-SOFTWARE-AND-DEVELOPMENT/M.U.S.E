from __future__ import annotations

import os

# Local-endpoint request-timeout tiers (seconds). Local llama.cpp/Ollama
# servers running large models on CPU can take many minutes per turn, so the
# generic remote-provider default is far too aggressive. These tiers are only
# applied for local endpoints and are never allowed to *shrink* an explicit
# user-set ``HERMES_API_TIMEOUT``.
LOCAL_REQUEST_TIMEOUT_CPU = 3600.0
LOCAL_REQUEST_TIMEOUT_GPU = 1200.0


def _local_gpu_available() -> bool:
    """Best-effort detection of whether the local endpoint is GPU-accelerated.

    There is no hardware probe wired in here (and we must not depend on one),
    so this is an opt-in signal: set ``HERMES_LOCAL_GPU=1`` (or ``true``/``yes``/
    ``on``) when the local server offloads to a GPU. Absent the signal we assume
    CPU-only, which yields the more generous (longer) timeout — the safe default
    that avoids killing a slow-but-progressing CPU generation.
    """
    raw = os.getenv("HERMES_LOCAL_GPU")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_local_request_timeout() -> float:
    """Return the request timeout (seconds) to use for a local endpoint.

    GPU-accelerated local servers get the shorter tier; CPU-only (the assumed
    default) gets the longer tier. The caller is responsible for taking the
    ``max`` with any explicit user-set timeout so this never shrinks an
    intentional override.
    """
    if _local_gpu_available():
        return LOCAL_REQUEST_TIMEOUT_GPU
    return LOCAL_REQUEST_TIMEOUT_CPU


def _coerce_timeout(raw: object) -> float | None:
    try:
        timeout = float(raw)  # ty: ignore[invalid-argument-type]  # TypeError handled below
    except (TypeError, ValueError):
        return None
    if timeout <= 0:
        return None
    return timeout


def get_provider_request_timeout(
    provider_id: str, model: str | None = None
) -> float | None:
    """Return a configured provider request timeout in seconds, if any."""
    if not provider_id:
        return None

    try:
        from hermes_cli.config import load_config_readonly
        config = load_config_readonly()
    except Exception:
        return None

    providers = config.get("providers", {}) if isinstance(config, dict) else {}
    provider_config = (
        providers.get(provider_id, {}) if isinstance(providers, dict) else {}
    )
    if not isinstance(provider_config, dict):
        return None

    model_config = _get_model_config(provider_config, model)
    if model_config is not None:
        timeout = _coerce_timeout(model_config.get("timeout_seconds"))
        if timeout is not None:
            return timeout

    return _coerce_timeout(provider_config.get("request_timeout_seconds"))


def get_provider_stale_timeout(
    provider_id: str, model: str | None = None
) -> float | None:
    """Return a configured non-stream stale timeout in seconds, if any."""
    if not provider_id:
        return None

    try:
        from hermes_cli.config import load_config_readonly
        config = load_config_readonly()
    except Exception:
        return None

    providers = config.get("providers", {}) if isinstance(config, dict) else {}
    provider_config = (
        providers.get(provider_id, {}) if isinstance(providers, dict) else {}
    )
    if not isinstance(provider_config, dict):
        return None

    model_config = _get_model_config(provider_config, model)
    if model_config is not None:
        timeout = _coerce_timeout(model_config.get("stale_timeout_seconds"))
        if timeout is not None:
            return timeout

    return _coerce_timeout(provider_config.get("stale_timeout_seconds"))


def _get_model_config(
    provider_config: dict[str, object], model: str | None
) -> dict[str, object] | None:
    if not model:
        return None

    models = provider_config.get("models", {})
    model_config = models.get(model, {}) if isinstance(models, dict) else {}
    if isinstance(model_config, dict):
        return model_config  # ty: ignore[invalid-return-type]  # isinstance-narrowed dict
    return None
