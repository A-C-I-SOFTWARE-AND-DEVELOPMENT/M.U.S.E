# Agent-loop efficiency audit (per-turn hot path)

A data-driven pass over the functions muse calls on **every agent-loop
iteration**, profiled with a representative turn (≈55 tool schemas, ≈40-message
history). The goal: find behaviour-preserving wins, bank the safe ones, and
honestly bound what's left. Two optimisations from this audit are already
landed (see below); the rest is a map for follow-up.

Method: `timeit`, 800 iterations per op, warm process. Numbers are µs/call on
the audit machine — treat them as **relative** signal, not absolute SLAs.

## Findings

| Per-turn operation | µs/call | Status |
|---|---:|---|
| `estimate_request_tokens_rough` (tool-schema term) | ~138 | **Optimised ~12×** (was ~452) — tool-schema length memoised |
| `get_provider_request_timeout` (no `config.yaml`) | ~308 | **Optimised ~4.4×** (was ~1306) — defaults-only config result cached |
| `estimate_messages_tokens_rough` | ~137 | Inherent `O(history)`; **cache unsafe** — message dicts mutate in place |
| `json.dumps(messages)` (wire serialise) | ~127 | Inherent; required to send the request |
| `get_tool_definitions` (quiet, cache hit) | see note | Memoised in code; cache-hit behaviour **needs verification** under real gateway state (a bare-harness probe suggested recompute — flagged, not confirmed) |

## Banked optimisations (behaviour-preserving, tested)

1. **Tool-schema length memoisation** — `agent/model_metadata.py`.
   `estimate_request_tokens_rough` was calling `str(tools)` (serialising the
   full ~60 KB schema list) on every call just to take its length. Profiling
   showed ~92% of the function's cost was that one line. Memoised on the tools
   list's `(id, len)` via a bounded LRU; output byte-for-byte identical, keyed
   on `len` so an in-place tool append is seen as a change. **452 → 36 µs/call
   for the tool term (~12×).** Tests: `TestEstimateRequestTokensRough`.

2. **Defaults-only config caching** — `hermes_cli/config.py`.
   `load_config()` rebuilt the whole config from `DEFAULT_CONFIG` (deepcopy +
   normalise + env-expand + deepcopy) on **every call when no `config.yaml`
   exists**, because the cache only populated for an existing file. The agent
   loop reads config 20–50×/turn, so default / fresh / Termux / CI installs paid
   it repeatedly. Folded the missing-file case into the cache under a sentinel
   key, with correct invalidation when a file later appears or is deleted.
   **1306 → 296 µs/call (~4.4×).** Tests: `TestLoadConfigNoFileCaching`.

## Deliberately NOT optimised (and why)

- **`estimate_messages_tokens_rough`** — the obvious move (cache per-message
  char counts) is **unsafe**: message dicts are mutated in place across the turn
  (guardrail observations appended, sequence repairs, content cleaning), so a
  per-message cache keyed on identity could go stale and produce a wrong token
  estimate → a wrong compression decision. The tool-schema cache is safe only
  because tool schemas are stable within a turn; messages are not. Left as-is.
- **`json.dumps(messages)` / wire serialisation** — inherent cost of sending the
  request; no behaviour-preserving shortcut.

## Follow-ups (need real runtime state or owner direction)

- **Verify `get_tool_definitions` cache-hit rate** under a live gateway/agent
  (real registry generation + config fingerprint), not a bare import. The
  cache key folds in `registry._generation`, a config-file fingerprint, and the
  toolset sets; if any of those churn per turn the memo would miss. Worth a
  one-off instrumented check before assuming it's hot.
- **Production profiling** — the `request_trace` instrument (this PR) records
  `first_token_ms`, `total_latency_ms`, `api_latency_ms`, tool counts, retries,
  and compression cost per request. Once traffic flows, `hermes trace` /
  `GET /v1/cockpit/trace` rank the *real* hotspots, which beats micro-profiling
  guesses. That's the intended next iteration of this audit.

## How to reproduce

The profiling snippets live in this PR's history; re-run with a warm process and
a representative tool/message set. Re-profile after any change to the token
estimators, config loader, or tool-definition cache.
