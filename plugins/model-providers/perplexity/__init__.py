"""Perplexity provider profile — search-augmented OpenAI-compatible chat."""

from providers import register_provider
from providers.base import ProviderProfile


perplexity = ProviderProfile(
    name="perplexity",
    aliases=("pplx", "perplexity-ai"),
    display_name="Perplexity",
    description="Perplexity — search-augmented chat with citations",
    signup_url="https://www.perplexity.ai/settings/api",
    env_vars=("PERPLEXITY_API_KEY", "PERPLEXITY_BASE_URL"),
    base_url="https://api.perplexity.ai",
    auth_type="api_key",
    default_aux_model="sonar",
    fallback_models=(
        "sonar",
        "sonar-pro",
        "sonar-reasoning",
    ),
)

register_provider(perplexity)
