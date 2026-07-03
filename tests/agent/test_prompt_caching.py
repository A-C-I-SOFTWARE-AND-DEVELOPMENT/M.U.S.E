"""Tests for agent/prompt_caching.py — Anthropic cache control injection."""

import copy
import pytest

from agent.prompt_caching import (
    _apply_cache_marker,
    apply_anthropic_cache_control,
)


MARKER = {"type": "ephemeral"}


class TestApplyCacheMarker:
    def test_tool_message_gets_top_level_marker_on_native_anthropic(self):
        """Native Anthropic path: cache_control injected top-level (adapter moves it inside tool_result)."""
        msg = {"role": "tool", "content": "result"}
        _apply_cache_marker(msg, MARKER, native_anthropic=True)
        assert msg["cache_control"] == MARKER

    def test_tool_message_skips_marker_on_openrouter(self):
        """OpenRouter path: top-level cache_control on role:tool is invalid and causes silent hang."""
        msg = {"role": "tool", "content": "result"}
        _apply_cache_marker(msg, MARKER, native_anthropic=False)
        assert "cache_control" not in msg

    def test_none_content_gets_top_level_marker(self):
        msg = {"role": "assistant", "content": None}
        _apply_cache_marker(msg, MARKER)
        assert msg["cache_control"] == MARKER

    def test_empty_string_content_gets_top_level_marker(self):
        """Empty text blocks cannot have cache_control (Anthropic rejects them)."""
        msg = {"role": "assistant", "content": ""}
        _apply_cache_marker(msg, MARKER)
        assert msg["cache_control"] == MARKER
        # Must NOT wrap into [{"type": "text", "text": "", "cache_control": ...}]
        assert msg["content"] == ""

    def test_string_content_wrapped_in_list(self):
        msg = {"role": "user", "content": "Hello"}
        _apply_cache_marker(msg, MARKER)
        assert isinstance(msg["content"], list)
        assert len(msg["content"]) == 1
        assert msg["content"][0]["type"] == "text"
        assert msg["content"][0]["text"] == "Hello"
        assert msg["content"][0]["cache_control"] == MARKER

    def test_list_content_last_item_gets_marker(self):
        msg = {
            "role": "user",
            "content": [
                {"type": "text", "text": "First"},
                {"type": "text", "text": "Second"},
            ],
        }
        _apply_cache_marker(msg, MARKER)
        assert "cache_control" not in msg["content"][0]
        assert msg["content"][1]["cache_control"] == MARKER

    def test_empty_list_content_no_crash(self):
        msg = {"role": "user", "content": []}
        # Should not crash on empty list
        _apply_cache_marker(msg, MARKER)


class TestApplyAnthropicCacheControl:
    def test_empty_messages(self):
        result = apply_anthropic_cache_control([])
        assert result == []

    def test_returns_deep_copy(self):
        msgs = [{"role": "user", "content": "Hello"}]
        result = apply_anthropic_cache_control(msgs)
        assert result is not msgs
        assert result[0] is not msgs[0]
        # Original should be unmodified
        assert "cache_control" not in msgs[0].get("content", "")

    def test_system_message_gets_marker(self):
        msgs = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hi"},
        ]
        result = apply_anthropic_cache_control(msgs)
        # System message should have cache_control
        sys_content = result[0]["content"]
        assert isinstance(sys_content, list)
        assert sys_content[0]["cache_control"]["type"] == "ephemeral"

    def test_last_3_non_system_get_markers(self):
        msgs = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "msg2"},
            {"role": "user", "content": "msg3"},
            {"role": "assistant", "content": "msg4"},
        ]
        result = apply_anthropic_cache_control(msgs)
        # System (index 0) + last 3 non-system (indices 2, 3, 4) = 4 breakpoints
        # Index 1 (msg1) should NOT have marker
        content_1 = result[1]["content"]
        if isinstance(content_1, str):
            assert True  # No marker applied (still a string)
        else:
            assert "cache_control" not in content_1[0]

    def test_no_system_message(self):
        msgs = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = apply_anthropic_cache_control(msgs)
        # Both should get markers (4 slots available, only 2 messages)
        assert len(result) == 2

    def test_1h_ttl(self):
        msgs = [{"role": "system", "content": "System prompt"}]
        result = apply_anthropic_cache_control(msgs, cache_ttl="1h")
        sys_content = result[0]["content"]
        assert isinstance(sys_content, list)
        assert sys_content[0]["cache_control"]["ttl"] == "1h"

    def test_max_4_breakpoints(self):
        msgs = [
            {"role": "system", "content": "System"},
        ] + [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
            for i in range(10)
        ]
        result = apply_anthropic_cache_control(msgs)
        # Count how many messages have cache_control
        count = 0
        for msg in result:
            content = msg.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and "cache_control" in item:
                        count += 1
            elif "cache_control" in msg:
                count += 1
        assert count <= 4


def _full_deepcopy_reference(api_messages, cache_ttl="5m", native_anthropic=False):
    """Oracle: the previous full-deepcopy implementation, to prove the
    selective-copy version produces a byte-identical wire payload."""
    from agent.prompt_caching import _apply_cache_marker, _build_marker

    messages = copy.deepcopy(api_messages)
    if not messages:
        return messages
    marker = _build_marker(cache_ttl)
    used = 0
    if messages[0].get("role") == "system":
        _apply_cache_marker(messages[0], marker, native_anthropic=native_anthropic)
        used += 1
    non_sys = [i for i in range(len(messages)) if messages[i].get("role") != "system"]
    for idx in non_sys[-(4 - used):]:
        _apply_cache_marker(messages[idx], marker, native_anthropic=native_anthropic)
    return messages


class TestSelectiveCopyNoMutation:
    """The selective-deepcopy optimization must never mutate the caller's input
    and must produce a payload identical to the old full-deepcopy version."""

    def _history(self):
        return [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": [{"type": "text", "text": "two"}]},
            {"role": "user", "content": "three"},
            {"role": "assistant", "content": [{"type": "text", "text": "four"}]},
            {"role": "user", "content": "five"},
        ]

    def test_input_list_and_nested_content_never_mutated(self):
        msgs = self._history()
        snapshot = copy.deepcopy(msgs)
        apply_anthropic_cache_control(msgs, native_anthropic=True)
        # No cache_control leaked anywhere into the caller's messages, and
        # string content was not rewrapped into a list.
        assert msgs == snapshot

    def test_payload_matches_full_deepcopy_reference(self):
        for native in (True, False):
            msgs = self._history()
            got = apply_anthropic_cache_control(msgs, native_anthropic=native)
            want = _full_deepcopy_reference(msgs, native_anthropic=native)
            assert got == want, f"native={native}"

    def test_unmarked_messages_shared_marked_are_copied(self):
        msgs = self._history()  # system + 5 non-system → mark system + last 3
        result = apply_anthropic_cache_control(msgs, native_anthropic=True)
        # Marked: index 0 (system) and last 3 (indices 3,4,5) → deep-copied.
        assert result[0] is not msgs[0]
        assert result[3] is not msgs[3]
        assert result[4] is not msgs[4]
        assert result[5] is not msgs[5]
        # Unmarked (indices 1, 2) are shared by reference — the optimization.
        assert result[1] is msgs[1]
        assert result[2] is msgs[2]
