"""Tests for the model-invocable Mixture-of-Agents fan-out tool.

The tool's real caller is the model, via the tool registry. These tests pin the
registration seam (so that caller can actually reach it) and the rebase itself:
the panel comes from the configured MoA presets and the calls go through
``agent/moa_loop.py``'s runtime, not a hardcoded provider.
"""

import json
from types import SimpleNamespace

import pytest

import agent.moa_loop as moa_loop
import tools.mixture_of_agents_tool as moa_tool
from tools.registry import registry


PRESET_CONFIG = {
    "presets": {
        "default": {
            "reference_models": [
                {"provider": "ollama", "model": "qwen3:8b"},
                {"provider": "anthropic", "model": "claude-sonnet-4-5"},
            ],
            "aggregator": {"provider": "openrouter", "model": "some/aggregator"},
            "reference_temperature": 0.6,
            "aggregator_temperature": 0.4,
            "reference_max_tokens": 600,
        },
        "local-only": {
            "reference_models": [{"provider": "ollama", "model": "qwen3:8b"}],
            "aggregator": {"provider": "ollama", "model": "qwen3:32b"},
        },
    },
    "default_preset": "default",
}


class _FanOutSpy:
    """Stand-in for ``_run_references_parallel`` that records what it saw."""

    def __init__(self, answers=None, failures=()):
        self.answers = answers or ["answer A", "answer B"]
        self.failures = set(failures)
        self.calls = []

    def __call__(self, reference_models, ref_messages, **kwargs):
        self.calls.append(
            {"slots": reference_models, "messages": ref_messages, "kwargs": kwargs}
        )
        out = []
        for idx, slot in enumerate(reference_models):
            label = moa_loop._slot_label(slot)
            if label in self.failures:
                text = "[failed: boom]"
            else:
                text = self.answers[idx % len(self.answers)]
            out.append((label, text, None))
        return out


@pytest.fixture
def wired(monkeypatch):
    """Wire the tool onto stubbed MoA machinery and return the spies."""
    fanout = _FanOutSpy()
    fusion_calls = []

    def _fake_call_llm(**kwargs):
        fusion_calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="FUSED"))]
        )

    monkeypatch.setattr(moa_tool, "_moa_config", lambda: PRESET_CONFIG)
    monkeypatch.setattr(moa_loop, "_run_references_parallel", fanout)
    monkeypatch.setattr(moa_loop, "_slot_runtime", lambda slot: {
        "provider": slot["provider"], "model": slot["model"]
    })
    monkeypatch.setattr(moa_loop, "_aggregator_reasoning_config", lambda slot: None)
    # Cache-control decoration is exercised by the provider path's own
    # tests; here it would rewrite message content into block form.
    monkeypatch.setattr(
        moa_loop, "_maybe_apply_moa_cache_control",
        lambda messages, runtime, **kw: messages,
    )
    monkeypatch.setattr("agent.auxiliary_client.call_llm", _fake_call_llm)
    return SimpleNamespace(fanout=fanout, fusion_calls=fusion_calls)


# --- registration seam ------------------------------------------------------

def test_tool_is_registered_and_schema_renders():
    entry = registry.get_entry("mixture_of_agents")
    assert entry is not None
    assert entry.toolset == "moa"
    assert entry.is_async is False

    schema = registry.get_schema("mixture_of_agents")
    assert schema["name"] == "mixture_of_agents"
    assert schema["parameters"]["required"] == ["user_prompt"]
    assert set(schema["parameters"]["properties"]) == {
        "user_prompt", "preset", "reference_models", "aggregator_model",
        "rounds", "strategy",
    }
    assert "mixture_of_agents" in registry.get_tool_names_for_toolset("moa")


# --- the rebase: preset-driven panel, moa_loop runtime ----------------------

def test_default_panel_comes_from_the_configured_preset(wired):
    result = json.loads(moa_tool.mixture_of_agents_tool("why is the sky blue?"))
    assert result["success"] is True
    assert result["response"] == "FUSED"
    assert result["metadata"]["reference_models"] == [
        "ollama:qwen3:8b", "anthropic:claude-sonnet-4-5",
    ]
    assert result["metadata"]["aggregator_model"] == "openrouter:some/aggregator"

    # Preset sampling/limit settings are threaded into the fan-out, not
    # reinvented by the tool.
    kwargs = wired.fanout.calls[0]["kwargs"]
    assert kwargs["temperature"] == 0.6
    assert kwargs["max_tokens"] == 600

    # The synthesis call runs on the aggregator slot's resolved runtime.
    assert wired.fusion_calls[0]["provider"] == "openrouter"
    assert wired.fusion_calls[0]["model"] == "some/aggregator"
    assert wired.fusion_calls[0]["temperature"] == 0.4
    # Never capped by default: a hardcoded cap truncates long syntheses.
    assert wired.fusion_calls[0]["max_tokens"] is None


