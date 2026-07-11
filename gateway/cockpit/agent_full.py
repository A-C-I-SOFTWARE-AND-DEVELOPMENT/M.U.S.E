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
import uuid
from typing import Any, Callable, Generator, Iterator, Optional

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

# Bound the chunk queue so a slow/gone consumer applies backpressure to the
# worker thread (q.put blocks) instead of letting an abandoned run pile up
# unbounded body_delta/tool_call chunks in memory.
_QUEUE_MAXSIZE = 512


def _claim_active(session_key: str, agent: Any) -> bool:
    """Atomically register ``agent`` as the active run for ``session_key``.

    Returns False when a run is ALREADY active for that key — the caller must
    refuse (one in-flight run per session key, so concurrent POSTs with the
    same client-supplied key can't clobber each other's agent/approval state).
    """
    with _active_lock:
        if session_key in _active_agents:
            return False
        _active_agents[session_key] = agent
        return True


def _unregister_active(session_key: str, agent: Any = None) -> None:
    """Remove the active run for ``session_key``.

    When ``agent`` is given, only clears the slot if it still holds that exact
    agent — so a late finally from a superseded run can't evict a newer one.
    """
    with _active_lock:
        cur = _active_agents.get(session_key)
        if agent is None or cur is agent:
            _active_agents.pop(session_key, None)


def interrupt_run(session_key: str) -> bool:
    """Interrupt the active agent run for ``session_key`` (if any).

    Returns True when a run was found and signalled. Also wakes a run that is
    blocked waiting on an owner approval: ``agent.interrupt`` alone does not
    unblock ``tools.approval``'s wait, so we resolve any pending approval as a
    denial first — otherwise a stopped-but-blocked run would hang until the
    approval timeout.
    """
    with _active_lock:
        agent = _active_agents.get(session_key)
    if agent is None:
        return False
    # Deny any pending approval so the blocked worker thread wakes immediately.
    try:
        from tools.approval import resolve_gateway_approval

        resolve_gateway_approval(session_key, "deny", resolve_all=True)
    except Exception:
        logger.debug("interrupt_run: approval wake failed", exc_info=True)
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
    reasoning_callback: Optional[Callable[[str], None]] = None,
    status_callback: Optional[Callable[..., None]] = None,
    interim_assistant_callback: Optional[Callable[..., None]] = None,
    model_override: Optional[str] = None,
    provider_override: Optional[str] = None,
    reasoning_config_override: Optional[dict] = None,
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

    runtime_kwargs = dict(_resolve_runtime_agent_kwargs())
    reasoning_config = reasoning_config_override or GatewayRunner._load_reasoning_config()
    model = (model_override or "").strip() or _resolve_gateway_model()
    if provider_override:
        runtime_kwargs["provider"] = provider_override
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
        reasoning_callback=reasoning_callback,
        status_callback=status_callback,
        interim_assistant_callback=interim_assistant_callback,
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


def _scrub(text: str) -> str:
    """Secret-redact before truncation (a secret straddling the clip boundary
    would otherwise evade the downstream regex)."""
    if not text:
        return text
    try:
        from hermes_cli.secrets_policy import redact

        return redact(text)
    except Exception:  # pragma: no cover - redaction is best-effort
        return text


