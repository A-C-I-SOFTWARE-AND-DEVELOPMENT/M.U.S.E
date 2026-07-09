"""Fireworks AI provider profile — OpenAI-compatible inference."""

from providers import register_provider
from providers.base import ProviderProfile


fireworks = ProviderProfile(
    name="fireworks",
    aliases=("fireworks-ai", "fireworksai"),
    display_name="Fireworks AI",
    description="Fireworks AI — fast open-weight inference",
    signup_url="https://fireworks.ai/api-keys",
    env_vars=("FIREWORKS_API_KEY", "FIREWORKS_BASE_URL"),
    base_url="https://api.fireworks.ai/inference/v1",
    auth_type="api_key",
    default_aux_model="accounts/fireworks/models/llama-v3p3-70b-instruct",
    fallback_models=(
        "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "accounts/fireworks/models/deepseek-v3",
        "accounts/fireworks/models/qwen2p5-72b-instruct",
    ),
)

register_provider(fireworks)
