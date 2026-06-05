"""Tests for ``agent.conversation_loop.build_usage_record``.

This is the producer side of the per-job cost seam: it turns a finished run's
session totals (a ``run_conversation`` result dict, or an ``AIAgent``-like
object) into the ``{usage, cost_usd, model, provider}`` block the orchestrator
consumes. The cross-module round-trip (block -> consumer seam -> ``JobCost``)
is covered in ``tests/test_parallel_orchestration.py``; here we pin the shaping
rules of the helper itself.
"""

from __future__ import annotations

from agent.conversation_loop import build_usage_record


def _result(**overrides) -> dict:
    base = {
        "model": "claude-opus-4-8",
        "provider": "anthropic",
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "estimated_cost_usd": 0.0,
    }
    base.update(overrides)
    return base


def test_build_from_result_dict_shapes_full_block():
    rec = build_usage_record(
        _result(
            input_tokens=1000,
            output_tokens=200,
            cache_read_tokens=500,
            reasoning_tokens=30,
            estimated_cost_usd=0.0456,
        )
    )
    assert rec == {
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_read_tokens": 500,
            "reasoning_tokens": 30,
        },
        "cost_usd": 0.0456,
        "model": "claude-opus-4-8",
        "provider": "anthropic",
    }


def test_noop_turn_returns_none():
    # Zero tokens and zero cost must not move any meter.
    assert build_usage_record(_result()) is None


def test_require_tokens_false_forces_cost_only_block():
    rec = build_usage_record(_result(estimated_cost_usd=0.0), require_tokens=False)
    assert rec is not None
    assert "usage" not in rec
    assert rec["cost_usd"] == 0.0
    assert rec["model"] == "claude-opus-4-8"


def test_cost_only_entry_emits_without_tokens():
    rec = build_usage_record(_result(estimated_cost_usd=0.25))
    assert rec is not None
    assert "usage" not in rec
    assert rec["cost_usd"] == 0.25


def test_bool_cost_is_rejected_not_coerced():
    # bool is an int subclass; True must not become $1.
    rec = build_usage_record(_result(input_tokens=5, estimated_cost_usd=True))
    assert rec == {"usage": {"input_tokens": 5}, "cost_usd": 0.0, "model": "claude-opus-4-8", "provider": "anthropic"}


def test_negative_cost_is_dropped():
    rec = build_usage_record(_result(input_tokens=5, estimated_cost_usd=-3.0))
    assert rec is not None
    assert rec["cost_usd"] == 0.0


def test_non_positive_token_buckets_are_omitted():
    rec = build_usage_record(_result(input_tokens=10, output_tokens=0, estimated_cost_usd=0.01))
    assert rec is not None
    assert rec["usage"] == {"input_tokens": 10}


def test_blank_model_and_provider_are_omitted():
    rec = build_usage_record(
        _result(input_tokens=5, estimated_cost_usd=0.01, model="   ", provider="")
    )
    assert rec is not None
    assert "model" not in rec
    assert "provider" not in rec


def test_build_from_agent_like_object():
    class FakeAgent:
        session_input_tokens = 10
        session_output_tokens = 5
        session_cache_read_tokens = 0
        session_cache_write_tokens = 0
        session_reasoning_tokens = 0
        session_estimated_cost_usd = 0.001
        model = "gpt-x"
        provider = "openai"

    rec = build_usage_record(FakeAgent())
    assert rec == {
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "cost_usd": 0.001,
        "model": "gpt-x",
        "provider": "openai",
    }


def test_malformed_token_values_degrade_to_zero():
    rec = build_usage_record(
        _result(input_tokens="not a number", output_tokens=7, estimated_cost_usd=0.01)
    )
    assert rec is not None
    # The junk bucket is dropped; the good one survives.
    assert rec["usage"] == {"output_tokens": 7}
