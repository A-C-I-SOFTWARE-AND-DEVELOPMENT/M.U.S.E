"""Together AI provider profile — multi-model OpenAI-compatible cloud."""

from providers import register_provider
from providers.base import ProviderProfile


together = ProviderProfile(
    name="together",
    aliases=("together-ai", "togetherai"),
    display_name="Together AI",
    description="Together AI — open-weight models at cloud scale",
    signup_url="https://api.together.xyz/settings/api-keys",
    env_vars=("TOGETHER_API_KEY", "TOGETHER_BASE_URL"),
    base_url="https://api.together.xyz/v1",
    auth_type="api_key",
    default_aux_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
    fallback_models=(
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "deepseek-ai/DeepSeek-V3",
        "Qwen/Qwen2.5-72B-Instruct-Turbo",
        "google/gemma-2-27b-it",
    ),
)

register_provider(together)
