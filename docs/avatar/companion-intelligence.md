# Companion intelligence — persona, model routing, and the room editor

How the companion thinks, which brain it uses for what, and the design for the
AI-furnished room.

---

## 1. Adopted persona — "make my avatar Goku" ✅ built

Set a character and the companion adopts its personality:

```
POST /v1/cockpit/avatar/persona   {"description": "Goku from Dragon Ball", "name": "Goku"}
GET  /v1/cockpit/avatar/persona
POST /v1/cockpit/avatar/persona   {"description": ""}      # clears it
```

The configured model **researches** the character from its knowledge and writes
a persona directive; it's persisted (`${HERMES_HOME}/jarvis_prime/avatar_persona.json`)
and **prepended to every chat turn**, so the companion speaks/behaves in
character while staying genuinely helpful (`gateway/cockpit/persona_store.py`,
injected in `gateway/cockpit/agent.py`). Falls back to a plain directive when no
model is reachable. *(In-app "describe your character" field calls this endpoint
— small UI wire pending.)*

---

## 2. Model routing — which brain, when ✅ working + validated

MUSE classifies each turn and routes to the right brain (free-first), validated
this session (`tests/gateway/test_cockpit_routing.py`, `_brain_hint`):

| Task kind (from the turn) | Brain | Why |
|---|---|---|
| **chat** (companion, high confidence) | **local Qwen** (offline, private, fast) | everyday talk |
| **code** (builder mode / `codex_*`/`claude_code` route) | **coder-local → Codex (ChatGPT) → Claude Code** | implementation/review |
| **reasoning / hard / low-confidence / council** | **DeepSeek-R1 (local)** → **escalate to a stronger cloud brain first** | deep problems |
| **vision / image** | **Gemini** | images & visual understanding |

Free-first by default (local before cloud); a genuinely hard turn **escalates**
to the stronger subscription/cloud brain first, then falls back. The selector
even picks a coder vs reasoning **local** model when several are installed.

### Version awareness
Specific model **versions** are resolved by the free-first **model policy**
(`hermes models bootstrap` → `model_policy.json`) and the router
(`hermes_cli/model_router.py`), not hard-coded in the app:
- **Anthropic**: Claude Code worker uses your subscription's current model
  (e.g. Opus 4.8 / 4.7) via the CLI — no version pinned in-app.
- **OpenAI**: Codex worker uses your ChatGPT plan's model (e.g. GPT-5.x).
- **DeepSeek / Qwen**: the local tag you pulled (e.g. `deepseek-r1:8b`,
  `qwen2.5:3b`) — `pick_model()` prefers a policy tag, else what's installed.
- **Gemini**: the configured Gemini model for vision/image.

To pin exact versions per task, set them in `model_policy.json` /
`auxiliary.<task>.model` (config) — the router honours those overrides.

---

## 3. Pipeline coherence ✅ validated

`MUSE → Navigator → Orchestrator → Worker → Ledger`, validated end-to-end this
session: `submit_job → navigate_job (localizes @conf 1.0) → dispatch_job (5-step
contract) → owner-gate (execute blocked without the exact-phrase approval) →
replay`. The companion has full, owner-gated app access per the operating-system
doc and verification gates. 46 routing/pipeline tests green.

---

## 4. AI room editor — "type *Victorian desk* → generate it" 🔜 designed

The plan (needs an **image-generation model** wired — the one remaining piece):

1. `POST /v1/cockpit/avatar/room-item {"prompt": "a Victorian desk"}` → calls a
   configured **image model** (Gemini-image / similar) → returns a small PNG.
2. The Den's `PixelRoom` becomes data-driven (a list of placed items); generated
   furniture is pixelated to match and dropped into the room.
3. An in-app **room editor**: add/move/remove items, themes, "workspace" zone.

**Status:** the room renderer (`PixelRoom`) and the persona/endpoint pattern are
in place; the gating piece is wiring a real **image-gen provider** (and it can't
be exercised without one). This is the next build once an image model is chosen.