def test_named_preset_selects_its_own_panel(wired):
    result = json.loads(
        moa_tool.mixture_of_agents_tool("q", preset="local-only")
    )
    assert result["metadata"]["reference_models"] == ["ollama:qwen3:8b"]
    assert result["metadata"]["aggregator_model"] == "ollama:qwen3:32b"


def test_unknown_preset_is_a_readable_error(wired):
    result = json.loads(moa_tool.mixture_of_agents_tool("q", preset="nope"))
    assert result["success"] is False
    assert "nope" in result["error"]


def test_caller_may_override_the_panel_with_provider_model_strings(wired):
    result = json.loads(
        moa_tool.mixture_of_agents_tool(
            "q",
            reference_models=["ollama:qwen3:8b", "openai:gpt-5.5"],
            aggregator_model="anthropic:claude-opus-4-5",
        )
    )
    assert result["metadata"]["reference_models"] == [
        "ollama:qwen3:8b", "openai:gpt-5.5",
    ]
    assert wired.fusion_calls[0]["model"] == "claude-opus-4-5"
    # The first colon splits provider from model, so colon-bearing model ids
    # (ollama tags) survive intact.
    assert wired.fanout.calls[0]["slots"][0] == {
        "provider": "ollama", "model": "qwen3:8b", "enabled": True,
    }


def test_recursive_moa_slots_are_rejected(wired):
    result = json.loads(
        moa_tool.mixture_of_agents_tool("q", reference_models=["moa:default"])
    )
    assert result["success"] is False
    assert "moa" in result["error"]
    assert not wired.fanout.calls


def test_unparseable_override_errors_instead_of_silently_using_defaults(wired):
    result = json.loads(
        moa_tool.mixture_of_agents_tool("q", reference_models=["gpt-5.5"])
    )
    assert result["success"] is False
    assert "gpt-5.5" in result["error"]
    assert not wired.fanout.calls


def test_empty_prompt_is_rejected(wired):
    result = json.loads(moa_tool.mixture_of_agents_tool("   "))
    assert result["success"] is False
    assert not wired.fanout.calls


# --- rounds / strategy ------------------------------------------------------

def test_second_round_shows_the_panel_the_previous_fusion(wired):
    result = json.loads(moa_tool.mixture_of_agents_tool("q", rounds=2))
    assert result["success"] is True
    assert len(wired.fanout.calls) == 2
    assert len(wired.fusion_calls) == 2

    first_view = wired.fanout.calls[0]["messages"]
    assert [m["role"] for m in first_view] == ["user"]

    second_view = wired.fanout.calls[1]["messages"]
    assert [m["role"] for m in second_view] == ["user", "assistant", "user"]
    assert second_view[1]["content"] == "FUSED"
    assert result["metadata"]["rounds_executed"][1]["refined_previous_round"] is True


def test_rounds_are_clamped_to_the_maximum(wired):
    json.loads(moa_tool.mixture_of_agents_tool("q", rounds=99))
    assert len(wired.fanout.calls) == moa_tool.MAX_ROUNDS


def test_raw_strategy_skips_synthesis(wired):
    result = json.loads(
        moa_tool.mixture_of_agents_tool("q", strategy="raw", rounds=3)
    )
    assert result["success"] is True
    assert wired.fusion_calls == []
    assert result["metadata"]["aggregator_model"] is None
    assert "### ollama:qwen3:8b" in result["response"]
    assert "answer A" in result["response"]
    # Refinement needs a fusion to refine, so raw never runs extra rounds.
    assert len(wired.fanout.calls) == 1


def test_too_many_reference_models_is_rejected(wired):
    panel = [f"ollama:model-{i}" for i in range(moa_tool.MAX_REFERENCE_MODELS + 1)]
    result = json.loads(
        moa_tool.mixture_of_agents_tool("q", reference_models=panel)
    )
    assert result["success"] is False
    assert not wired.fanout.calls


