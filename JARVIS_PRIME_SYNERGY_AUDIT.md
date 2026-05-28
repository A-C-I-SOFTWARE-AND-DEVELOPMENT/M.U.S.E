# JARVIS Prime ⇄ OpenHuman — End-to-End Synergy Audit

**Date:** 2026-05-28 · **Owner:** Jeremiah Echerd (echerd27) · **Org:** A-C-I Software & Development
**Scope:** Audit `hermes-agent` (Jarvis Prime) and `openhuman` end-to-end; plan and begin a
license-clean synergy that enhances Jarvis. **Personal use, open-source, org credit preserved.**

---

## 1. TL;DR

- **Jarvis already exists and is serious.** Jarvis Prime is the apex persona of `hermes-agent`:
  a local-first AI operating partner with six modes, a deterministic router, reasoning,
  epistemics, eight verification gates, owner-authorization gates, memory, persona, six-stream
  awareness, research, self-update proposals, a test suite, and an Android app.
- **The model plumbing is already world-class.** Hermes ships provider plugins for nearly every
  open-weight vendor and a mature worker/router/registry stack. The gap was **curation**, not
  connectivity.
- **OpenHuman is GPL-3.0 Rust/Tauri.** Copying its code into MIT/Python `hermes-agent` would be a
  license violation and a stack mismatch. Decision (owner-approved): **clean-room reimplement the
  valuable *concepts* in Python, keep Jarvis MIT, credit OpenHuman + tinyhumans.ai.**
