"""Tests for the ToolBroker pre-dispatch choke point (P1-3).

Tools like ``delegate_task`` / ``memory`` / ``todo`` / ``session_search`` are
dispatched by special-case branches that BYPASS
``model_tools.handle_function_call`` (and therefore its ``_maybe_broker_block``
call). These tests prove the pre-dispatch choke point evaluates those bypassing
tools through the broker WHEN THE BROKER IS ENABLED — and is a no-op (dispatch
byte-for-byte unchanged) when the broker is OFF (default).

The choke point is ``agent_runtime_helpers.maybe_broker_block_bypassing_tool``,
exercised here via ``invoke_tool`` (the concurrent dispatch path).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from agent.agent_runtime_helpers import (
    invoke_tool,
    maybe_broker_block_bypassing_tool,
)


def _cfg(**tool_broker_section):
    return {"security": {"tool_broker": {"enabled": True, **tool_broker_section}}}


class _FakeAgent:
    """Minimal agent surface used by ``invoke_tool``'s delegate_task path."""

    def __init__(self, session_id="sess-1"):
        self.session_id = session_id
        self._memory_manager = None
        self._memory_store = None
        self._todo_store = None
        self._context_engine_tool_names = None
        self.valid_tool_names = None
        self.clarify_callback = None
        self.delegate_called = False

    def _dispatch_delegate_task(self, function_args):
        self.delegate_called = True
        return json.dumps({"delegated": True})

    # Forwarder mirroring the real AIAgent method.
    def _maybe_broker_block_bypassing_tool(self, name, args, task_id, tool_call_id):
        return maybe_broker_block_bypassing_tool(self, name, args, task_id, tool_call_id)


# ---------------------------------------------------------------------------
# Broker OFF (default): delegate_task dispatches normally; no broker.
# ---------------------------------------------------------------------------

class TestBrokerOffBypassUnchanged:
    def test_delegate_task_dispatches_when_broker_off(self, monkeypatch):
        monkeypatch.delenv("MUSE_TOOL_BROKER", raising=False)
        agent = _FakeAgent()

        with (
            patch(
                "hermes_cli.config.load_config_readonly",
                return_value={"security": {"tool_broker": {"enabled": False}}},
            ),
            patch(
                "hermes_cli.jarvis_prime.tool_broker.ToolBroker.evaluate"
            ) as spy_evaluate,
        ):
            result = invoke_tool(
                agent,
                "delegate_task",
                {"goal": "do a thing"},
                "task-1",
                tool_call_id="c1",
                pre_tool_block_checked=True,
            )

        assert agent.delegate_called is True
        assert json.loads(result)["delegated"] is True
        spy_evaluate.assert_not_called()


# ---------------------------------------------------------------------------
# Broker ON + allowlist NOT permitting delegate_task → BLOCKED, no dispatch.
# ---------------------------------------------------------------------------

class TestBrokerOnBlocksBypassingTool:
    def test_delegate_task_blocked_and_not_dispatched(self, monkeypatch):
        monkeypatch.delenv("MUSE_TOOL_BROKER", raising=False)
        agent = _FakeAgent()

        # Allowlist grants a different tool to this identity → delegate_task
        # denied (fail-closed) by a CONFIGURED policy.
        cfg = _cfg(allowlist={"sess-1": ["read_file"]})
        with patch("hermes_cli.config.load_config_readonly", return_value=cfg):
            result = invoke_tool(
                agent,
                "delegate_task",
                {"goal": "do a thing"},
                "task-1",
                tool_call_id="c1",
                pre_tool_block_checked=True,
            )

        # Structured block-result returned; the special-case dispatch did NOT run.
        assert result.startswith('{"error"')
        parsed = json.loads(result)
        assert parsed["tool_broker"]["verdict"] in {
            "deny",
            "requires_owner_approval",
        }
        assert agent.delegate_called is False

    def test_delegate_task_allowed_dispatches(self, monkeypatch):
        """When the allowlist permits delegate_task, it is NOT a side-effecting
        default here? delegate_task IS side-effecting → owner approval. Confirm
        that an explicit non-side-effecting bypassing tool (todo) on the
        allowlist dispatches through the choke point."""
        monkeypatch.delenv("MUSE_TOOL_BROKER", raising=False)
        agent = _FakeAgent()

        # Route a benign bypassing tool: choke point should ALLOW and return
        # None, so invoke_tool proceeds to the real (todo) dispatch.
        cfg = _cfg(allowlist={"sess-1": ["todo"]})
        with (
            patch("hermes_cli.config.load_config_readonly", return_value=cfg),
            patch("tools.todo_tool.todo_tool", return_value='{"todo":"ok"}'),
        ):
            result = invoke_tool(
                agent,
                "todo",
                {"todos": []},
                "task-1",
                tool_call_id="c1",
                pre_tool_block_checked=True,
            )

        assert json.loads(result)["todo"] == "ok"


# ---------------------------------------------------------------------------
# Choke point only fires for BYPASSING tools (no double-evaluation).
# ---------------------------------------------------------------------------

class TestNoDoubleEvaluation:
    def test_non_bypassing_tool_returns_none(self, monkeypatch):
        """A tool that falls through to handle_function_call (e.g. read_file)
        is NOT evaluated by the choke point — it returns None so the tool is
        evaluated once, inside handle_function_call."""
        monkeypatch.delenv("MUSE_TOOL_BROKER", raising=False)
        agent = SimpleNamespace(
            session_id="sess-1",
            _memory_manager=None,
            _context_engine_tool_names=None,
        )
        cfg = _cfg(allowlist={"sess-1": ["read_file"]})
        with patch("hermes_cli.config.load_config_readonly", return_value=cfg):
            out = maybe_broker_block_bypassing_tool(
                agent, "read_file", {"path": "x"}, "task-1", "c1"
            )
        assert out is None

    def test_bypassing_tool_is_evaluated(self, monkeypatch):
        """A bypassing tool (delegate_task) IS evaluated by the choke point."""
        monkeypatch.delenv("MUSE_TOOL_BROKER", raising=False)
        agent = SimpleNamespace(
            session_id="sess-1",
            _memory_manager=None,
            _context_engine_tool_names=None,
        )
        cfg = _cfg(allowlist={"sess-1": ["read_file"]})
        with patch("hermes_cli.config.load_config_readonly", return_value=cfg):
            out = maybe_broker_block_bypassing_tool(
                agent, "delegate_task", {"goal": "x"}, "task-1", "c1"
            )
        assert out is not None
        assert out.startswith('{"error"')
