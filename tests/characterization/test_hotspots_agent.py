"""Characterization tests for the §5.3 complexity hotspots — agent side.

Work Packet §5.3 lists the repository's branch-heaviest functions and prescribes
*characterization tests and seam extraction*, "explicitly **not** a broad
rewrite".  This file is the agent half of the characterization step for:

    agent/conversation_loop.py::run_conversation              (3,990 lines / 642 branch nodes)
    agent/agent_init.py::init_agent                           (1,498 / 272)
    agent/chat_completion_helpers.py::interruptible_streaming_api_call (914 / 154)

A characterization test records what the code **does**, not what it ought to
do.  Pins that capture something surprising are labelled ``CHARACTERIZED
ODDITY`` and are deliberately left alone: changing them is a behaviour change
and must be made on purpose, not silently during a refactor.  Nothing in this
file refactors production code.

``run_conversation`` is the largest function in the repository at 642 branch
nodes and this file does **not** pretend to cover it.  What is pinned is the
turn envelope: the loop's entry guard, its two terminal shapes (text answer and
budget exhaustion), the one-round tool cycle, and the wire-order contract for
system prompt / history / new message.  Everything else is enumerated in
``COVERAGE_NOTES`` at the bottom of this file.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Agent construction helper
#
# ``AIAgent.__init__`` is a thin forwarder to ``agent.agent_init.init_agent``
# (run_agent.py:513), so constructing an AIAgent *is* how init_agent is
# exercised.  The three patches below remove the only parts of construction
# that touch the outside world: real toolset discovery and the OpenAI client
# constructor.  Everything the tests assert on is computed by init_agent
# itself.
# ---------------------------------------------------------------------------

def _tool_defs(*names: str) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": "t",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for name in names
    ]


def _make_agent(*, tools: tuple[str, ...] = ("web_search",), **kwargs):
    from run_agent import AIAgent

    kwargs.setdefault("quiet_mode", True)
    kwargs.setdefault("skip_context_files", True)
    kwargs.setdefault("skip_memory", True)
    with (
        patch("run_agent.get_tool_definitions", return_value=_tool_defs(*tools)),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        return AIAgent(**kwargs)


# ===========================================================================
# agent/agent_init.py :: init_agent  (1,498 lines / 272 branch nodes)
#
# The cleanest seam in the function is the api_mode/provider resolution: one
# ordered if/elif chain at agent_init.py:637-675 that turns
# (api_mode, provider, base_url) into (agent.api_mode, agent.provider).
# Everything downstream — which transport is loaded, which adapter formats the
# request, whether prompt caching applies — hangs off that decision, so it is
# pinned exhaustively.
# ===========================================================================

class TestInitAgentApiModeInference:
    """URL sniffing, used when the caller names neither api_mode nor provider."""

    @pytest.mark.parametrize(
        "base_url, expected_mode, expected_provider",
        [
            # Anthropic's own endpoint: mode AND provider are both inferred.
            ("https://api.anthropic.com", "anthropic_messages", "anthropic"),
            # ChatGPT's Codex backend: mode AND provider are both inferred.
            ("https://chatgpt.com/backend-api/codex", "codex_responses",
             "openai-codex"),
            # xAI: mode AND provider are both inferred.
            ("https://api.x.ai/v1", "codex_responses", "xai"),
            # A third-party Anthropic-compatible proxy is recognised by the
            # "/anthropic" URL suffix — but nothing is inferred about WHO it
            # is, so provider stays empty.
            ("https://mm.example/anthropic", "anthropic_messages", ""),
            # ...including with a trailing slash.
            ("https://mm.example/anthropic/", "anthropic_messages", ""),
            # Bedrock is recognised by hostname; provider is likewise not set.
            ("https://bedrock-runtime.us-east-1.amazonaws.com",
             "bedrock_converse", ""),
            # Anything else is OpenAI-wire chat completions.
            ("https://x.example/v1", "chat_completions", ""),
        ],
    )
    def test_base_url_alone_decides_the_wire_protocol(
            self, base_url, expected_mode, expected_provider):
        agent = _make_agent(api_key="k", base_url=base_url, model="m")

        assert agent.api_mode == expected_mode
        assert agent.provider == expected_provider

    def test_a_named_provider_selects_the_mode_without_any_url_hint(self):
        agent = _make_agent(api_key="k", base_url="https://x.example/v1",
                            provider="openai-codex", model="m")

        assert agent.api_mode == "codex_responses"
        assert agent.provider == "openai-codex"


class TestInitAgentApiModePrecedence:
    """Which input wins when two of them disagree."""

    def test_an_explicit_api_mode_beats_the_url_and_leaves_provider_unset(self):
        """The caller's declaration is final (#10473) — and note that because
        the anthropic.com branch is skipped, the side effect of that branch
        (``agent.provider = "anthropic"``) never happens either."""
        agent = _make_agent(api_key="k", base_url="https://api.anthropic.com",
                            api_mode="chat_completions", model="m")

        assert agent.api_mode == "chat_completions"
        assert agent.provider == ""

    @pytest.mark.parametrize(
        "base_url",
        [
            "https://api.anthropic.com",
            "https://chatgpt.com/backend-api/codex",
            "https://api.x.ai/v1",
        ],
    )
    def test_a_named_provider_suppresses_the_hostname_rules(self, base_url):
        """Those three branches are guarded by ``provider_name is None``, so
        naming any provider — even an unrelated one — turns the sniffing off
        and the request falls through to chat completions."""
        agent = _make_agent(api_key="k", base_url=base_url,
                            provider="myproxy", model="m")

        assert agent.api_mode == "chat_completions"
        assert agent.provider == "myproxy"

    @pytest.mark.parametrize(
        "base_url, expected_mode",
        [
            ("https://mm.example/anthropic", "anthropic_messages"),
            ("https://bedrock-runtime.us-east-1.amazonaws.com", "bedrock_converse"),
        ],
    )
    def test_the_suffix_and_bedrock_rules_ignore_a_named_provider(
            self, base_url, expected_mode):
        """CHARACTERIZED ODDITY — the URL rules are not uniformly guarded.

        The anthropic.com / chatgpt.com / api.x.ai branches all test
        ``provider_name is None`` first; the "/anthropic" suffix branch
        (agent_init.py:655) and the bedrock-hostname branch (:660) do not.  So
        naming a provider disables three URL rules and not the other two, and
        the resulting agent carries a mode inferred from the URL alongside a
        provider name the caller chose.

        This matters for a proxy: ``provider="myproxy"`` on a "/anthropic"
        URL still speaks the Anthropic Messages protocol.  That is probably
        the useful outcome; it is simply not the rule the other three
        branches follow.
        """
        agent = _make_agent(api_key="k", base_url=base_url,
                            provider="myproxy", model="m")

        assert agent.api_mode == expected_mode
        assert agent.provider == "myproxy"

    def test_provider_bedrock_selects_converse_without_a_bedrock_url(self):
        agent = _make_agent(api_key="k", base_url="https://x.example/v1",
                            provider="bedrock", model="m")

        assert agent.api_mode == "bedrock_converse"


class TestInitAgentIdentityNormalisation:
    """The scalar assignments the whole agent then reads back."""

    def test_provider_is_stripped_and_lowercased(self):
        agent = _make_agent(api_key="k", base_url="https://x.example/v1",
                            provider="  MyProxy  ", model="m")

        assert agent.provider == "myproxy"

    def test_requested_provider_defaults_to_provider_and_is_normalised(self):
        defaulted = _make_agent(api_key="k", base_url="https://x.example/v1",
                                provider="  MyProxy  ", model="m")
        explicit = _make_agent(api_key="k", base_url="https://x.example/v1",
                               provider="p", requested_provider="  REQ ", model="m")

        assert defaulted.requested_provider == "myproxy"
        assert explicit.provider == "p"
        assert explicit.requested_provider == "req"

    def test_log_prefix_gains_a_trailing_space_only_when_non_empty(self):
        """Callers concatenate ``agent.log_prefix`` directly onto log lines, so
        the separator lives in the stored value rather than at each callsite."""
        default = _make_agent(api_key="k", base_url="https://x.example/v1", model="m")
        prefixed = _make_agent(api_key="k", base_url="https://x.example/v1",
                               model="m", log_prefix="[x]")

        assert default.log_prefix == ""
        assert prefixed.log_prefix == "[x] "

    def test_command_and_args_are_aliases_for_acp_command_and_acp_args(self):
        plain = _make_agent(api_key="k", base_url="https://x.example/v1", model="m")
        aliased = _make_agent(api_key="k", base_url="https://x.example/v1", model="m",
                              command="cmd", args=["a"])

        assert plain.acp_command is None
        assert plain.acp_args == []
        assert aliased.acp_command == "cmd"
        assert aliased.acp_args == ["a"]

    def test_max_iterations_reaches_both_the_attribute_and_the_budget(self):
        """The declared default is pinned by identity to the signature rather
        than by literal, so bumping the default is a one-place change."""
        from agent.agent_init import init_agent
        from agent.iteration_budget import IterationBudget

        declared_default = inspect.signature(init_agent).parameters[
            "max_iterations"].default

        default_agent = _make_agent(api_key="k", base_url="https://x.example/v1",
                                    model="m")
        custom_agent = _make_agent(api_key="k", base_url="https://x.example/v1",
                                   model="m", max_iterations=7)

        assert default_agent.max_iterations == declared_default
        assert isinstance(default_agent.iteration_budget, IterationBudget)
        assert custom_agent.max_iterations == 7
        assert custom_agent.iteration_budget.max_total == 7


# ===========================================================================
# agent/chat_completion_helpers.py :: interruptible_streaming_api_call (914 / 154)
#
# The body is a per-transport streaming implementation (chat_completions,
# anthropic_messages, codex_responses, bedrock_converse) with watchdog threads,
# stale-stream detection and provider-error fallbacks.  None of that is
# reachable without a live provider socket.
#
# Its *prologue* is a clean seam and is pinned in full: three guards, executed
# in a fixed order, that decide whether a streaming call happens at all.  The
# agent is a SimpleNamespace here on purpose — the prologue reads exactly four
# attributes, and saying so is the point of the pin.
# ===========================================================================

class TestShouldUseDirectApiCall:
    """Which contexts run the request inline instead of on the interrupt worker."""

    @pytest.mark.parametrize(
        "platform, api_mode, provider, expected",
        [
            # Interactive CLI keeps the interrupt worker.
            ("cli", "chat_completions", "x", False),
            # Gateway cron turns deadlock on a nested pool (#62151).
            ("cron", "chat_completions", "x", True),
            # Delegated children hit the same fingerprint (#60203).
            ("subagent", "chat_completions", "x", True),
            # Native transports keep their own workers regardless of platform.
            ("cron", "anthropic_messages", "x", False),
            # MoA owns its own client lifecycle.
            ("cron", "chat_completions", "moa", False),
        ],
    )
    def test_the_inline_decision_table(self, platform, api_mode, provider, expected):
        from agent.chat_completion_helpers import should_use_direct_api_call

        agent = SimpleNamespace(platform=platform, api_mode=api_mode,
                                provider=provider)

        assert should_use_direct_api_call(agent) is expected

    def test_the_delegated_child_contextvar_forces_inline_on_any_platform(self,
                                                                          monkeypatch):
        """A caller that bypasses the child runner still gets the inline path,
        because the ContextVar is checked before the platform stamp."""
        import agent.delegation_context as delegation_context
        from agent.chat_completion_helpers import should_use_direct_api_call

        agent = SimpleNamespace(platform="cli", api_mode="chat_completions",
                                provider="x")
        assert should_use_direct_api_call(agent) is False

        monkeypatch.setattr(delegation_context, "is_delegated_child_context",
                            lambda: True)
        assert should_use_direct_api_call(agent) is True


class TestInterruptibleStreamingApiCallPrologue:

    def test_a_pending_interrupt_raises_before_anything_else_is_read(self):
        """The guard is the very first statement, so an agent carrying nothing
        but ``_interrupt_requested`` is enough to trigger it."""
        from agent.chat_completion_helpers import interruptible_streaming_api_call

        agent = SimpleNamespace(_interrupt_requested=True)

        with pytest.raises(InterruptedError) as exc:
            interruptible_streaming_api_call(agent, {})

        assert str(exc.value) == "Agent interrupted before streaming API call"

    def test_an_inline_context_delegates_verbatim_to_the_non_streaming_entry(self):
        """Routing through the *method* (not the module function) is what keeps
        the outer loop's per-request retry/refresh seam intact."""
        from agent.chat_completion_helpers import interruptible_streaming_api_call

        seen: list[dict] = []
        api_kwargs = {"a": 1}
        agent = SimpleNamespace(
            _interrupt_requested=False,
            api_mode="chat_completions",
            provider="x",
            platform="cron",                       # → should_use_direct_api_call
            _interruptible_api_call=lambda kw: seen.append(kw) or "RESULT",
        )

        result = interruptible_streaming_api_call(
            agent, api_kwargs, on_first_delta=lambda: None)

        assert result == "RESULT"
        # Same dict object, unmodified — the prologue is not allowed to rewrite
        # the request on its way through.
        assert seen == [api_kwargs]
        assert seen[0] is api_kwargs
        # CHARACTERIZED ODDITY: on this path ``on_first_delta`` is silently
        # dropped.  The inline call produces no deltas, so there is nothing to
        # fire it with — but the caller is not told.
        assert api_kwargs == {"a": 1}

    def test_codex_hands_the_first_delta_callback_over_the_instance(self):
        """``_run_codex_stream`` reads the callback off the agent rather than
        taking it as an argument, so the prologue parks it there for the
        duration of the call and clears it afterwards."""
        from agent.chat_completion_helpers import interruptible_streaming_api_call

        observed: dict = {}

        def _call(_kw):
            observed["during"] = agent._codex_on_first_delta
            return "CODEX"

        agent = SimpleNamespace(
            _interrupt_requested=False,
            api_mode="codex_responses",
            provider="x",
            platform="cli",                        # not an inline context
            _codex_on_first_delta=None,
            _interruptible_api_call=_call,
        )
        callback = lambda: None  # noqa: E731

        result = interruptible_streaming_api_call(
            agent, {}, on_first_delta=callback)

        assert result == "CODEX"
        assert observed["during"] is callback
        assert agent._codex_on_first_delta is None

    def test_the_codex_callback_is_cleared_even_when_the_call_raises(self):
        """It is parked in a ``try`` with a ``finally``, so a failed turn cannot
        leave a stale callback attached to the agent for the next one."""
        from agent.chat_completion_helpers import interruptible_streaming_api_call

        def _boom(_kw):
            raise RuntimeError("provider exploded")

        agent = SimpleNamespace(
            _interrupt_requested=False,
            api_mode="codex_responses",
            provider="x",
            platform="cli",
            _codex_on_first_delta=None,
            _interruptible_api_call=_boom,
        )

        with pytest.raises(RuntimeError, match="provider exploded"):
            interruptible_streaming_api_call(agent, {}, on_first_delta=lambda: None)

        assert agent._codex_on_first_delta is None

    def test_the_interrupt_guard_outranks_the_inline_context(self):
        """Ordering matters: a cron turn with a pending interrupt must raise
        rather than quietly running the request inline."""
        from agent.chat_completion_helpers import interruptible_streaming_api_call

        agent = SimpleNamespace(
            _interrupt_requested=True,
            api_mode="chat_completions",
            provider="x",
            platform="cron",
            _interruptible_api_call=lambda _kw: pytest.fail(
                "the request was dispatched despite a pending interrupt"),
        )

        with pytest.raises(InterruptedError):
            interruptible_streaming_api_call(agent, {})