def test_a_large_configured_preset_is_not_rejected(wired, monkeypatch):
    """The panel cap bounds the caller, never the user's own preset.

    ``_run_references_parallel`` queues slots past its worker cap, so a
    hand-configured preset with more advisors than workers must still run.
    """
    big = {
        "presets": {
            "default": {
                "reference_models": [
                    {"provider": "ollama", "model": f"m{i}"}
                    for i in range(moa_tool.MAX_REFERENCE_MODELS + 1)
                ],
                "aggregator": {"provider": "ollama", "model": "agg"},
            }
        }
    }
    monkeypatch.setattr(moa_tool, "_moa_config", lambda: big)
    result = json.loads(moa_tool.mixture_of_agents_tool("q"))
    assert result["success"] is True
    assert len(result["metadata"]["reference_models"]) == (
        moa_tool.MAX_REFERENCE_MODELS + 1
    )


@pytest.mark.parametrize(
    "override",
    [
        "openai:gpt-5.5",
        {"provider": "openai", "model": "gpt-5.5"},
        '["openai:gpt-5.5"]',
    ],
)
def test_a_non_array_override_is_honoured_not_silently_dropped(wired, override):
    """Models emit a bare string/object/JSON-array where the schema says array.

    Falling back to the preset there would answer with a panel the caller did
    not ask for, without saying so.
    """
    result = json.loads(
        moa_tool.mixture_of_agents_tool("q", reference_models=override)
    )
    assert result["success"] is True
    assert result["metadata"]["reference_models"] == ["openai:gpt-5.5"]


# --- degradation ------------------------------------------------------------

def test_partial_failure_is_disclosed_in_the_response(wired):
    wired.fanout.failures = {"anthropic:claude-sonnet-4-5"}
    result = json.loads(moa_tool.mixture_of_agents_tool("q"))
    assert result["success"] is True
    assert result["metadata"]["failed_models"] == ["anthropic:claude-sonnet-4-5"]
    assert "Reference models unavailable" in result["response"]
    # Only the surviving advisor reaches the aggregator.
    fused_prompt = wired.fusion_calls[0]["messages"][0]["content"]
    assert "[ollama:qwen3:8b]" in fused_prompt
    assert "[anthropic:claude-sonnet-4-5]" not in fused_prompt


def test_total_failure_returns_an_error_rather_than_fusing_nothing(wired):
    wired.fanout.failures = {"ollama:qwen3:8b", "anthropic:claude-sonnet-4-5"}
    result = json.loads(moa_tool.mixture_of_agents_tool("q"))
    assert result["success"] is False
    assert "Reference models unavailable" in result["error"]
    assert wired.fusion_calls == []


def test_a_later_round_losing_the_panel_keeps_the_earlier_fusion(wired, monkeypatch):
    """Round 2 failing wholesale means no refinement, not no answer."""
    seen = {"n": 0}
    spy = wired.fanout

    def _flaky(reference_models, ref_messages, **kwargs):
        seen["n"] += 1
        out = spy(reference_models, ref_messages, **kwargs)
        if seen["n"] == 1:
            return out
        return [(label, "[failed: rate limit]", acct) for label, _t, acct in out]

    monkeypatch.setattr(moa_loop, "_run_references_parallel", _flaky)

    result = json.loads(moa_tool.mixture_of_agents_tool("q", rounds=2))
    assert result["success"] is True
    assert result["response"].startswith("FUSED")
    assert "Reference models unavailable" in result["response"]
    assert len(wired.fusion_calls) == 1


def test_empty_synthesis_falls_back_to_the_panel(wired, monkeypatch):
    monkeypatch.setattr(
        "agent.auxiliary_client.call_llm",
        lambda **kw: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=""))]
        ),
    )
    result = json.loads(moa_tool.mixture_of_agents_tool("q"))
    assert result["success"] is True
    assert "answer A" in result["response"]


# --- requirements check -----------------------------------------------------

def test_check_requirements_needs_a_usable_panel(monkeypatch):
    monkeypatch.setattr(moa_tool, "_moa_config", lambda: PRESET_CONFIG)
    assert moa_tool.check_moa_requirements() is True

    monkeypatch.setattr(moa_tool, "_moa_config", lambda: {
        "presets": {
            "default": {
                "reference_models": [
                    {"provider": "ollama", "model": "qwen3:8b", "enabled": False}
                ],
                "aggregator": {"provider": "ollama", "model": "qwen3:32b"},
            }
        }
    })
    assert moa_tool.check_moa_requirements() is False
