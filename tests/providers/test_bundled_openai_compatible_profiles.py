"""Tests for five bundled OpenAI-compatible provider plugins.

Cerebras, Groq, Mistral, Perplexity and Together all speak the OpenAI wire
format behind their own base URLs, so each is a plain ``ProviderProfile``
registered from ``plugins/model-providers/<name>/``. Nothing else in the
codebase needs to change for them to work -- ``auth``, ``config``, ``models``,
``doctor`` and the chat transport all read the registry.

That is exactly why they need a test: a profile that silently fails to
register, or whose alias collides with another provider's, produces no error
at import time. It just quietly stops resolving.
"""

import pytest

from providers import get_provider_profile, list_providers

# name -> (base_url, first env var, aliases, default aux model)
EXPECTED = {
    "cerebras": (
        "https://api.cerebras.ai/v1",
        "CEREBRAS_API_KEY",
        ("cerebras-ai", "cerebrasai", "cerebras-cloud"),
        "gpt-oss-120b",
    ),
    "groq": (
        "https://api.groq.com/openai/v1",
        "GROQ_API_KEY",
        ("groq-cloud", "groqcloud"),
        "llama-3.3-70b-versatile",
    ),
    "mistral": (
        "https://api.mistral.ai/v1",
        "MISTRAL_API_KEY",
        ("mistral-ai", "mistralai", "codestral"),
        "mistral-small-latest",
    ),
    "perplexity": (
        "https://api.perplexity.ai",
        "PERPLEXITY_API_KEY",
        ("pplx", "perplexity-ai"),
        "sonar",
    ),
    "together": (
        "https://api.together.xyz/v1",
        "TOGETHER_API_KEY",
        ("together-ai", "togetherai"),
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    ),
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_profile_registered(name: str) -> None:
    base_url, env_var, _aliases, aux = EXPECTED[name]
    profile = get_provider_profile(name)
    assert profile is not None, f"{name} did not register"
    assert profile.name == name
    assert profile.base_url == base_url
    assert profile.auth_type == "api_key"
    assert env_var in profile.env_vars
    assert profile.default_aux_model == aux
    # An empty fallback list makes the offline model picker useless.
    assert profile.fallback_models, f"{name} ships no fallback models"


@pytest.mark.parametrize(
    ("name", "alias"),
    [(n, a) for n, (_, _, aliases, _) in EXPECTED.items() for a in aliases],
)
def test_aliases_resolve_to_their_profile(name: str, alias: str) -> None:
    assert get_provider_profile(alias) is get_provider_profile(name)


def test_no_alias_collides_across_the_registry() -> None:
    """Two providers claiming one alias is a silent last-writer-wins bug.

    Registration order decides the winner, so the loser simply stops
    resolving under that name with nothing logged.
    """
    owner: dict[str, str] = {}
    collisions: list[str] = []
    for profile in list_providers():
        for handle in (profile.name, *profile.aliases):
            key = handle.lower()
            if key in owner and owner[key] != profile.name:
                collisions.append(f"{handle!r}: {owner[key]} vs {profile.name}")
            owner.setdefault(key, profile.name)
    assert not collisions, "aliases claimed by more than one provider: " + "; ".join(
        collisions
    )
