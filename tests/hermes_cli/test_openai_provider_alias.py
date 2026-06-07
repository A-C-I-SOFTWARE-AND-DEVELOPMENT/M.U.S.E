"""Regression: the `openai` provider must mean real OpenAI, not OpenRouter.

`ALIASES` used to map ``"openai" -> "openrouter"``, so requesting provider
``openai`` (or any GPT model, which `model_normalize` resolves to the ``openai``
vendor) was silently routed through the OpenRouter aggregator. These tests lock
in that ``openai`` resolves to the real OpenAI endpoint while the OpenRouter
aggregator keeps working independently.
"""

from urllib.parse import urlparse

from hermes_cli.providers import get_provider, normalize_provider


def test_openai_does_not_alias_to_openrouter():
    assert normalize_provider("openai") == "openai"


def test_openai_resolves_to_real_openai_endpoint():
    pdef = get_provider("openai")
    assert pdef is not None
    assert urlparse(pdef.base_url).hostname == "api.openai.com"
    assert "OPENAI_API_KEY" in pdef.api_key_env_vars
    assert pdef.is_aggregator is False
    assert pdef.name == "OpenAI"


def test_openrouter_aggregator_still_resolves():
    # The fix must not disturb the real aggregator.
    assert normalize_provider("openrouter") == "openrouter"
    router = get_provider("openrouter")
    assert router is not None
    assert router.is_aggregator is True
    assert urlparse(router.base_url).hostname == "openrouter.ai"