# ===========================================================================
# agent/conversation_loop.py :: run_conversation  (3,990 lines / 642 branch nodes)
#
# The largest function in the repository.  ``AIAgent.run_conversation``
# (run_agent.py:7894) is a forwarder to it, so driving the method is how the
# function is reached.
#
# These pins describe the TURN ENVELOPE only: what a turn is handed, what it
# returns, and how it stops.  They are not a claim of coverage — see
# COVERAGE_NOTES.
# ===========================================================================

def _chat_response(*, content, finish_reason, tool_calls=None):
    """A minimal duck-type of an OpenAI ChatCompletion response object."""
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model="test/model", usage=None)


def _tool_call(name: str, call_id: str, arguments: str = "{}"):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _loop_agent(*tools: str):
    """An agent wired for the loop with every out-of-process seam disabled."""
    agent = _make_agent(tools=tools or ("web_search",), api_key="test-key",
                        base_url="https://x.example/v1")
    agent._cached_system_prompt = "You are helpful."
    agent._use_prompt_caching = False
    agent.compression_enabled = False
    agent.save_trajectories = False
    agent.valid_tool_names = set(tools or ("web_search",))
    agent.client = MagicMock()
    return agent


def _run_turn(agent, *args, tool_result="TOOLRESULT", tool_spy=None, **kwargs):
    """Drive one turn with persistence and tool execution stubbed out."""
    if tool_spy is None:
        handler = patch("run_agent.handle_function_call", return_value=tool_result)
    else:
        handler = patch("run_agent.handle_function_call", side_effect=tool_spy)
    with (
        handler,
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        return agent.run_conversation(*args, **kwargs)


#: Every key ``run_conversation`` promises its callers.  The gateway, the CLI,
#: the orchestrator and the delegation runner all read this dict, so the key
#: set is a cross-surface contract rather than an implementation detail.
EXPECTED_RESULT_KEYS = {
    "api_calls", "base_url", "cache_read_tokens", "cache_write_tokens",
    "completed", "completion_tokens", "cost_source", "cost_status",
    "estimated_cost_usd", "failed", "final_response", "input_tokens",
    "interrupted", "last_prompt_tokens", "last_reasoning", "messages", "model",
    "output_tokens", "partial", "pre_transform_response", "prompt_tokens",
    "provider", "reasoning_tokens", "response_previewed",
    "response_transformed", "service_tier", "session_id", "total_tokens",
    "turn_exit_reason",
}


class TestRunConversationTextTurn:

    def test_a_plain_answer_is_one_api_call_and_two_messages(self):
        agent = _loop_agent("web_search")
        agent.client.chat.completions.create.side_effect = [
            _chat_response(content="Hello there.", finish_reason="stop"),
        ]

        result = _run_turn(agent, "hi")

        assert result["api_calls"] == 1
        assert result["final_response"] == "Hello there."
        assert result["completed"] is True
        assert result["failed"] is False
        assert result["interrupted"] is False
        # The exit reason carries the provider's finish_reason inline — it is
        # a human-readable label, not an enum, and the ledger records it.
        assert result["turn_exit_reason"] == "text_response(finish_reason=stop)"
        assert [m["role"] for m in result["messages"]] == ["user", "assistant"]
        assert result["messages"][1]["content"] == "Hello there."
        assert result["messages"][1]["finish_reason"] == "stop"

    def test_the_result_envelope_carries_the_full_documented_key_set(self):
        agent = _loop_agent("web_search")
        agent.client.chat.completions.create.side_effect = [
            _chat_response(content="ok", finish_reason="stop"),
        ]

        result = _run_turn(agent, "hi")

        assert set(result) == EXPECTED_RESULT_KEYS

    def test_the_system_prompt_is_sent_but_never_returned_in_messages(self):
        """CHARACTERIZED ODDITY — ``messages`` is not the wire payload.

        The returned list is the *persistable* conversation: the system prompt
        is stripped out, while the wire request carries it in position 0.  A
        caller that feeds ``result["messages"]`` straight back in as
        ``conversation_history`` therefore does not double the system prompt —
        which is exactly why it is stripped.
        """
        agent = _loop_agent("web_search")
        agent.client.chat.completions.create.side_effect = [
            _chat_response(content="ok", finish_reason="stop"),
        ]

        result = _run_turn(agent, "hi", system_message="SYSTEM-X")

        sent = agent.client.chat.completions.create.call_args.kwargs["messages"]
        assert sent[0]["role"] == "system"
        assert all(m["role"] != "system" for m in result["messages"])


class TestRunConversationWireOrder:

    def test_history_is_replayed_between_the_system_prompt_and_the_new_message(self):
        agent = _loop_agent("web_search")
        agent.client.chat.completions.create.side_effect = [
            _chat_response(content="ok", finish_reason="stop"),
        ]

        result = _run_turn(
            agent,
            "second",
            system_message="SYSTEM-X",
            conversation_history=[
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "reply"},
            ],
        )

        sent = agent.client.chat.completions.create.call_args.kwargs["messages"]
        assert [(m["role"], m["content"]) for m in sent] == [
            ("system", "You are helpful."),   # the cached prompt, not SYSTEM-X
            ("user", "first"),
            ("assistant", "reply"),
            ("user", "second"),
        ]
        # The returned transcript keeps the replayed history and appends the
        # new exchange, so it can be persisted as the whole conversation.
        assert [(m["role"], m["content"]) for m in result["messages"]] == [
            ("user", "first"),
            ("assistant", "reply"),
            ("user", "second"),
            ("assistant", "ok"),
        ]

    def test_the_cached_system_prompt_wins_over_the_per_call_system_message(self):
        """CHARACTERIZED ODDITY — ``system_message=`` did not reach the wire.

        With ``_cached_system_prompt`` populated (the normal state for a warm
        agent), the cached value is what is sent; the caller's
        ``system_message`` argument does not replace it.  Pinned because it is
        the sort of thing a refactor "cleans up" by accident, and doing so
        would change what every warm gateway turn sends.
        """
        agent = _loop_agent("web_search")
        agent._cached_system_prompt = "CACHED PROMPT"
        agent.client.chat.completions.create.side_effect = [
            _chat_response(content="ok", finish_reason="stop"),
        ]

        _run_turn(agent, "hi", system_message="PER-CALL PROMPT")

        sent = agent.client.chat.completions.create.call_args.kwargs["messages"]
        assert sent[0]["content"] == "CACHED PROMPT"


