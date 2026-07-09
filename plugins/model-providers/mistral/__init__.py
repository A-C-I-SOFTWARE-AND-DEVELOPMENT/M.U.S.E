"""Mistral AI provider profile — first-party OpenAI-compatible chat.

``MISTRAL_API_KEY`` is also used by Voxtral TTS/STT tooling. Setting the key
enables both inference (``provider: mistral``) and those voice tools.
"""

from providers import register_provider
from providers.base import ProviderProfile


mistral = ProviderProfile(
    name="mistral",
    aliases=("mistral-ai", "mistralai", "codestral"),
    display_name="Mistral AI",
    description="Mistral AI — first-party Mistral / Codestral models",
    signup_url="https://console.mistral.ai/",
    env_vars=("MISTRAL_API_KEY", "MISTRAL_BASE_URL"),
    base_url="https://api.mistral.ai/v1",
    auth_type="api_key",
    default_aux_model="mistral-small-latest",
    fallback_models=(
        "mistral-small-latest",
        "mistral-large-latest",
        "codestral-latest",
        "ministral-8b-latest",
    ),
)

register_provider(mistral)
