"""Tests for Ollama num_ctx context length detection and injection.

Covers:
  agent/model_metadata.py — query_ollama_num_ctx()
  run_agent.py — _ollama_num_ctx detection + extra_body injection
  agent/chat_completion_helpers.py — opt-in native /api/chat transport
    (ACTION #6) and opt-in fallback-on-timeout gate (ACTION #8)
"""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from agent.model_metadata import query_ollama_num_ctx


# ═══════════════════════════════════════════════════════════════════════
# Level 1: query_ollama_num_ctx — Ollama API interaction
# ═══════════════════════════════════════════════════════════════════════


def _mock_httpx_client(show_response_data, status_code=200):
    """Create a mock httpx.Client context manager that returns given /api/show data."""
    mock_resp = MagicMock(status_code=status_code)
    mock_resp.json.return_value = show_response_data
    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_client)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx, mock_client


class TestQueryOllamaNumCtx:
    """Test the Ollama /api/show context length query."""

    def test_returns_context_from_model_info(self):
        """Should extract context_length from GGUF model_info metadata."""
        show_data = {
            "model_info": {"llama.context_length": 131072},
            "parameters": "",
        }
        mock_ctx, _ = _mock_httpx_client(show_data)

        with patch("agent.model_metadata.detect_local_server_type", return_value="ollama"):
            # httpx is imported inside the function — patch the module import
            import httpx
            with patch.object(httpx, "Client", return_value=mock_ctx):
                result = query_ollama_num_ctx("llama3.1:8b", "http://localhost:11434/v1")

        assert result == 131072

    def test_prefers_explicit_num_ctx_from_modelfile(self):
        """If the Modelfile sets num_ctx explicitly, that should take priority."""
        show_data = {
            "model_info": {"llama.context_length": 131072},
            "parameters": "num_ctx 32768\ntemperature 0.7",
        }
        mock_ctx, _ = _mock_httpx_client(show_data)

        with patch("agent.model_metadata.detect_local_server_type", return_value="ollama"):
            import httpx
            with patch.object(httpx, "Client", return_value=mock_ctx):
                result = query_ollama_num_ctx("custom-model", "http://localhost:11434")

        assert result == 32768

    def test_returns_none_for_non_ollama_server(self):
        """Should return None if the server is not Ollama."""
        with patch("agent.model_metadata.detect_local_server_type", return_value="lm-studio"):
            result = query_ollama_num_ctx("model", "http://localhost:1234")
        assert result is None

    def test_returns_none_on_connection_error(self):
        """Should return None if the server is unreachable."""
        with patch("agent.model_metadata.detect_local_server_type", side_effect=Exception("timeout")):
            result = query_ollama_num_ctx("model", "http://localhost:11434")
        assert result is None

    def test_returns_none_on_404(self):
        """Should return None if the model is not found."""
        mock_ctx, _ = _mock_httpx_client({}, status_code=404)

        with patch("agent.model_metadata.detect_local_server_type", return_value="ollama"):
            import httpx
            with patch.object(httpx, "Client", return_value=mock_ctx):
                result = query_ollama_num_ctx("nonexistent", "http://localhost:11434")

        assert result is None

    def test_strips_provider_prefix(self):
        """Should strip 'local:' prefix from model name before querying."""
        show_data = {
            "model_info": {"qwen2.context_length": 32768},
            "parameters": "",
        }
        mock_ctx, mock_client = _mock_httpx_client(show_data)

        with patch("agent.model_metadata.detect_local_server_type", return_value="ollama"):
            import httpx
            with patch.object(httpx, "Client", return_value=mock_ctx):
                result = query_ollama_num_ctx("local:qwen2.5:7b", "http://localhost:11434/v1")

        # Verify the post was called with stripped name (no "local:" prefix)
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["name"] == "qwen2.5:7b" or call_args[0][1] is not None
        assert result == 32768

    def test_handles_qwen2_architecture_key(self):
        """Different model architectures use different key prefixes in model_info."""
        show_data = {
            "model_info": {"qwen2.context_length": 65536},
            "parameters": "",
        }
        mock_ctx, _ = _mock_httpx_client(show_data)

        with patch("agent.model_metadata.detect_local_server_type", return_value="ollama"):
            import httpx
            with patch.object(httpx, "Client", return_value=mock_ctx):
                result = query_ollama_num_ctx("qwen2.5:32b", "http://localhost:11434")

        assert result == 65536

    def test_returns_none_when_model_info_empty(self):
        """Should return None if model_info has no context_length key."""
        show_data = {
            "model_info": {"llama.embedding_length": 4096},
            "parameters": "",
        }
        mock_ctx, _ = _mock_httpx_client(show_data)

        with patch("agent.model_metadata.detect_local_server_type", return_value="ollama"):
            import httpx
            with patch.object(httpx, "Client", return_value=mock_ctx):
                result = query_ollama_num_ctx("model", "http://localhost:11434")

        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# Level 2: native Ollama /api/chat transport (ACTION #6, opt-in)