class TestRunConversationToolCycle:

    def test_one_tool_round_produces_four_messages_and_two_api_calls(self):
        agent = _loop_agent("web_search")
        agent.client.chat.completions.create.side_effect = [
            _chat_response(content="", finish_reason="tool_calls",
                           tool_calls=[_tool_call("web_search", "c1",
                                                  '{"q": "x"}')]),
            _chat_response(content="Done.", finish_reason="stop"),
        ]
        executed: list[tuple] = []

        def _spy(name, args, *_a, **_k):
            executed.append((name, args))
            return "TOOLRESULT"

        result = _run_turn(agent, "go", tool_spy=_spy)

        # The tool name and its JSON arguments are decoded before dispatch.
        assert executed == [("web_search", {"q": "x"})]
        assert result["api_calls"] == 2
        assert result["final_response"] == "Done."
        assert result["turn_exit_reason"] == "text_response(finish_reason=stop)"
        assert [m["role"] for m in result["messages"]] == [
            "user", "assistant", "tool", "assistant"]

    def test_the_tool_result_message_is_correlated_back_to_its_call(self):
        agent = _loop_agent("web_search")
        agent.client.chat.completions.create.side_effect = [
            _chat_response(content="", finish_reason="tool_calls",
                           tool_calls=[_tool_call("web_search", "c1")]),
            _chat_response(content="Done.", finish_reason="stop"),
        ]

        result = _run_turn(agent, "go")

        assistant_msg, tool_msg = result["messages"][1], result["messages"][2]
        assert assistant_msg["finish_reason"] == "tool_calls"
        assert assistant_msg["tool_calls"][0]["id"] == "c1"
        assert tool_msg["tool_call_id"] == "c1"
        assert tool_msg["name"] == "web_search"
        assert tool_msg["content"] == "TOOLRESULT"
        # Tool output is risk-scored on the way in, and the verdict rides on
        # the message rather than being computed again downstream.
        assert tool_msg["_tool_output_risk"]["risk"] == "low"
        assert tool_msg["_tool_output_risk"]["redacted"] is False


