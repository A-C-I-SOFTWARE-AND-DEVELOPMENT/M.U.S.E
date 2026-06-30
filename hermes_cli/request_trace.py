"""Thin, opt-in per-request observability for the agent loop and model lifecycle.

This is a deliberately *small* surface — a per-request JSON trace plus a couple
of standalone model-lifecycle events — not a metrics system. It answers, for one
request: which model/endpoint was used, was it local or remote, how slow was the
first token and the whole turn, how many tool calls ran (and how many were
malformed or failed), and did the request fall back to another model.

Design choices that keep it cheap and honest:

* **Off by default.** Enabled via ``observability.request_trace: true`` in
  ``~/.hermes/config.yaml`` or the ``HERMES_REQUEST_TRACE=1`` environment
  variable. When disabled, :meth:`RequestTrace.start` returns a shared no-op
  instance so every call site is a single attribute read + early-return — no
  allocation, no I/O, and the default code path stays byte-for-byte unchanged.
* **Reuses the existing sink.** Traces are emitted through
  :func:`gateway.cockpit.event_log.emit`, a best-effort JSONL appender that
  *never raises into the caller* and already powers ``GET
  /v1/cockpit/events/stream``. No new endpoint, no new file, nothing to break a
  request.
* **No invented data.** Signals that the code can't actually observe today
  (live VRAM, idle-timeout / memory-pressure unload reasons) are simply absent
  rather than faked. Only what the call sites genuinely know is recorded.

Trace records land as ``message="request_trace"`` (source ``hook``); lifecycle
load/unload records land as ``message="model_lifecycle"``.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

_TRUTHY = {"1", "true", "yes", "on"}

# Maps the agent's internal ``api_mode`` to the human-readable wire endpoint the
# request actually used. For LM Studio (and most local servers) the agent loop
# drives the OpenAI-compatible ``/v1/chat/completions`` path; the native
# ``/api/v1/*`` endpoints are lifecycle-only and never appear here.
_ENDPOINT_BY_API_MODE = {
    "chat_completions": "openai_v1_chat_completions",
    "anthropic_messages": "anthropic_v1_messages",
    "codex_responses": "openai_v1_responses",
    "bedrock_converse": "bedrock_converse",
}

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _flag_enabled() -> bool:
    """True when request tracing is switched on (env wins over config)."""
    env = os.environ.get("HERMES_REQUEST_TRACE")
    if env is not None:
        return env.strip().lower() in _TRUTHY
    try:
        from hermes_cli.config import load_config_readonly

        cfg = load_config_readonly()
        obs = cfg.get("observability") or {}
        return bool(obs.get("request_trace", False))
    except Exception:  # pragma: no cover - config must never break the request
        return False


def _endpoint_for(api_mode: Optional[str]) -> str:
    api_mode = api_mode or ""
    return _ENDPOINT_BY_API_MODE.get(api_mode, api_mode or "unknown")


def _is_remote(base_url: Optional[str]) -> Optional[bool]:
    """Best-effort local-vs-remote flag from a base URL.

    Returns ``False`` for loopback hosts (true local server), ``True`` for any
    other host, and ``None`` when there is no URL to judge (e.g. native-SDK
    cloud providers that carry no base_url).
    """
    if not base_url:
        return None
    try:
        from urllib.parse import urlparse

        host = (urlparse(base_url).hostname or "").lower()
    except Exception:  # pragma: no cover - defensive
        return None
    if not host:
        return None
    return host not in _LOOPBACK_HOSTS


def _emit_event(message: str, attributes: dict[str, Any], session_id: Optional[str]) -> None:
    """Append one event via the cockpit event log. Best-effort."""
    try:
        from gateway.cockpit.event_log import emit as _emit

        _emit("info", "hook", message, job_id=session_id, attributes=attributes)
    except Exception:  # pragma: no cover - observability must never break callers
        pass


@dataclass
class RequestTrace:
    """One request's worth of observability, assembled in-process then emitted.

    All mutation methods are guarded by :attr:`enabled`; when off they are
    no-ops, which is what the shared :data:`_DISABLED` instance relies on.
    """

    enabled: bool = False
    trace_id: str = ""
    session_id: Optional[str] = None
    model: str = ""
    provider: str = ""
    endpoint: str = ""
    is_remote: Optional[bool] = None
    # timing
    _mono0: float = 0.0
    first_token_ms: Optional[int] = None
    api_calls: int = 0
    api_latency_ms: int = 0
    total_latency_ms: int = 0
    # tool-call behaviour
    tool_calls: int = 0
    tool_parse_errors: int = 0
    tool_exec_failures: int = 0
    # fallback outcome
    fallback_used: bool = False
    fallback_model: Optional[str] = None
    fallback_reason: Optional[str] = None
    # retry / failover classification (per FailoverReason)
    retry_count: int = 0
    retry_reasons: dict[str, int] = field(default_factory=dict)
    # context compression
    compressions: int = 0
    compression_ms: int = 0
    tokens_saved: int = 0

    @classmethod
    def start(
        cls,
        *,
        model: str,
        provider: str,
        base_url: Optional[str] = None,
        api_mode: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> "RequestTrace":
        """Begin a trace, or return the shared no-op when tracing is disabled."""
        if not _flag_enabled():
            return _DISABLED
        return cls(
            enabled=True,
            trace_id=uuid.uuid4().hex,
            session_id=session_id,
            model=model or "",
            provider=provider or "",
            endpoint=_endpoint_for(api_mode),
            is_remote=_is_remote(base_url),
            _mono0=time.monotonic(),
        )

    def mark_first_token(self) -> None:
        if not self.enabled or self.first_token_ms is not None:
            return
        self.first_token_ms = int((time.monotonic() - self._mono0) * 1000)

    def add_api_call(self, duration_s: float) -> None:
        if not self.enabled:
            return
        self.api_calls += 1
        self.api_latency_ms += int(duration_s * 1000)

    def add_tool_calls(self, n: int) -> None:
        if self.enabled and n:
            self.tool_calls += n

    def add_parse_error(self, n: int = 1) -> None:
        if self.enabled:
            self.tool_parse_errors += n

    def add_exec_failure(self, n: int = 1) -> None:
        if self.enabled:
            self.tool_exec_failures += n

    def record_fallback(self, to_model: str, reason: Any = None) -> None:
        if not self.enabled:
            return
        self.fallback_used = True
        self.fallback_model = to_model or None
        self.fallback_reason = str(reason) if reason is not None else None

    def record_retry_reason(self, reason: Any) -> None:
        """Record one API-error classification (a retry/failover decision)."""
        if not self.enabled:
            return
        self.retry_count += 1
        key = str(reason) if reason is not None else "unknown"
        self.retry_reasons[key] = self.retry_reasons.get(key, 0) + 1

    def record_compression(self, ms: int, tokens_before: int, tokens_after: int) -> None:
        """Record one context-compression pass: duration and tokens reclaimed."""
        if not self.enabled:
            return
        self.compressions += 1
        self.compression_ms += int(ms)
        saved = int(tokens_before) - int(tokens_after)
        if saved > 0:
            self.tokens_saved += saved

    def as_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "model": self.model,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "is_remote": self.is_remote,
            "first_token_ms": self.first_token_ms,
            "api_calls": self.api_calls,
            "api_latency_ms": self.api_latency_ms,
            "total_latency_ms": self.total_latency_ms,
            "tool_calls": self.tool_calls,
            "tool_parse_errors": self.tool_parse_errors,
            "tool_exec_failures": self.tool_exec_failures,
            "fallback_used": self.fallback_used,
            "fallback_model": self.fallback_model,
            "fallback_reason": self.fallback_reason,
            "retry_count": self.retry_count,
            "retry_reasons": dict(self.retry_reasons),
            "compressions": self.compressions,
            "compression_ms": self.compression_ms,
            "tokens_saved": self.tokens_saved,
        }

    def emit(self) -> None:
        """Stamp total wall-clock latency and append the trace. Idempotent-safe."""
        if not self.enabled:
            return
        self.total_latency_ms = int((time.monotonic() - self._mono0) * 1000)
        _emit_event("request_trace", self.as_dict(), self.session_id)


# Shared, immutable-in-effect no-op returned whenever tracing is disabled. Its
# guarded methods all early-return, so call sites pay only a method call.
_DISABLED = RequestTrace(enabled=False)


def current(agent: Any) -> RequestTrace:
    """Return the agent's active trace, or the shared no-op if none is set."""
    return getattr(agent, "_active_trace", None) or _DISABLED


