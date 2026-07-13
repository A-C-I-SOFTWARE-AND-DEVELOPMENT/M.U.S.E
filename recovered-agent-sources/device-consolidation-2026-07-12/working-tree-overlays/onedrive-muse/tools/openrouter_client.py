"""Shared OpenRouter API client for Hermes tools.

Provides a single lazy-initialized AsyncOpenAI client that all tool modules
can share.  Routes through the centralized provider router in
agent/auxiliary_client.py so auth, headers, and API format are handled
consistently.
"""

import os

_clients = {}


def get_async_client(provider: str = "openrouter"):
    """Return a shared async OpenAI-compatible client for a routed provider.

    The client is created lazily on first call and reused thereafter. Defaults
    to OpenRouter for backwards compatibility, but can also target named
    OpenAI-wire providers such as ``nvidia-all``.
    """
    key = (provider or "openrouter").strip().lower()
    # Use the built-in NVIDIA provider for auth/env loading even when config
    # names the expanded catalog provider `nvidia-all`.
    runtime_provider = "nvidia" if key == "nvidia-all" else key
    if key not in _clients:
        from agent.auxiliary_client import resolve_provider_client
        client, _model = resolve_provider_client(runtime_provider, async_mode=True)
        if client is None:
            raise ValueError(f"{key} provider credentials are not configured")
        _clients[key] = client
    return _clients[key]


def check_api_key(provider: str = "openrouter") -> bool:
    """Check whether the requested provider can build a client.

    Environment variables may be loaded from ~/.hermes/.env by Hermes config
    helpers rather than already present in os.environ, so fall back to the
    central resolver instead of checking os.environ only.
    """
    key = (provider or "openrouter").strip().lower()
    if key in {"openrouter", "openrouter-all"} and os.getenv("OPENROUTER_API_KEY"):
        return True
    if key in {"nvidia", "nvidia-all"} and os.getenv("NVIDIA_API_KEY"):
        return True

    runtime_provider = "nvidia" if key == "nvidia-all" else key
    try:
        from agent.auxiliary_client import resolve_provider_client
        client, _model = resolve_provider_client(runtime_provider, async_mode=False)
        return client is not None
    except Exception:
        return False
