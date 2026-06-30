# Per-request observability (request trace)

A thin, **opt-in** trace of the agent loop and model lifecycle. It answers, for
a single request: which model and wire endpoint were used, was the server local
or remote, how slow was the first token and the whole turn, how many tool calls
ran (and how many were malformed or failed), and did the request fall back to
another model. It is deliberately small — a per-request JSON record plus a
couple of model-lifecycle events — **not** a metrics system.

It is **off by default**. When disabled the default code path is unchanged: each
trace call site is a single guarded method on a shared no-op object — no
allocation, no I/O.

## Enabling it

Either set the config flag in `~/.hermes/config.yaml`:

```yaml
observability:
  request_trace: true
```

…or set the environment variable (which overrides the config flag):

```bash
export HERMES_REQUEST_TRACE=1
```

## Where traces go

Traces reuse the existing **cockpit event log** sink
(`gateway/cockpit/event_log.py`), a best-effort JSONL appender that never raises
into the caller. Records land in `${HERMES_HOME:-~/.hermes}/cockpit/events.jsonl`
and flow to the live SSE stream at `GET /v1/cockpit/events/stream` — so the
cockpit "debug panel" need is already covered with no new endpoint.

For an at-a-glance **analytical view**, `GET /v1/cockpit/trace` folds the recent
records into a summary — latency percentiles (p50/p95 first-token & total),
tool-call failure rate, fallback rate, and endpoint / model / local-vs-remote
distributions. It is read-only, bearer-auth'd like the rest of the cockpit, and
honest-empty when tracing is off:

```jsonc
{
  "request_count": 12,
  "latency_ms": {"first_token_p50": 140, "first_token_p95": 410,
                 "total_p50": 1800, "total_p95": 5200, "first_token_samples": 12},
  "tool_calls": {"total": 47, "parse_errors": 0, "exec_failures": 2, "failure_rate": 0.0426},
  "fallback": {"count": 1, "rate": 0.0833},
  "endpoints": {"openai_v1_chat_completions": 12},
  "models": {"qwen": 9, "gpt-4o": 3},
  "remote": {"local": 9, "remote": 3, "unknown": 0},
  "lifecycle": {"load_count": 4, "load_ok": 4, "unload_count": 3, "unload_ok": 3}
}
```

Two raw record shapes appear in the event log (source `hook`):

- **`request_trace`** — one per `run_conversation`, emitted at turn end:

  ```json
  {
    "trace_id": "…", "session_id": "…",
    "model": "qwen", "provider": "lmstudio",
    "endpoint": "openai_v1_chat_completions", "is_remote": false,
    "first_token_ms": 412, "api_calls": 2, "api_latency_ms": 1830,
    "total_latency_ms": 2050,
    "tool_calls": 3, "tool_parse_errors": 0, "tool_exec_failures": 1,
    "fallback_used": false, "fallback_model": null, "fallback_reason": null
  }
  ```

- **`model_lifecycle`** — LM Studio load/unload events (they happen between
  requests, e.g. on a `/model` switch, so they are their own records):

  ```json
  {"event": "unload", "model": "qwen", "provider": "lmstudio",
   "reason": "manual_switch", "ok": true, "is_remote": false}
  ```

## What is and isn't captured

Captured from existing measurement points (cheap, exact):

- `endpoint` / `is_remote` — derived from the agent's `api_mode` and base URL.
- `first_token_ms` — via the streaming `on_first_delta` callback (only on the
  streaming path; `null` otherwise).
- `api_calls` / `api_latency_ms` / `total_latency_ms` — from the loop's existing
  per-call timing plus end-to-end wall clock.
- tool-call counts — at the parse and failure sites in both the sequential and
  concurrent executors.
- fallback outcome — recorded when `try_activate_fallback` switches models.
- LM Studio load/unload `ok` + duration — at the load/unload call sites.

**Not** captured today (left absent rather than faked):

- **Live VRAM** — LM Studio's native API exposes model *file sizes*, not live
  VRAM usage. Honest VRAM accounting needs an out-of-band probe (e.g.
  `nvidia-smi`) and is intentionally deferred.
- **Unload reasons other than `manual_switch`** — idle-timeout /
  memory-pressure unloads have no code paths yet, so they are never reported.

## Endpoint strategy (why `endpoint` is almost always OpenAI-compatible)

The agent loop drives LM Studio (and other local servers) over the
OpenAI-compatible `/v1/chat/completions` path — that's where tool-calls,
streaming, retry/fallback, and reasoning-effort mapping are wired. The native
`/api/v1/*` endpoints are **lifecycle-only** (load/unload/download). So a
healthy request trace reads `endpoint: openai_v1_chat_completions`; a
`native_api_v1_chat` value would signal a misconfiguration worth surfacing.

## Implementation

- Module: [`hermes_cli/request_trace.py`](../../hermes_cli/request_trace.py)
  (`RequestTrace`, `lifecycle_event`, and the pure `summarize` aggregator).
- Wired in: `agent/conversation_loop.py` (start/first-token/api-latency/emit),
  `agent/tool_executor.py` (tool counts + failures, both paths),
  `agent/chat_completion_helpers.py` (fallback), `run_agent.py` +
  `agent/agent_runtime_helpers.py` (LM Studio load/unload).
- Summary endpoint: `gateway/cockpit/handlers.py:trace_summary` registered at
  `GET /v1/cockpit/trace` in `gateway/cockpit/server.py`.
- Tests: [`tests/test_request_trace.py`](../../tests/test_request_trace.py) and
  the endpoint tests in
  [`tests/gateway/test_cockpit_events_stream.py`](../../tests/gateway/test_cockpit_events_stream.py).