def lifecycle_event(
    event: str,
    *,
    model: str,
    provider: str = "lmstudio",
    reason: Optional[str] = None,
    ok: Optional[bool] = None,
    dur_ms: Optional[int] = None,
    resolved_ctx: Optional[int] = None,
    base_url: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Emit a standalone model-lifecycle event (``load`` / ``unload``).

    These happen between requests (e.g. a ``/model`` switch), so they are their
    own records rather than fields on a per-request trace. Gated by the same
    flag and best-effort like everything else here.
    """
    if not _flag_enabled():
        return
    attributes = {
        "event": event,
        "model": model or "",
        "provider": provider or "",
        "reason": reason,
        "ok": ok,
        "dur_ms": dur_ms,
        "resolved_ctx": resolved_ctx,
        "is_remote": _is_remote(base_url),
    }
    _emit_event("model_lifecycle", attributes, session_id)


def _percentile(values: list[int], pct: float) -> Optional[int]:
    """Nearest-rank percentile of a list of ints (None when empty)."""
    if not values:
        return None
    ordered = sorted(values)
    # nearest-rank: rank = ceil(pct/100 * N), 1-indexed
    rank = max(1, int(-(-pct * len(ordered) // 100)))
    return ordered[min(rank, len(ordered)) - 1]


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate raw cockpit event-log records into a trace summary.

    Accepts the records returned by :func:`gateway.cockpit.event_log.read`
    (each ``{message, attributes, ...}``) and folds the ``request_trace`` and
    ``model_lifecycle`` entries into latency percentiles, tool-failure / fallback
    rates, and endpoint / model distributions. Pure and side-effect-free so it
    can be unit-tested without HTTP or a live log. Honest-empty when there are no
    trace records.
    """
    traces = [
        r.get("attributes") or {}
        for r in records
        if isinstance(r, dict) and r.get("message") == "request_trace"
    ]
    lifecycle = [
        r.get("attributes") or {}
        for r in records
        if isinstance(r, dict) and r.get("message") == "model_lifecycle"
    ]

    def _ints(key: str) -> list[int]:
        out = []
        for t in traces:
            v = t.get(key)
            if isinstance(v, (int, float)):
                out.append(int(v))
        return out

    def _dist(key: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for t in traces:
            k = t.get(key)
            label = "unknown" if k is None else str(k)
            counts[label] = counts.get(label, 0) + 1
        return counts

    n = len(traces)
    first_token = _ints("first_token_ms")
    total_latency = _ints("total_latency_ms")
    tool_calls = sum(_ints("tool_calls"))
    parse_errors = sum(_ints("tool_parse_errors"))
    exec_failures = sum(_ints("tool_exec_failures"))
    fallbacks = sum(1 for t in traces if t.get("fallback_used"))

    def _rate(num: int, den: int) -> Optional[float]:
        return round(num / den, 4) if den else None

    load_events = [e for e in lifecycle if e.get("event") == "load"]
    unload_events = [e for e in lifecycle if e.get("event") == "unload"]

    retry_total = sum(_ints("retry_count"))
    retry_reasons: dict[str, int] = {}
    for t in traces:
        reasons = t.get("retry_reasons")
        if isinstance(reasons, dict):
            for k, v in reasons.items():
                if isinstance(v, (int, float)):
                    retry_reasons[str(k)] = retry_reasons.get(str(k), 0) + int(v)

    return {
        "request_count": n,
        "latency_ms": {
            "first_token_p50": _percentile(first_token, 50),
            "first_token_p95": _percentile(first_token, 95),
            "total_p50": _percentile(total_latency, 50),
            "total_p95": _percentile(total_latency, 95),
            "first_token_samples": len(first_token),
        },
        "tool_calls": {
            "total": tool_calls,
            "parse_errors": parse_errors,
            "exec_failures": exec_failures,
            "failure_rate": _rate(exec_failures, tool_calls),
        },
        "fallback": {
            "count": fallbacks,
            "rate": _rate(fallbacks, n),
        },
        "endpoints": _dist("endpoint"),
        "models": _dist("model"),
        "remote": {
            "local": sum(1 for t in traces if t.get("is_remote") is False),
            "remote": sum(1 for t in traces if t.get("is_remote") is True),
            "unknown": sum(1 for t in traces if t.get("is_remote") is None),
        },
        "retries": {
            "count": retry_total,
            "reasons": retry_reasons,
        },
        "compression": {
            "passes": sum(_ints("compressions")),
            "total_ms": sum(_ints("compression_ms")),
            "tokens_saved": sum(_ints("tokens_saved")),
        },
        "lifecycle": {
            "load_count": len(load_events),
            "load_ok": sum(1 for e in load_events if e.get("ok")),
            "unload_count": len(unload_events),
            "unload_ok": sum(1 for e in unload_events if e.get("ok")),
        },
    }


__all__ = ["RequestTrace", "current", "lifecycle_event", "summarize"]