class TestRunConversationTermination:

    def test_a_pending_interrupt_ends_the_turn_before_the_first_api_call(self):
        agent = _loop_agent("web_search")
        agent._interrupt_requested = True
        agent.client.chat.completions.create.side_effect = [
            _chat_response(content="never", finish_reason="stop"),
        ]

        result = _run_turn(agent, "hi")

        assert agent.client.chat.completions.create.call_count == 0
        assert result["api_calls"] == 0
        assert result["interrupted"] is True
        assert result["completed"] is False
        assert result["failed"] is False
        assert result["final_response"] is None
        assert result["turn_exit_reason"] == "interrupted_by_user"
        # An interrupted turn still returns the full envelope — callers do not
        # need a separate shape for the aborted case.
        assert set(result) == EXPECTED_RESULT_KEYS

    def test_budget_exhaustion_stops_the_loop_and_reports_the_limit(self):
        """A model that only ever emits tool calls must not loop forever.

        The budget stops it, and the caller gets a stand-in answer rather than
        ``None``, so a gateway turn never renders an empty reply.
        """
        from agent.iteration_budget import IterationBudget

        agent = _loop_agent("web_search")
        agent.max_iterations = 2
        agent.iteration_budget = IterationBudget(2)
        agent.client.chat.completions.create.side_effect = [
            _chat_response(content="", finish_reason="tool_calls",
                           tool_calls=[_tool_call("web_search", f"c{i}")])
            for i in range(10)
        ]

        result = _run_turn(agent, "loop")

        assert result["api_calls"] == 2
        assert result["turn_exit_reason"] == "max_iterations_reached(2/2)"
        assert result["final_response"] == (
            "I reached the iteration limit and couldn't generate a summary.")
        assert set(result) == EXPECTED_RESULT_KEYS
        # Unused scripted responses remain: the loop stopped on its budget, it
        # did not merely run out of replies.
        assert agent.client.chat.completions.create.call_count < 10

    def test_the_post_budget_summary_requests_are_not_counted_in_api_calls(self):
        """CHARACTERIZED ODDITY — ``api_calls`` under-reports provider traffic.

        On exhaustion the loop asks the model to summarise so the user gets a
        real answer instead of a truncation notice.  Two such requests go out
        (one from the budget guard, one from the max-iterations guard) and
        neither increments ``api_calls``: the reported 2 is the budget, while
        4 requests actually reached the client.

        Anything costing or rate-limiting off ``api_calls`` is therefore short
        by the summary attempts.  Pinned rather than fixed — raising the count
        would change every recorded turn's ledger entry.
        """
        from agent.iteration_budget import IterationBudget

        agent = _loop_agent("web_search")
        agent.max_iterations = 2
        agent.iteration_budget = IterationBudget(2)
        agent.client.chat.completions.create.side_effect = [
            _chat_response(content="", finish_reason="tool_calls",
                           tool_calls=[_tool_call("web_search", f"c{i}")])
            for i in range(10)
        ]

        result = _run_turn(agent, "loop")

        assert result["api_calls"] == 2
        assert agent.client.chat.completions.create.call_count == 4


