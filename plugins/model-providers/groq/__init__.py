"""Groq provider profile — ultra-fast OpenAI-compatible inference."""

from providers import register_provider
from providers.base import ProviderProfile


groq = ProviderProfile(
    name="groq",
    aliases=("groq-cloud", "groqcloud"),
    display_name="Groq",
    description="Groq — ultra-fast open-weight inference (~500+ tok/s)",
    signup_url="https://console.groq.com/keys",
    env_vars=("GROQ_API_KEY", "GROQ_BASE_URL"),
    base_url="https://api.groq.com/openai/v1",
    auth_type="api_key",
    default_aux_model="llama-3.3-70b-versatile",
    fallback_models=(
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "qwen/qwen3-32b",
    ),
)

register_provider(groq)
