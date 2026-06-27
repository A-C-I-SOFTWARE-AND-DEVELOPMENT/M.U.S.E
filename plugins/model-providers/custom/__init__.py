"""Custom / Ollama (local) provider profile.

Covers any endpoint registered as provider="custom", including local
Ollama instances. Key quirks:
  - ollama_num_ctx → extra_body.options.num_ctx (local context window)
  - reasoning_config disabled → extra_body.think = False
"""

import logging
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

log = logging.getLogger(__name__)

# Emit the "/v1 ignores options.num_ctx" guidance only once per process so a
# long agent loop doesn't spam the log on every turn.
_NUM_CTX_V1_WARNED = False


def _warn_v1_ignores_num_ctx_once() -> None:
    """Warn once when ollama_num_ctx is set but a *remote* base_url ends in /v1.

    Ollama's OpenAI-compatible ``/v1`` shim silently ignores
    ``options.num_ctx`` (and ``keep_alive``), so the requested context window
    never takes effect and the server stays at its default (4096). Local
    Ollama endpoints route through the native /api/chat transport (which
    honors the option), so this warning targets only a remote, non-loopback
    /v1 Ollama — telling the user to set ``OLLAMA_CONTEXT_LENGTH`` server-side.
    """
    global _NUM_CTX_V1_WARNED
    if _NUM_CTX_V1_WARNED:
        return
    try:
        from hermes_cli.config import load_config_readonly

        cfg = load_config_readonly()
    except Exception:
        return
    model_cfg = cfg.get("model") if isinstance(cfg, dict) else None
    base_url = ""
    if isinstance(model_cfg, dict):
        base_url = str(model_cfg.get("base_url") or "").strip()
    if not base_url.rstrip("/").lower().endswith("/v1"):
        return
    # Local Ollama endpoints route through the native /api/chat transport
    # (it honors options.num_ctx), so the /v1 caveat does not apply to them.
    # Only a remote, non-loopback /v1 Ollama is affected.
    _bl = base_url.lower()
    if ":11434" in _bl or any(
        h in _bl for h in ("127.0.0.1", "localhost", "::1", "0.0.0.0")
    ):
        return
    _NUM_CTX_V1_WARNED = True
    log.warning(
        "ollama_num_ctx is set but this remote base_url ends in /v1; Ollama's "
        "OpenAI compatibility shim ignores options.num_ctx so the context "
        "window stays at the server default. Set OLLAMA_CONTEXT_LENGTH "
        "server-side on that host (e.g. `OLLAMA_CONTEXT_LENGTH=%s ollama "
        "serve`).",
        "<num_ctx>",
    )


class CustomProfile(ProviderProfile):
    """Custom/Ollama local provider — think=false and num_ctx support."""

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        ollama_num_ctx: int | None = None,
        **ctx: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        extra_body: dict[str, Any] = {}

        # Ollama context window
        if ollama_num_ctx:
            options = extra_body.get("options", {})
            options["num_ctx"] = ollama_num_ctx
            extra_body["options"] = options
            # Interim guidance: the /v1 shim drops options.num_ctx. Warn once
            # so users aren't silently capped at the 4096 server default.
            _warn_v1_ignores_num_ctx_once()

        # Disable thinking when reasoning is turned off
        if reasoning_config and isinstance(reasoning_config, dict):
            _effort = (reasoning_config.get("effort") or "").strip().lower()
            _enabled = reasoning_config.get("enabled", True)
            if _effort == "none" or _enabled is False:
                extra_body["think"] = False

        return extra_body, {}

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Custom/Ollama: base_url is user-configured; fetch if set."""
        if not self.base_url:
            return None
        return super().fetch_models(api_key=api_key, timeout=timeout)


custom = CustomProfile(
    name="custom",
    aliases=(
        "ollama",
        "local",
        "vllm",
        "llamacpp",
        "llama.cpp",
        "llama-cpp",
    ),
    env_vars=(),  # No fixed key — custom endpoint
    base_url="",  # User-configured
)

register_provider(custom)
