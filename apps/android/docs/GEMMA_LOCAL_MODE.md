# Gemma / Local Models (v1.5)

v1.5 treats **Gemma as a first-class local option** for coding and chat — but
Gemma is **never required** for the app to launch or for the coding cockpit to
work. Local models run on a backend you control (Termux on-device, or a LAN/VPS
host) via an OpenAI-compatible runtime such as **Ollama**.

## Why local-first

- No provider key, no per-token cost, no data leaving your device/network.
- The free-first router prefers `local_oss` before any paid lane.

## Install Gemma via Ollama (on the backend host)

```bash
# 1. Install Ollama:  https://ollama.com/download
# 2. Pull a Gemma variant (sizes vary by hardware):
ollama pull gemma3            # or the tag your host can run
# 3. Verify it's installed and reachable:
curl http://127.0.0.1:11434/api/tags
```

Refs: Gemma + Ollama integration
<https://ai.google.dev/gemma/docs/integrations/ollama>; Gemma model card
<https://ai.google.dev/gemma/docs/core/model_card_4>. Capabilities described in
the model card (e.g. multimodal input, large context) are **vendor-reported**;
what actually runs depends on the variant you pull and your hardware.

The gateway already speaks to Ollama (`gateway/cockpit/generate.py`): it asks
`/api/tags` what is *actually installed* and prefers a tag present in the
router policy. Set `OLLAMA_HOST` to point at a non-default runtime.

## Honest status vocabulary

The cockpit never shows a model as "ready" unless it has been **smoke-tested**
or the backend explicitly reports readiness. Status is one of:

| Label | Meaning |
|---|---|
| **Not configured** | No local runtime base URL set. |
| **Configured** | A runtime URL is set but not yet probed. |
| **Runtime reachable** | The runtime answered (e.g. `/api/tags` returned). |
| **Variant installed** | A Gemma variant is present in the runtime. |
| **Smoke-tested** | An explicit, owner-initiated tiny generation succeeded. |
| **Promoted for task** | The router selected this model for a task class. |
| **Fallback only** | Available but not the primary route. |
| **Blocked / error** | Probe or generation failed (reason shown). |

A model becomes **Smoke-tested** only after you explicitly run the smoke test —
the app never fabricates readiness.

## Gemma thinking blocks

Gemma "thinking"/reasoning content is treated as transient and is **not**
stored in history or memory — consistent with the memory rules (no
chain-of-thought persisted). Only final answers and source-backed facts are
eligible for memory, and only after owner approval.

## Where it appears today vs. next

- **Today:** the **Model Route** screen surfaces the free-first router policy
  and per-task routes (`/v1/cockpit/model-routes`, `/v1/cockpit/models`) with
  owner overrides; the coding packet shows the suggested `model_lane_hint`.
- **Next (WS2):** a dedicated **Model Center** screen backed by
  `GET /v1/cockpit/models/local` (+ an explicit `smoke` action) renders the
  full label set above and an Ollama base-URL setting. Until it lands, Gemma
  status is shown as "not yet probed" rather than a fabricated "ready".
