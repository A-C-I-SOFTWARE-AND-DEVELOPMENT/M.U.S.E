"""switch_model unloads the previous LM Studio model to free VRAM.

When leaving an LM Studio model (different model, or a different provider),
switch_model should call unload_lmstudio_model with the OLD model + endpoint
before preloading the new one. Staying on the same LM Studio model must not
unload. All hermetic — no network.
"""

from unittest.mock import MagicMock, patch

from run_agent import AIAgent


def _make_lmstudio_agent(model="publisher/old-model"):
    agent = AIAgent.__new__(AIAgent)
    agent.model = model
    agent.provider = "lmstudio"
    agent.base_url = "http://localhost:1234/v1"
    agent.api_key = "lm-key"
    agent.api_mode = "chat_completions"
    agent.client = MagicMock()
    agent.quiet_mode = True
    agent._config_context_length = None
    agent._primary_runtime = {}
    agent._transport_cache = {}
    agent.context_compressor = None  # skip the compressor-update branch
    return agent


def _switch(agent, new_model, new_provider, base_url):
    """Drive switch_model with the network-touching collaborators patched out."""
    with patch.object(AIAgent, "_ensure_lmstudio_runtime_loaded"), \
         patch.object(AIAgent, "_create_openai_client", return_value=MagicMock()), \
         patch.object(AIAgent, "_anthropic_prompt_cache_policy", return_value=(False, False)), \
         patch("hermes_cli.models.unload_lmstudio_model") as mock_unload:
        agent.switch_model(
            new_model, new_provider, api_key="new-key", base_url=base_url,
            api_mode="chat_completions",
        )
    return mock_unload


def test_unloads_old_model_when_switching_lmstudio_models():
    agent = _make_lmstudio_agent("publisher/old-model")
    mock_unload = _switch(
        agent, "publisher/new-model", "lmstudio", "http://localhost:1234/v1"
    )
    mock_unload.assert_called_once()
    args = mock_unload.call_args.args
    # old model + old endpoint + old key (captured before the swap)
    assert args[0] == "publisher/old-model"
    assert args[1] == "http://localhost:1234/v1"
    assert args[2] == "lm-key"


def test_unloads_old_model_when_switching_to_cloud_provider():
    agent = _make_lmstudio_agent("publisher/old-model")
    mock_unload = _switch(
        agent, "anthropic/claude", "openrouter", "https://openrouter.ai/api/v1"
    )
    mock_unload.assert_called_once()
    assert mock_unload.call_args.args[0] == "publisher/old-model"


def test_no_unload_when_staying_on_same_lmstudio_model():
    agent = _make_lmstudio_agent("publisher/same-model")
    mock_unload = _switch(
        agent, "publisher/same-model", "lmstudio", "http://localhost:1234/v1"
    )
    mock_unload.assert_not_called()


def test_no_unload_when_old_provider_is_not_lmstudio():
    agent = _make_lmstudio_agent("publisher/old-model")
    agent.provider = "openrouter"
    agent.base_url = "https://openrouter.ai/api/v1"
    mock_unload = _switch(
        agent, "publisher/new-model", "lmstudio", "http://localhost:1234/v1"
    )
    mock_unload.assert_not_called()