# ═══════════════════════════════════════════════════════════════════════

from agent import chat_completion_helpers as cch  # noqa: E402


def _agent_stub(*, base_url="http://localhost:11434/v1", api_mode="chat_completions"):
    """Minimal AIAgent stand-in exposing only what the native path touches."""
    return SimpleNamespace(
        api_mode=api_mode,
        base_url=base_url,
        provider="custom",
        model="qwen3.5:9b",
        api_key="no-key-required",
        _interrupt_requested=False,
        _primary_runtime={"provider": "custom"},
        _resolved_api_call_timeout=lambda: 60.0,
        _touch_activity=lambda *a, **k: None,
        _capture_rate_limits=lambda *a, **k: None,
        _fire_stream_delta=lambda *a, **k: None,
        _fire_reasoning_delta=lambda *a, **k: None,
    )


class TestNativeOllamaGate:
    """Native /api/chat is used for any Ollama (:11434) endpoint — no flag."""

    def test_native_default_on_for_local_ollama(self):
        # localhost:11434 + chat_completions → native, no env/config needed.
        assert cch._should_route_native_ollama(_agent_stub()) is True

    def test_native_on_for_remote_ollama_default_port(self):
        agent = _agent_stub(base_url="http://10.0.0.5:11434/v1")
        assert cch._should_route_native_ollama(agent) is True

    def test_gate_off_for_other_loopback_servers(self):
        # llama.cpp (:8080) / LM Studio (:1234) share loopback but are NOT
        # Ollama — they must stay on the unchanged /v1 path.
        for url in ("http://127.0.0.1:8080/v1", "http://localhost:1234/v1"):
            assert cch._should_route_native_ollama(_agent_stub(base_url=url)) is False

    def test_gate_off_for_non_local_endpoint(self):
        agent = _agent_stub(base_url="https://api.openrouter.ai/api/v1")
        assert cch._should_route_native_ollama(agent) is False

    def test_gate_off_for_non_chat_completions_mode(self):
        agent = _agent_stub(api_mode="anthropic_messages")
        assert cch._should_route_native_ollama(agent) is False


class TestNativeOllamaPayload:
    """The native payload carries options.num_ctx (the whole point of #6)."""

    def test_url_strips_v1_and_appends_api_chat(self):
        assert cch._ollama_native_url("http://localhost:11434/v1") == (
            "http://localhost:11434/api/chat"
        )
        assert cch._ollama_native_url("http://localhost:11434") == (
            "http://localhost:11434/api/chat"
        )

    def test_payload_lifts_num_ctx_from_extra_body_options(self):
        api_kwargs = {
            "model": "qwen3.5:9b",
            "messages": [{"role": "user", "content": "hi"}],
            "extra_body": {"options": {"num_ctx": 16384}, "think": False},
            "max_tokens": 512,
        }
        payload = cch._build_ollama_native_payload(api_kwargs)
        assert payload["options"]["num_ctx"] == 16384
        assert payload["think"] is False
        # max_tokens maps to Ollama's num_predict.
        assert payload["options"]["num_predict"] == 512

    def test_keep_alive_promoted_to_top_level(self):
        api_kwargs = {
            "model": "m",
            "messages": [],
            "extra_body": {"options": {"num_ctx": 8192, "keep_alive": "30m"}},
        }
        payload = cch._build_ollama_native_payload(api_kwargs)
        assert payload["keep_alive"] == "30m"
        assert "keep_alive" not in payload["options"]
        assert payload["options"]["num_ctx"] == 8192