- **Delivered in this PR (#1):** the **OSS Model Brain** — a cross-referenced, refreshable catalog
  of the best open-weight models per task, wired into Jarvis's CLI and resolved against installed
  providers. **Next (PR #2):** voice + avatar embodiment (clean-room from OpenHuman's local
  Whisper/TTS/voice concepts) + Jarvis branding pass.

---

## 2. Method

Read-only audit of both checked-out repos, plus live web research cross-referenced across five
independent benchmark/landscape sources (see the catalog doc). No code was copied between repos.
All claims below are grounded in files actually present in the trees on 2026-05-28.

---

## 3. `hermes-agent` (Jarvis Prime) — what's there

**Identity.** MIT (© Nous Research). A self-improving agent that runs on any model and bridges
many messaging surfaces. Jarvis Prime is its owner-facing apex persona.

**Jarvis Prime subsystem** (`hermes_cli/jarvis_prime/`):

| Module | Role |
|---|---|
| `runtime.py` | Orchestrator: perceive → classify → route → gate → handoff |
| `modes.py` | Six modes (Companion/Strategy/Critic/Operator/Builder/Mobile Voice) + classifier |
| `router.py` | Deterministic intent → `RouteDecision` (council/specialist/skill/builder/…) |
| `reasoning.py` | Deduction + induction with confidence + research escalation |
| `epistemics.py` | `audit_response` — challenges weak/unsupported answers |
| `gates.py` | Eight verification gates (Planning…Rollback) |
| `owner_auth.py` | Owner-gated actions require the exact phrase `Yes, with authorization.` |
| `memory.py` | Durable/session memory with secret rejection |
| `awareness.py` | Six-stream live perception snapshot |
| `persona.py` | Voice/identity system-prompt builder |
| `research.py` / `social_research.py` | Research brief scaffolding |
| `self_update.py` | Self-improvement *proposals* (human-gated; no auto-exec) |
| `model_brain.py` | **NEW** — bridge to the OSS Model Brain (this PR) |

**Model infrastructure** (already present): `model_registry.py` (worker registry, YAML-backed),
`model_router.py`, `model_catalog.py` (remote refreshable manifest), `providers/` +
`plugins/model-providers/` covering `deepseek`, `zai`/GLM, `kimi-coding`, `minimax`, `qwen-oauth`,
`huggingface`, `novita`, `nvidia`/NIM, `openrouter`, `ollama-cloud`, and more.

**Strengths.** Disciplined separation of transport/worker/model layers; deterministic routing;
owner + verification gates baked in; honest "challenge weak ideas" persona; strong test culture.

**Gaps this work addresses.**
1. *No curated OSS-model intelligence.* Connectivity existed; "which open model for which task,
   with evidence" did not. → **OSS Model Brain (this PR).**
2. *Local-first inference + voice embodiment is thin* vs. OpenHuman's. → **PR #2.**

---

## 4. `openhuman` — what's there

**Identity.** GPL-3.0. A fork of tinyhumans.ai's "OpenHuman" — *"your Personal AI super
intelligence. Private, Simple and extremely powerful."* Stack: **Rust core** (`src/openhuman/**`)
+ **Tauri desktop app** (`app/src-tauri`, React/TS frontend), Remotion video, multi-language docs.

**The transferable gold (local-AI + voice stack, Rust):**

| Area | Files |
|---|---|
| Local model admin | `src/openhuman/inference/local/service/ollama_admin.rs`, `inference/local/**` |
| Whisper STT install/transcribe | `inference/local/install_whisper.rs`, `inference/voice/{local,cloud}_transcribe.rs` |
| Streaming voice + speech | `inference/voice/{streaming,local_speech,postprocess,hallucination}.rs` |
| Audio capture / voice server | `voice/{audio_capture,server,factory,types,schemas,ops}.rs` |
| Local-AI config schema | `config/schema/local_ai.rs`, `config/schema/voice_server.rs` |
| Integrations | `integrations/twilio.rs`, `composio/providers/**` (gmail/slack/notion) |

**Why not copy it.** (a) **License:** GPL-3.0 copyleft vs. hermes-agent MIT — copying would force
Jarvis to GPL or violate the license. (b) **Stack:** Rust/Tauri vs. Python/Kotlin — not portable
as code. The *architecture* (local Ollama admin, Whisper install + local/cloud transcribe,
streaming TTS, on-device-first config) is what's worth carrying over — cleanly reimplemented.

---

## 5. The synergy decision

> **Clean-room reimplement** OpenHuman's valuable concepts in Python, keep `hermes-agent` MIT,
> and credit OpenHuman + tinyhumans.ai in docs. (Owner-selected 2026-05-28.)

This honors the stated constraints — *stay open source, give org/company credit* — without the
license violation that "copy all the direct code" would have caused. The local-first emphasis is
attributed to OpenHuman wherever it is borrowed.

---

## 6. Delivered in PR #1 — the OSS Model Brain

- `docs/ai-intelligence/oss-model-catalog.yaml` — canonical, cross-referenced, refreshable catalog
  (12 model families across frontier / strong / local tiers; per-task routing).
- `hermes_cli/oss_model_brain.py` — stdlib-first loader + recommender (PyYAML optional; built-in
  fallback; license / local-only / installed-provider filtering; provider resolution).
- `hermes_cli/jarvis_prime/model_brain.py` — lazy bridge keeping `jarvis_prime` stdlib-only at import.
- `python -m hermes_cli.jarvis_prime models <task>` — CLI surface (`--local`, `--license`,
  `--all-providers`, `--json`, `tasks`).
- `docs/ai-intelligence/oss-model-catalog.md` — the validated research write-up + sources + credits.
- `tests/test_oss_model_brain.py` — 17 hermetic tests (all green; existing Jarvis CLI tests still green).

**Validated landscape (2026-05):** DeepSeek-V4 (MIT, ~80.6% SWE-bench), GLM-5 (MIT, agentic/bug-fix),
Kimi-K2 (HumanEval ~99%), MiniMax-M2 (~80.2%), Qwen3-Coder (Apache, local-friendly); reasoning:
DeepSeek-R1 (MATH-500 97.3%) + R1-Distill-8B (local), Qwen3-235B, GPT-OSS-120B/20B.

---

## 7. Honest non-goals / reframes

- **No "super-intelligence" claim.** This is a real, measured capability upgrade — not magic.
- **No auto-merge.** PRs open as **drafts** for owner review; Jarvis's own design already gates
  main-branch merges behind owner authorization.
- **Security/owner gates kept.** "Ignore security" was reframed: no vulnerabilities introduced and
  no gates stripped — those gates are core to Jarvis's quality.
- **Recommendation, not silent control.** The brain advises model choice; switching the live model
  still flows through `/model` + owner gates.

---

## 8. Roadmap

- **PR #1 (this):** OSS Model Brain. ✅
- **PR #2 (next, this session):** Voice + avatar embodiment — clean-room Python for local Whisper
  STT + TTS config and a Jarvis avatar/branding pass, wired into the Android Jarvis Prime screens.
- **Later:** a local `ollama` provider plugin (local-first inference), and feeding `ai_radar.py`
  findings into a scheduled catalog-refresh proposal (human-gated promotion).
