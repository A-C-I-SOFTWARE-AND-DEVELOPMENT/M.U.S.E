# LM Studio native v1 REST API

This page documents how M.U.S.E. talks to a local **LM Studio** server,
and in particular how it uses LM Studio's **native v1 REST API** at
`/api/v1/*`.

LM Studio exposes two HTTP surfaces:

1. An **OpenAI-compatible** surface at `…/v1/*` (`/v1/chat/completions`,
   `/v1/models`, …). This is what inference runs against, and it follows
   the OpenAI schema — which deliberately omits context-window metadata.
2. A **native REST API** at `/api/v1/*`. It returns richer model
   information (real context window, load state, capabilities) and
   manages the model lifecycle.

> **Version note.** The native API was **officially released at
> `/api/v1/*` in LM Studio 0.4.0**. Earlier builds shipped a *beta* REST
> API at `/api/v0/*`. M.U.S.E. targets the released `/api/v1/*` surface;
> if you are on an older LM Studio, upgrade to 0.4.0+ so context-window
> auto-detection works.

## Configuration

LM Studio is a first-class provider. In `cli-config.yaml` (or via
`--provider` / `HERMES_INFERENCE_PROVIDER`):

```yaml
inference:
  provider: "lmstudio"
  base_url: "http://127.0.0.1:1234/v1"   # OpenAI-compat endpoint (note: /v1)
  # api_key: "…"   # optional — only if you enabled auth on the server
```

- `base_url` points at the **OpenAI-compat** endpoint (ends in `/v1`).
  M.U.S.E. derives the native base (`…/api/v1`) from it automatically.
- Both no-auth and auth-enabled server modes work. When an API key is
  set it is forwarded as `Authorization: Bearer <key>` to the native
  endpoints too.
- Local servers don't require auth; the key is optional.

### Remote instances

LM Studio doesn't have to run on `localhost`. You can point `base_url` at
another machine — a LAN box, a Tailscale peer, or a public IP / hostname
(e.g. `https://lmstudio.example.com/v1`). Setting `provider: "lmstudio"`
explicitly is what makes the remote case work: it tells M.U.S.E. to query
the native `/api/v1/models` endpoint even though the host isn't local, so
the model's real context window is detected instead of the 256K default
(fixes [NousResearch/hermes-agent#47200](https://github.com/NousResearch/hermes-agent/issues/47200)).
LAN/Tailscale hosts are treated as local automatically; only public
hosts strictly need the explicit `lmstudio` provider for native detection.

## v1 endpoints M.U.S.E. relies on

| Endpoint | Method | Used for |
|---|---|---|
| `/api/v1/models` | GET | Detect that the server is LM Studio; read the real context window and capabilities for each model. |
| `/api/v1/models/load` | POST | Preload a model before probing its context length, so the runtime window is reported instead of a default. |

Server detection probes `/api/v1/models` first because it is the most
specific signal that the server is LM Studio (see
`agent/model_metadata.py: detect_local_server_type`). Reasoning-effort
support is read from the per-model `allowed_options` the same endpoint
returns (see `agent/lmstudio_reasoning.py`).

## How context length is resolved

The OpenAI-compat `/v1/models` response omits the context window, so
M.U.S.E. reads it from the native `/api/v1/models` payload. Each model
object carries:

- `loaded_instances[].config.context_length` — the **actual runtime
  window** of a currently-loaded instance (the KV-cache size).
- `loaded_context_length` — the last runtime window configured for the
  model (top-level).
- `max_context_length` — the model's **training maximum**.

M.U.S.E. resolves the window in this priority order:

1. `loaded_instances[].config.context_length` — the real constraint
   right now. A model loaded at 122 651 tokens is capped at 122 651 even
   if its training max is 1 048 576, so this wins.
2. `loaded_context_length` — the last configured runtime window when no
   instance is currently loaded.
3. `max_context_length` — the training maximum, as a last resort.

> Steps 2–3 matter when the model **isn't currently loaded**. Without
> them the probe returned `None` and M.U.S.E. fell back to a generic
> default (regression
> [NousResearch/hermes-agent#47678](https://github.com/NousResearch/hermes-agent/issues/47678)).
> The fallback lets an unloaded model still report a sensible window.

Both the metadata cache (`fetch_endpoint_model_metadata`) and the
on-demand probe (`_query_local_context_length`) apply this order.

## Model naming

LM Studio's native API stores models as `publisher/slug`
(e.g. `nvidia/nvidia-nemotron-super-49b-v1`), while users typically
configure just the slug after the `local:` prefix. M.U.S.E. matches both
forms (`_model_id_matches`): an exact match, or a configured slug equal
to the basename after the last `/`.

## Troubleshooting

- **Context window looks wrong / capped.** LM Studio truncates to the
  *loaded* context length, not the model's training max. Set the context
  length in the model's load settings and reload, or let M.U.S.E.
  preload it via `/api/v1/models/load`.
- **Auto-detection returns nothing.** Confirm you're on LM Studio 0.4.0+
  (native API at `/api/v1/*`, not the old `/api/v0/*` beta) and that the
  local server is running and reachable at `base_url`.

## See also

- `cli-config.yaml.example` — the `lmstudio` provider block.
- `agent/model_metadata.py` — detection, metadata fetch, context-length
  resolution.
- `agent/lmstudio_reasoning.py` — reasoning-effort options from the
  native API.
