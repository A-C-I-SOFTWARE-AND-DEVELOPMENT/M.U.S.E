"""Full-capability muse chat responder for the cockpit chat endpoint.

Where :mod:`gateway.cockpit.agent` drives the *JarvisPrime* turn (mode
classification, routing, memory, owner gates) and produces prose,
this module drives the **complete agent loop** — the same
:class:`run_agent.AIAgent` the TUI and the messaging gateway run, with
the same tool surface (terminal, files, code execution, browser, web,
``delegate_task`` sub-agents, cron) — and streams every step as the
cockpit chunk vocabulary from :mod:`gateway.jarvis_local_http`:

``thinking`` / ``phase`` / ``tool_call`` / ``body_delta`` / ``body`` /
``approval`` / ``done`` / ``error``

Reuse map (this module is an adapter, not a re-implementation):

* Agent construction mirrors ``APIServerAdapter._create_agent``
  (``gateway/platforms/api_server.py``): runtime kwargs, model, fallback
  chain and reasoning config come from :mod:`gateway.run`; toolsets come
  from ``platform_toolsets.cockpit`` in config.yaml, defaulting to the
  ``hermes-cockpit`` toolset.
* Owner approvals reuse :mod:`tools.approval`'s gateway bridge
  (``register_gateway_notify`` / ``resolve_gateway_approval``) exactly like
  the API server's ``/v1/runs`` lane — a blocked tool surfaces as an
  ``approval`` chunk and the stream stays open until the client resolves
  it (or the run is interrupted).
* Tool lifecycle uses ``AIAgent``'s ``tool_start_callback`` /
  ``tool_complete_callback`` with ``agent.display.build_tool_preview``
  labels; model streaming uses ``stream_delta_callback``.

The responder is synchronous-iterator shaped (``(prompt, history) ->
Iterator[dict]``) so the stdlib cockpit server streams it exactly like the
jarvis responder. The agent runs in a worker thread; chunks cross over a
queue. Tests inject a fake agent via ``agent_factory``.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from typing import Any, Callable, Iterator, Optional

from gateway.jarvis_local_http import (
    approval as approval_chunk,
    body,
    body_delta,
    done,
    error,
    phase,
    tool_call,
)

logger = logging.getLogger(__name__)

# Sentinel queued by the worker thread when the run finishes.
_FINISHED = object()

# How long (seconds) the stream waits between queue polls. Small enough to
# notice interrupts promptly; the queue get() itself blocks so idle cost is nil.
_POLL_SECONDS = 0.25

# Cap tool-result detail riding the wire (full results stay in the session
# transcript; the cockpit chip only needs a preview).
_DETAIL_MAX = 600

# ---------------------------------------------------------------------------
# Active-run registry (stop/interrupt support)
# ---------------------------------------------------------------------------

_active_lock = threading.Lock()
_active_agents: dict[str, Any] = {}


def _register_active(session_key: str, agent: Any) -> None:
    with _active_lock:
        _active_agents[session_key] = agent


def _unregister_active(session_key: str) -> None:
    with _active_lock:
        _active_agents.pop(session_key, None)


def interrupt_run(session_key: str) -> bool:
    """Interrupt the active agent run for ``session_key`` (if any).

    Returns True when a run was found and signalled.
    """
    with _active_lock:
        agent = _active_agents.get(session_key)
    if agent is None:
        return False
    try:
        agent.interrupt("stopped from the cockpit")
    except Exception:
        logger.debug("interrupt_run failed", exc_info=True)
        return False
    return True


def resolve_approval(session_key: str, choice: str) -> int:
    """Resolve the oldest pending owner approval for ``session_key``.

    Thin wrapper over :func:`tools.approval.resolve_gateway_approval` so the
    HTTP handler never imports the approval machinery directly. Returns the
    number of approvals resolved (0 = nothing pending).
    """
    from tools.approval import resolve_gateway_approval

    valid = {"once", "session", "always", "deny"}
    if choice not in valid:
        raise ValueError(f"invalid choice {choice!r}; expected one of {sorted(valid)}")
    return resolve_gateway_approval(session_key, choice)


# ---------------------------------------------------------------------------
# Agent construction (mirrors APIServerAdapter._create_agent)
# ---------------------------------------------------------------------------


def _create_agent(
    *,
    session_id: str,
    gateway_session_key: str,
    stream_delta_callback: Callable[[str], None],
    tool_start_callback: Callable[..., None],
    tool_complete_callback: Callable[..., None],
) -> Any:
    import os

    from run_agent import AIAgent
    from gateway.run import (
        GatewayRunner,
        _load_gateway_config,
        _resolve_gateway_model,
        _resolve_runtime_agent_kwargs,
    )
    from hermes_cli.tools_config import _get_platform_tools

    runtime_kwargs = _resolve_runtime_agent_kwargs()
    reasoning_config = GatewayRunner._load_reasoning_config()
    model = _resolve_gateway_model()
    user_config = _load_gateway_config()
    # platform_toolsets.cockpit in config.yaml overrides; default is the
    # hermes-cockpit toolset (full agent surface).
    enabled_toolsets = sorted(_get_platform_tools(user_config, "cockpit"))
    fallback_model = GatewayRunner._load_fallback_model()
    max_iterations = int(os.getenv("HERMES_MAX_ITERATIONS", "90"))

    session_db = None
    try:
        from hermes_state import SessionDB

        session_db = SessionDB()
    except Exception as e:  # pragma: no cover - session persistence is optional
        logger.debug("SessionDB unavailable for cockpit agent: %s", e)

    return AIAgent(
        model=model,
        **runtime_kwargs,
        max_iterations=max_iterations,
        quiet_mode=True,
        verbose_logging=False,
        enabled_toolsets=enabled_toolsets,
        session_id=session_id,
        platform="cockpit",
        stream_delta_callback=stream_delta_callback,
        tool_start_callback=tool_start_callback,
        tool_complete_callback=tool_complete_callback,
        session_db=session_db,
        fallback_model=fallback_model,
        reasoning_config=reasoning_config,
        gateway_session_key=gateway_session_key,
    )


def _preview(name: str, args: Any) -> str:
    """Short human label for a tool invocation (never raises)."""
    try:
        from agent.display import build_tool_preview

        return build_tool_preview(name, args or {}) or name
    except Exception:
        return name


def _clip(text: Any, limit: int = _DETAIL_MAX) -> str:
    s = str(text) if text is not None else ""
    return s if len(s) <= limit else s[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# The responder
# ---------------------------------------------------------------------------


def full_agent_responder(
    prompt: str,
    history: list[dict],
    *,
    session_id: Optional[str] = None,
    session_key: Optional[str] = None,
    agent_factory: Optional[Callable[..., Any]] = None,
) -> Iterator[dict]:
    """Stream one full-agent turn for ``prompt``.

    ``history`` is the prior transcript as ``[{"role": ..., "content": ...}]``.
    ``session_id`` scopes the short-term transcript; ``session_key`` is the
    stable per-client identity used for long-term memory scope AND the
    owner-approval channel (the ``approval`` chunk echoes it back so the
    client can resolve). ``agent_factory`` lets tests inject a fake agent —
    it receives the same kwargs as :func:`_create_agent`.

    Never raises: failures degrade to an ``error`` chunk followed by ``done``.
    """
    run_id = uuid.uuid4().hex[:12]
    sid = session_id or f"cockpit-{run_id}"
    skey = session_key or sid

    q: "queue.Queue[Any]" = queue.Queue()
    streamed_any_delta = False

    def _stream_delta(delta: str) -> None:
        if delta:
            q.put(body_delta(delta))

    def _tool_start(call_id: str, name: str, args: Any) -> None:
        q.put(phase("TOOL"))
        q.put(tool_call(str(call_id), name, _preview(name, args), "START"))

    def _tool_complete(call_id: str, name: str, args: Any, result: Any) -> None:
        q.put(
            tool_call(
                str(call_id),
                name,
                _preview(name, args),
                "OK",
                detail=_clip(result),
            )
        )

    def _approval_notify(approval_data: dict) -> None:
        data = dict(approval_data or {})
        q.put(
            approval_chunk(
                data.get("id") or uuid.uuid4().hex[:8],
                skey,
                data.get("description") or data.get("command") or "owner approval required",
                tool=data.get("tool") or data.get("command"),
            )
        )

    result_box: dict[str, Any] = {}

    def _worker() -> None:
        from gateway.session_context import clear_session_vars, set_session_vars
        from tools.approval import (
            register_gateway_notify,
            reset_current_session_key,
            set_current_session_key,
            unregister_gateway_notify,
        )

        approval_token = None
        session_tokens: list = []
        agent = None
        try:
            factory = agent_factory or _create_agent
            agent = factory(
                session_id=sid,
                gateway_session_key=skey,
                stream_delta_callback=_stream_delta,
                tool_start_callback=_tool_start,
                tool_complete_callback=_tool_complete,
            )
            _register_active(skey, agent)
            # Bind approval/session identity via contextvars so concurrent
            # runs never share approval channels (api_server pattern).
            approval_token = set_current_session_key(skey)
            session_tokens = set_session_vars(platform="cockpit", session_key=skey)
            register_gateway_notify(skey, _approval_notify)
            result_box["result"] = agent.run_conversation(
                user_message=prompt,
                conversation_history=list(history or []),
                task_id=sid,
            )
        except Exception as exc:  # pragma: no cover - defensive
            result_box["exception"] = exc
        finally:
            try:
                unregister_gateway_notify(skey)
            finally:
                _unregister_active(skey)
                if approval_token is not None:
                    try:
                        reset_current_session_key(approval_token)
                    except Exception:
                        pass
                if session_tokens:
                    try:
                        clear_session_vars(session_tokens)
                    except Exception:
                        pass
            q.put(_FINISHED)

    yield {"type": "thinking"}
    yield phase("RECEIVING")
    yield phase("THINKING")

    thread = threading.Thread(
        target=_worker, name=f"cockpit-agent-{run_id}", daemon=True
    )
    thread.start()

    while True:
        try:
            item = q.get(timeout=_POLL_SECONDS)
        except queue.Empty:
            continue
        if item is _FINISHED:
            break
        if isinstance(item, dict) and item.get("type") == "body_delta":
            streamed_any_delta = True
        yield item

    exc = result_box.get("exception")
    if exc is not None:
        yield error(_clip(exc, 400), retry_hint="check the gateway logs and model configuration")
        yield done()
        return

    result = result_box.get("result") or {}
    final_text = ""
    if isinstance(result, dict):
        final_text = result.get("final_response") or ""
        if result.get("failed"):
            yield error(_clip(result.get("error") or "agent run failed", 400))
            if final_text:
                yield body(final_text)
            yield done()
            return

    yield phase("FINAL")
    # Always emit the accumulated body: delta-aware clients replace their
    # accumulated text with it (authoritative form); delta-blind clients get
    # the whole reply here.
    yield body(final_text or ("" if streamed_any_delta else "(no response)"))
    yield done()


def make_responder() -> Callable[[str, list[dict]], Iterator[dict]]:
    """Adapter to the plain ``(prompt, history)`` responder signature.

    Used when the cockpit server runs with ``--agent full`` but a request
    arrives on the legacy ``/v1/jarvis/chat`` path with no session fields.
    """

    def _responder(prompt: str, history: list[dict]) -> Iterator[dict]:
        return full_agent_responder(prompt, history)

    return _responder


__all__ = [
    "full_agent_responder",
    "make_responder",
    "interrupt_run",
    "resolve_approval",
]
