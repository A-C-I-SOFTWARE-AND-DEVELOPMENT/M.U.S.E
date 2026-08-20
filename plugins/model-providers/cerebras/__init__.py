"""Cerebras provider profile.

Cerebras Inference (https://www.cerebras.ai/inference) serves open-weight
models on wafer-scale hardware at very high output speed (roughly
1,000-3,000 tok/s depending on model), behind an OpenAI-compatible API at
``https://api.cerebras.ai/v1``.

Cerebras rotates its catalog aggressively and *removes* model IDs on short
notice — a request for a retired ID returns HTTP 404/400 ("model not
found"), which reads as "Cerebras isn't working". Because of that churn the
authoritative source is the live ``/v1/models`` fetch (the base
``ProviderProfile.fetch_models`` hits ``{base_url}/models`` with the Bearer
key), and ``fallback_models`` is kept intentionally MINIMAL — only the IDs
Cerebras has kept stable through several deprecation waves. As of 2026-07,
``qwen-3-coder-480b`` (→ migrate to GLM-4.7), ``llama-4-scout-*``,
``qwen-3-32b``, ``llama3.1-8b``, and ``qwen-3-235b-a22b-instruct-2507`` are
all retired, and ``gemma-4-31b-it`` is not a Cerebras-served ID — none of
them belong in the fallback. When in doubt, trust ``/v1/models``.
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
    # Minimal, stable-through-deprecations set. Live /v1/models is preferred
    # whenever a key is configured; this only backstops an offline picker.
    fallback_models=(
        "gpt-oss-120b",
        "zai-glm-4.7",
    ),
)

register_provider(cerebras)