def _clip(text: Any, limit: int = _DETAIL_MAX) -> str:
    # Scrub FIRST, then truncate — so a secret split by the clip can't leak its
    # (now-unmatchable) prefix. tool_call() also scrubs, but that runs on the
    # already-clipped string, so the ordering here is what actually protects it.
    s = _scrub(str(text) if text is not None else "")
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
    model: Optional[str] = None,
    provider: Optional[str] = None,
    effort: Optional[str] = None,
    fusion: Optional[bool] = None,
) -> Generator[dict, None, None]:
    """Stream one full-agent turn for ``prompt``.

    ``history`` is the prior transcript as ``[{"role": ..., "content": ...}]``.
    ``session_id`` scopes the short-term transcript; ``session_key`` is the
    stable per-client identity used for long-term memory scope AND the
    owner-approval channel (the ``approval`` chunk echoes it back so the
    client can resolve). ``agent_factory`` lets tests inject a fake agent —
    it receives the same kwargs as :func:`_create_agent`.

    Optional cockpit overrides (from Muse Omni chat controls):
      * ``model`` / ``provider`` — pin this turn's inference target
      * ``effort`` — reasoning effort (none/minimal/low/medium/high/xhigh)
      * ``fusion`` — force MoA fusion on/off for this turn

    Never raises: failures degrade to an ``error`` chunk followed by ``done``.
    """
    run_id = uuid.uuid4().hex[:12]
    sid = session_id or f"cockpit-{run_id}"
    skey = session_key or sid

    # Bounded so an abandoned/slow consumer applies backpressure instead of
    # letting chunks pile up unbounded in memory.
    q: "queue.Queue[Any]" = queue.Queue(maxsize=_QUEUE_MAXSIZE)
    streamed_any_delta = False
    thought_buf: list[str] = []
    thought_chars = 0
    _THOUGHT_FLUSH = 180  # emit a short summary every ~N chars of reasoning

    def _emit_thought(summary: str) -> None:
        text = (summary or "").strip()
        if not text:
            return
        # Keep chips short so the chat always shows motion without dumping CoT.
        if len(text) > 220:
            text = text[:217].rstrip() + "…"
        q.put({"type": "thought", "text": text})

    def _stream_delta(delta: str) -> None:
        nonlocal streamed_any_delta
        if delta:
            streamed_any_delta = True
            q.put(body_delta(delta))

    def _reasoning_delta(delta: str) -> None:
        nonlocal thought_chars
        if not delta:
            return
        thought_buf.append(delta)
        thought_chars += len(delta)
        if thought_chars >= _THOUGHT_FLUSH:
            joined = "".join(thought_buf).strip()
            thought_buf.clear()
            thought_chars = 0
            # Prefer the last sentence-ish fragment as the live summary.
            snippet = joined
            for sep in (". ", "\n", "? ", "! "):
                if sep in joined:
                    snippet = joined.rsplit(sep, 1)[-1].strip() or joined
                    break
            _emit_thought(snippet or "working through it…")

    def _status_cb(kind: str, message: str = "", *_a, **_k) -> None:
        label = (message or kind or "").strip()
        if label:
            _emit_thought(label)

    def _interim_cb(msg: Any) -> None:
        try:
            if isinstance(msg, dict):
                text = msg.get("content") or msg.get("text") or ""
            else:
                text = str(msg or "")
        except Exception:
            text = ""
        if text:
            _emit_thought(str(text)[:220])

    def _tool_start(call_id: str, name: str, args: Any) -> None:
        q.put(phase("TOOL"))
        preview = _preview(name, args)
        q.put(tool_call(str(call_id), name, preview, "START"))
        _emit_thought(f"using {name}" + (f" — {preview}" if preview and preview != name else ""))

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
        _emit_thought(f"finished {name}")

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
        _emit_thought("waiting for your approval")

    result_box: dict[str, Any] = {}

    # Resolve effort override once (shared by factory + status chip).
    reasoning_override = None
    effort_label = None
    if effort:
        from hermes_constants import parse_reasoning_effort

        reasoning_override = parse_reasoning_effort(str(effort))
        if reasoning_override is not None:
            effort_label = str(effort).strip().lower()

    def _worker() -> None:
        from gateway.session_context import clear_session_vars, set_session_vars
        from tools.approval import (
            register_gateway_notify,
            reset_current_session_key,
            set_current_session_key,
            unregister_gateway_notify,
        )
        from agent.fusion_router import set_fusion_override

        approval_token = None
        session_tokens: list = []
        try:
            set_fusion_override(fusion)
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
                set_fusion_override(None)
            except Exception:
                logger.debug("cockpit agent: clear fusion override failed", exc_info=True)
            try:
                unregister_gateway_notify(skey)
            finally:
                _unregister_active(skey, agent)
                if approval_token is not None:
                    try:
                        reset_current_session_key(approval_token)
                    except Exception:
                        # Best-effort contextvar cleanup — never mask the run's
                        # real outcome by raising from the finally.
                        logger.debug("cockpit agent: reset_current_session_key failed", exc_info=True)
                if session_tokens:
                    try:
                        clear_session_vars(session_tokens)
                    except Exception:
                        # Best-effort session-var cleanup; intentionally non-fatal.
                        logger.debug("cockpit agent: clear_session_vars failed", exc_info=True)
            # Never blocks: put on a full queue would deadlock a finished worker,
            # so drop-and-continue if the consumer is gone.
            try:
                q.put(_FINISHED, timeout=5)
            except queue.Full:
                # The consumer (client) is gone; nothing left to signal.
                logger.debug("cockpit agent: finished marker dropped (consumer gone)")

    yield {"type": "thinking"}
    yield phase("RECEIVING")
    # Immediate on-screen motion so the chat never looks frozen.
    model_chip = (model or "").strip() or "default model"
    bits = [f"starting with {model_chip}"]
    if effort_label:
        bits.append(f"effort {effort_label}")
    if fusion is True:
        bits.append("fusion on")
    elif fusion is False:
        bits.append("fusion off")
    yield {"type": "thought", "text": " · ".join(bits)}
    yield phase("THINKING")
    yield {"type": "thought", "text": "thinking…"}

    # Build the agent up front so we can refuse a duplicate in-flight run for
    # the same session key BEFORE starting a second worker (concurrent POSTs
    # with the same client-supplied key must not clobber each other).
    try:
        factory = agent_factory or _create_agent
        agent = factory(
            session_id=sid,
            gateway_session_key=skey,
            stream_delta_callback=_stream_delta,
            tool_start_callback=_tool_start,
            tool_complete_callback=_tool_complete,
            reasoning_callback=_reasoning_delta,
            status_callback=_status_cb,
            interim_assistant_callback=_interim_cb,
            model_override=model,
            provider_override=provider,
            reasoning_config_override=reasoning_override,
        )
    except TypeError:
        # Older test fakes / factories may not accept the new kwargs.
        try:
            agent = factory(
                session_id=sid,
                gateway_session_key=skey,
                stream_delta_callback=_stream_delta,
                tool_start_callback=_tool_start,
                tool_complete_callback=_tool_complete,
            )
        except Exception as exc:
            yield error(_clip(exc, 400), retry_hint="check the gateway logs and model configuration")
            yield done()
            return
    except Exception as exc:
        yield error(_clip(exc, 400), retry_hint="check the gateway logs and model configuration")
        yield done()
        return

    if not _claim_active(skey, agent):
        yield error(
            "a run is already in progress for this session — stop it or wait for it to finish",
            retry_hint="POST /v1/agent/stop with this session_key, then retry",
        )
        yield done()
        return

    thread = threading.Thread(
        target=_worker, name=f"cockpit-agent-{run_id}", daemon=True
    )
    thread.start()

    # On client disconnect the consumer generator is GC-closed and raises
    # GeneratorExit at a yield below; interrupt the worker so an abandoned run
    # (with live code execution) doesn't keep running headless.
    try:
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
    except GeneratorExit:
        # Client disconnect: interrupt the run but do NOT free the session slot
        # here — the worker's own finally is the SOLE releaser. That ordering
        # (worker unregisters the approval notify bridge, THEN frees the active
        # slot) means a fresh run with the same session key is refused (busy)
        # until the old worker has fully torn down, so the winding-down run can
        # never clobber a new run's notify bridge or approvals.
        interrupt_run(skey)
        raise

    # Flush any leftover reasoning into a final thought chip.
    if thought_buf:
        leftover = "".join(thought_buf).strip()
        thought_buf.clear()
        if leftover:
            yield {"type": "thought", "text": leftover[:220]}

    exc = result_box.get("exception")
    if exc is not None:
        yield error(_clip(exc, 400), retry_hint="check the gateway logs and model configuration")
        yield done()
        return

    result = result_box.get("result") or {}
    final_text = ""
    if isinstance(result, dict):
        final_text = result.get("final_response") or ""
        if result.get("fused"):
            yield {"type": "thought", "text": "fused multi-model answer"}
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