class TestNativeOllamaNonStreamingWire:
    """When the flag is ON, the request hitting the wire carries num_ctx."""

    def test_non_streaming_request_carries_num_ctx(self):
        agent = _agent_stub()
        api_kwargs = {
            "model": "qwen3.5:9b",
            "messages": [{"role": "user", "content": "hi"}],
            "extra_body": {"options": {"num_ctx": 24576}},
        }

        captured = {}
        mock_resp = MagicMock(status_code=200)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "model": "qwen3.5:9b",
            "message": {"role": "assistant", "content": "hello"},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 5,
            "eval_count": 3,
        }
        mock_client = MagicMock()

        def _post(url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            return mock_resp

        mock_client.post.side_effect = _post
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_client)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        import httpx
        with patch.object(httpx, "Client", return_value=mock_ctx):
            resp = cch._ollama_native_chat(agent, api_kwargs, stream=False)

        # Wire assertions: native endpoint + options.num_ctx present.
        assert captured["url"] == "http://localhost:11434/api/chat"
        assert captured["json"]["options"]["num_ctx"] == 24576
        assert captured["json"]["stream"] is False
        # Response is OpenAI-shaped for the rest of the agent loop.
        assert resp.choices[0].message.content == "hello"
        assert resp.choices[0].finish_reason == "stop"
        assert resp.usage.total_tokens == 8

    def test_tool_calls_map_to_finish_reason(self):
        agent = _agent_stub()
        api_kwargs = {"model": "m", "messages": [], "extra_body": {}}

        mock_resp = MagicMock(status_code=200)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "model": "m",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "search", "arguments": {"q": "x"}}}
                ],
            },
            "done": True,
            "done_reason": "stop",
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_client)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        import httpx
        with patch.object(httpx, "Client", return_value=mock_ctx):
            resp = cch._ollama_native_chat(agent, api_kwargs, stream=False)

        choice = resp.choices[0]
        assert choice.finish_reason == "tool_calls"
        assert choice.message.tool_calls[0].function.name == "search"
        # arguments serialized to a JSON string (OpenAI shape).
        assert choice.message.tool_calls[0].function.arguments == '{"q": "x"}'


class TestNonOllamaKeepsV1Path:
    """Non-Ollama endpoints never divert to the native /api/chat path."""

    def test_non_ollama_endpoint_keeps_v1_path(self):
        agent = _agent_stub(base_url="https://api.openrouter.ai/api/v1")
        assert cch._should_route_native_ollama(agent) is False


# ═══════════════════════════════════════════════════════════════════════
# Level 3: opt-in fallback-on-timeout gate (ACTION #8)
# ═══════════════════════════════════════════════════════════════════════


class TestFallbackOnTimeoutGate:
    """fallback-on-timeout is ON by default; opt out per provider."""

    def test_enabled_by_default(self):
        with patch("hermes_cli.config.load_config_readonly", return_value={}):
            assert cch.fallback_on_timeout_enabled("custom") is True

    def test_opt_out_via_provider_config(self):
        cfg = {"providers": {"custom": {"enable_fallback_on_timeout": False}}}
        with patch("hermes_cli.config.load_config_readonly", return_value=cfg):
            assert cch.fallback_on_timeout_enabled("custom") is False

    def test_explicit_enable_still_true(self):
        cfg = {"providers": {"custom": {"enable_fallback_on_timeout": True}}}
        with patch("hermes_cli.config.load_config_readonly", return_value=cfg):
            assert cch.fallback_on_timeout_enabled("custom") is True

    def test_other_provider_defaults_enabled(self):
        cfg = {"providers": {"custom": {"enable_fallback_on_timeout": False}}}
        with patch("hermes_cli.config.load_config_readonly", return_value=cfg):
            # openrouter has no explicit setting → default ON.
            assert cch.fallback_on_timeout_enabled("openrouter") is True

    def test_timeout_reason_blocked_when_flag_off(self):
        """try_activate_fallback(reason=timeout) returns False with flag off,
        without advancing the fallback chain (default behavior preserved)."""
        from agent.error_classifier import FailoverReason

        agent = SimpleNamespace(
            provider="custom",
            _primary_runtime={"provider": "custom"},
            _fallback_index=0,
            _fallback_chain=[{"provider": "openrouter", "model": "x/y"}],
        )
        with patch.object(cch, "fallback_on_timeout_enabled", return_value=False):
            assert cch.try_activate_fallback(agent, reason=FailoverReason.timeout) is False
        # Chain index must NOT advance — no escalation attempted.
        assert agent._fallback_index == 0