# ---------------------------------------------------------------------------
# COVERAGE_NOTES — what these tests deliberately do NOT reach.
#
# Stated explicitly because §29.2 forbids presenting partial work as complete.
#
#   agent/conversation_loop.py::run_conversation (642 branch nodes)
#       This is the largest function in the repository and the pins above are
#       a turn envelope, NOT coverage of it.  Covered: the pre-flight
#       interrupt guard, the single text-response exit, the one-round tool
#       cycle including argument decoding and tool_call_id correlation, the
#       system/history/user wire order, the returned-transcript shape, the
#       iteration-budget exit, and the 29-key result envelope on three
#       different exits.
#
#       NOT covered, and each is a substantial piece of work in its own right:
#         * every transport other than chat_completions — the
#           anthropic_messages, codex_responses and bedrock_converse turn
#           shapes each have their own request build and response normalise;
#         * streaming turns (stream_callback / on_first_delta / delta
#           accumulation) and the stale-stream watchdog;
#         * context compression and the summarisation fork
#           (``compression_enabled`` is forced False above);
#         * all error/retry ladders — provider errors, rate limits, credential
#           refresh, fallback-provider rotation, and the tool-loop guardrails;
#         * multi-round tool cycles, parallel tool calls, tool approval
#           prompts, and the execute_code refund path;
#         * MoA (``moa_config``), delegation/subagent turns, and the
#           background review fork;
#         * session persistence, trajectory saving and task-resource cleanup
#           (all three are patched out here — they are I/O, not turn logic);
#         * cost/token accounting beyond the presence of its keys.  The pins
#           above assert the key set, never the values, because the fake
#           response carries ``usage=None``.
#
#   agent/agent_init.py::init_agent (272 branch nodes)
#       Covered: the api_mode/provider resolution chain in full, including its
#       precedence rules, plus the identity/normalisation assignments the rest
#       of the agent reads back.  NOT covered: the ~1,300 remaining lines —
#       toolset assembly and the requirements check, client construction and
#       credential-pool matching, memory/context-file loading, compression and
#       auxiliary-model configuration, the GPT-5.x Responses auto-upgrade
#       (agent_init.py:725-742, which needs live model metadata), and the
#       skill/plugin wiring.  Two of those are stubbed by the construction
#       helper on purpose: real toolset discovery and the OpenAI constructor.
#
#   agent/chat_completion_helpers.py::interruptible_streaming_api_call (154 nodes)
#       Covered: the whole prologue — the interrupt guard, the inline-context
#       delegation and its verbatim argument forwarding, and the codex
#       callback park/restore including the failure path.  NOT covered: any
#       actual streaming.  The chat_completions, anthropic_messages and
#       bedrock_converse bodies each spawn a worker thread around a live
#       provider stream with watchdog polling, stale-stream detection, a
#       cross-turn give-up circuit breaker and a non-streaming fallback;
#       reaching them needs a fake streaming transport, which is a fixture
#       this task did not build.  Recorded as not done rather than skipped.
# ---------------------------------------------------------------------------
