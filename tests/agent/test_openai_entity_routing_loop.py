"""Tests for the per-turn dual-entity routing applied in the conversation loop."""

from __future__ import annotations

from types import SimpleNamespace

from agent.conversation_loop import (
    _infer_previous_openai_entity,
    _maybe_route_openai_entity,
)


def _agent(**kwargs):
    base = dict(
        _openai_dual_entity=True,
        _openai_chat_model="gpt-5.5",
        _openai_codex_model="gpt-5.3-codex",
        _openai_active_entity=None,
        model="gpt-5.5",
        _config_context_length=123,
    )
    base.update(kwargs)
    a = SimpleNamespace(**base)
    a._emit_status = lambda *args, **kw: None
    return a


def test_routing_inert_when_disabled():
    a = _agent(_openai_dual_entity=False, model="gpt-5.4")
    _maybe_route_openai_entity(a, [], "fix the bug in app.py")
    assert a.model == "gpt-5.4"  # unchanged


def test_routing_switches_to_codex_on_coding_turn():
    a = _agent()
    _maybe_route_openai_entity(a, [], "refactor the parser in run_agent.py")
    assert a.model == "gpt-5.3-codex"
    assert a._openai_active_entity == "code"
    assert a._config_context_length is None  # forced re-resolution


def test_routing_stays_gpt_on_chat_turn():
    a = _agent()
    _maybe_route_openai_entity(a, [], "hey, how are you?")
    assert a.model == "gpt-5.5"
    assert a._openai_active_entity == "chat"


def test_routing_sticky_codex_for_ambiguous_followup():
    a = _agent(_openai_active_entity="code", model="gpt-5.3-codex")
    _maybe_route_openai_entity(a, [], "now make it faster")
    assert a.model == "gpt-5.3-codex"
    assert a._openai_active_entity == "code"


def test_infer_previous_entity_from_history_tool_calls():
    history = [
        {"role": "user", "content": "build it"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "edit_file"}, "id": "1"},
            ],
        },
    ]
    a = _agent(_openai_active_entity=None)
    assert _infer_previous_openai_entity(a, history) == "code"


def test_infer_previous_entity_prefers_live_flag():
    a = _agent(_openai_active_entity="chat")
    # Even with coding tool calls in history, the live flag wins.
    history = [
        {"role": "assistant", "tool_calls": [{"function": {"name": "bash"}}]},
    ]
    assert _infer_previous_openai_entity(a, history) == "chat"
