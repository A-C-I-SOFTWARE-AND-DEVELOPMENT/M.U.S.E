"""MEM-1 live-loop wiring tests for AIAgent.

Covers the capture call site added to ``run_agent.py``: completed turns append
provenance-bearing raw memory events when ``memory.layers.enabled`` is set, and
nothing is recorded when the flag is off (the default). The raw event log is
redirected to a tmp ``HERMES_HOME`` so these tests touch no real home dir.
"""

from unittest.mock import MagicMock, patch

import pytest

from run_agent import AIAgent


def _make_tool_defs(*names: str) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"{n} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in names
    ]


@pytest.fixture()
def agent():
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        a = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        a.client = MagicMock()
        a.session_id = "sess-mem1"
        return a


# -- text coercion (pure) ---------------------------------------------------


def test_coerce_memory_text_handles_string(agent):
    assert agent._coerce_memory_text("  hello  ") == "hello"


def test_coerce_memory_text_handles_content_blocks(agent):
    blocks = [{"type": "text", "text": "part one"}, {"type": "text", "text": "part two"}]
    assert agent._coerce_memory_text(blocks) == "part one\npart two"


def test_coerce_memory_text_empty_returns_blank(agent):
    assert agent._coerce_memory_text(None) == ""
    assert agent._coerce_memory_text([]) == ""
    assert agent._coerce_memory_text("   ") == ""


# -- flag gating ------------------------------------------------------------


def test_disabled_by_default_records_nothing(agent, tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # No config flag set ⇒ default off.
    with patch("muse_cli.config.load_config", return_value={}):
        agent._record_memory_layer_events(
            original_user_message="remember this", final_response="ok"
        )
    assert not (tmp_path / "memory-raw").exists()


def test_enabled_records_owner_and_assistant_events(agent, tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from agent.memory_layers import read_all

    with patch(
        "muse_cli.config.load_config",
        return_value={"memory": {"layers": {"enabled": True}}},
    ):
        agent._record_memory_layer_events(
            original_user_message="user said hi", final_response="assistant replied"
        )

    events = read_all("sess-mem1")
    assert len(events) == 2
    user_ev = next(e for e in events if e.source == "user")
    asst_ev = next(e for e in events if e.source == "assistant")
    # Owner input is owner-trust + owner-approved; the model reply is trusted,
    # never owner — so injected/model content can never auto-promote.
    assert user_ev.trust_level == "owner"
    assert user_ev.user_approval_state == "approved"
    assert asst_ev.trust_level == "trusted"
    assert asst_ev.user_approval_state == "unreviewed"


def test_flag_is_cached_after_first_read(agent, monkeypatch):
    calls = {"n": 0}

    def _fake_load():
        calls["n"] += 1
        return {"memory": {"layers": {"enabled": True}}}

    with patch("muse_cli.config.load_config", side_effect=_fake_load):
        assert agent._memory_layers_enabled() is True
        assert agent._memory_layers_enabled() is True
    assert calls["n"] == 1  # read once, then cached


def test_interrupted_turns_skip_capture(agent, tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    with patch(
        "muse_cli.config.load_config",
        return_value={"memory": {"layers": {"enabled": True}}},
    ):
        agent._sync_external_memory_for_turn(
            original_user_message="hi", final_response="partial", interrupted=True
        )
    assert not (tmp_path / "memory-raw").exists()
