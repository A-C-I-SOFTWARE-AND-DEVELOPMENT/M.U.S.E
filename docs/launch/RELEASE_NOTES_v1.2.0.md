# Hermes Agent v1.2.0 — LM Studio native v1 REST API

LM Studio 0.4.0 officially released its native REST API at `/api/v1/*` (the
old beta lived at `/api/v0/*`). This release adopts that API end-to-end:
accurate context-window detection for local **and** remote servers, model
lifecycle management (load / unload / download), and automatic VRAM freeing on
model switch.

## Highlights

- **Accurate context windows from the native API.** MUSE reads each model's real
  context window from `/api/v1/models` (the OpenAI-compat `/v1/models` omits it),
  resolving `loaded_instances[].config.context_length` →
  `loaded_context_length` → `max_context_length`.
- **Remote LM Studio works.** A remote instance (public IP / hostname) reached
  with `provider: lmstudio` now reports its real window instead of defaulting to
  256K.
- **Model lifecycle.** New helpers and agent tools to **unload** (free VRAM),
  **download** (catalog id or Hugging Face link), and poll **download status**.
- **Auto-unload on switch.** Switching away from an LM Studio model unloads it
  *before* the next model loads — no transient double-VRAM spike on the same box.

## Context-length resolution (local + remote)

- The native `/api/v1/models` payload is the source of truth; resolution order is
  loaded-instance window → last configured runtime window → training maximum.
- An unloaded model now reports a sensible window via the `max_context_length`
  fallback instead of returning nothing (fixes
  [NousResearch/hermes-agent#47678](https://github.com/NousResearch/hermes-agent/issues/47678)).
- The native query is no longer gated to local hosts: `provider: lmstudio`
  reaches it for remote servers too (fixes
  [NousResearch/hermes-agent#47200](https://github.com/NousResearch/hermes-agent/issues/47200)).

## Model lifecycle

Thin, best-effort wrappers in `hermes_cli/models.py` (alongside the existing
`ensure_lmstudio_model_loaded`):

- `unload_lmstudio_model` → `POST /api/v1/models/unload` (idempotent — a 404
  "nothing loaded" still succeeds).
- `download_lmstudio_model` → `POST /api/v1/models/download` (`model` =
  catalog id or HF link, optional `quantization`; returns `{status, job_id?}`).
- `lmstudio_download_status` → `GET /api/v1/models/download/status?job_id=…`.

### Auto-unload on model switch

`switch_model` unloads the model you're leaving (different model, or a different
provider) before preloading the new one, releasing its KV cache first. No-op
when staying on the same model; best-effort, never blocks the switch.

### Agent tools

The lifecycle helpers are exposed as agent tools so the model can manage models
on the user's behalf: `lmstudio_download_model`, `lmstudio_download_status`,
`lmstudio_unload_model`. They're **gated** by a reachability check, so they only
enter the tool schema when an LM Studio server is up (hidden in cloud-only
sessions). Connection resolves like the `lmstudio` provider (`base_url` arg →
`$LM_BASE_URL` → default `http://127.0.0.1:1234/v1`); the API key is read from
`$LM_API_KEY` only — never a model-supplied argument.

> **Not adopted:** the native `/api/v1/chat` endpoint. It cannot accept custom
> client-defined tools (only LM-Studio-side MCP), so it can't drive MUSE's
> tool-using agent loop. Inference stays on the OpenAI-compat
> `/v1/chat/completions`, which does support custom tools.

## Fixes (test infrastructure)

- **pytest-timeout on Windows.** Dropped the pinned `--timeout-method=signal`
  (Unix-only `SIGALRM`) so pytest-timeout auto-selects `thread` on Windows —
  every xdist worker had been crashing at setup with
  `AttributeError: module 'signal' has no attribute 'SIGALRM'`. Unchanged on
  Linux/CI, where `signal` is still selected.
- **`pair_confirm` owner-phrase test.** Aligned a stale test + docstring with the
  intended behavior (the owner phrase is required only in `--allow-external`
  mode; loopback skips it) — `main` had been red on this unrelated test.

## New modules / files

- `tools/lmstudio_tools.py` — the three lifecycle agent tools.
- New helpers in `hermes_cli/models.py`; routing changes in
  `agent/model_metadata.py` and `agent/agent_runtime_helpers.py`.

## Docs

- New: `docs/integrations/lmstudio-rest-api.md` — endpoints MUSE uses,
  context-length resolution, lifecycle helpers, auto-unload, agent tools,
  remote instances, troubleshooting.
- Updated: `cli-config.yaml.example`, `docs/README.md`.

## Tests

- `tests/agent/test_model_metadata_local_ctx.py` — context-length fallback +
  remote-provider routing.
- `tests/hermes_cli/test_lmstudio_lifecycle.py` — unload / download / status.
- `tests/run_agent/test_switch_model_lmstudio_unload.py` — auto-unload on switch.
- `tests/tools/test_lmstudio_tools.py` — agent tools (gating, handlers,
  registration).
- `tests/gateway/test_cockpit_device_pairing.py` — corrected owner-phrase cases.

## CI

- `Python unit (muse + redact + orchestrator)` is now a **required** status
  check on `main`.
