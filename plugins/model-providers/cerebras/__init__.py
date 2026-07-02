"""Cerebras provider profile.

Cerebras Inference (https://www.cerebras.ai/inference) serves open-weight
models on wafer-scale hardware at very high output speed (roughly
1,000-3,000 tok/s depending on model), behind an OpenAI-compatible API at
``https://api.cerebras.ai/v1``.

The Cerebras catalog churns quickly — several 2025-era IDs
(``llama3.1-8b``, ``llama-3.3-70b``, ``qwen-3-32b``,
``qwen-3-235b-a22b-instruct-2507``) were fully deprecated on 2026-05-27 —
so ``fallback_models`` only lists IDs current as of July 2026. The live
``/v1/models`` fetch is always preferred once a key is configured.
"""

from providers import register_provider
from providers.base import ProviderProfile


cerebras = ProviderProfile(
    name="cerebras",
    aliases=("cerebras-ai", "cerebrasai", "cerebras-cloud"),
    display_name="Cerebras",
    description="Cerebras — wafer-scale inference, ~1,000-3,000 tok/s (the speed lane)",
    signup_url="https://cloud.cerebras.ai/",
    env_vars=("CEREBRAS_API_KEY", "CEREBRAS_BASE_URL"),
    base_url="https://api.cerebras.ai/v1",
    auth_type="api_key",
    default_aux_model="gpt-oss-120b",
    fallback_models=(
        "zai-glm-4.7",
        "gpt-oss-120b",
        "qwen-3-coder-480b",
        "gemma-4-31b-it",
    ),
)

register_provider(cerebras)
