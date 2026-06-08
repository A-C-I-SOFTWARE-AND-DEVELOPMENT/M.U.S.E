# Gemma 4 in Hermes / MUSE

Gemma 4 is wired into Hermes as a first-class **local / open-weight model
family** (Google DeepMind, Apache-2.0). It makes MUSE more useful offline and
on mobile **without** weakening safety, memory integrity, routing quality, or
owner control.

This page is the operator guide: what Gemma is used for, what it is *not*
allowed to do, which lanes it improves immediately vs which are scorecard-gated,
how to install/inspect it, how auto-learning promotes it, and how to roll back.

## What Gemma 4 is used for

Gemma leads these MUSE lanes **immediately** (no scorecards required), because
the local lanes are local-first by policy:

| Lane | Why Gemma |
|---|---|
| `local_reasoning` | Offline reasoning on laptop→server hardware |
| `mobile_chat` | Low-latency on-device chat |
| `voice_reply` | Fast E2B/E4B replies for voice |
| `memory_curator` | Cleaner memory proposals (see below) |
| `summarization` | Local summaries, no API spend |
| `multimodal_doc` | Document / OCR workflows |

Variants (configured in `config/model-catalog.yaml` and the OSS brain):

| Variant | Ollama tag | Tiers | Role |
|---|---|---|---|
| `gemma4-e2b` | `gemma4:e2b` | laptop→server | **fast-daily default** — mobile / voice / summarize / memory |
| `gemma4-e4b` | `gemma4:e4b` | laptop→server | **reasoning / coding default** — *load-gated, falls back to E2B* |
| `gemma4-26b-a4b` | `gemma4:26b` | workstation/server | reasoning / review fallback — **never an auto local default** |
| `gemma4-31b` | `gemma4:31b` | workstation/server | deep reasoning / review fallback — **never an auto local default** |

### Local routing by job weight

Local Gemma lanes are routed by job weight, not one blanket default
(`hermes_cli/jarvis_prime/task_router.py`, `model_bootstrap.compute_local_defaults`):

- **Fast daily** (`mobile_chat`, `voice_reply`, `summarization`, `memory_curator`)
  → **E2B** — low latency, low footprint (`TaskProfile.local_purpose="local_fast"`).
- **Coding / planning / deeper reasoning** (`coding_*`, `test_debug`) → **E4B**,
  **only if it loads cleanly**. The opt-in smoke check
  (`muse models gemma smoke --variant gemma4-e4b`) persists the result to
  `gemma_load_status.json`; if E4B is on record as *failed* (e.g. OOM on an 8 GB
  box) the router automatically demotes those lanes to **E2B**. A fresh/unprobed
  install still prefers E4B — only a *demonstrated* failure downgrades it.
- **Large autonomous research** (`research`, `citation_verification`) routes
  **off-local** — to a hosted/worker/paid endpoint first (the small Gemma
  variants are too small, and 26B/31B don't fit an 8 GB box); `local_oss` is only
  a last-ditch fallback (`local_first=False`).
- **26B / 31B are never an auto local default** — they are sunk to the tail of
  the local candidate list and reached only through a measured, scorecard-gated
  promotion.

The Gemma preference is a *prior*: measured scorecards still move any lane
(`model_scorecard.promotion_eligible`), so a better-measured local coder can
overtake E4B for coding through an owner-visible promotion.

> One-shot setup for a local-only 8 GB box: `scripts/setup-local-gemma-8gb.sh`
> (pulls E2B+E4B, runs bootstrap + the E4B smoke gate, pins the lanes).

> **12B** is represented as a **model-card variant only** in the OSS model brain
> (`docs/ai-intelligence/oss-model-catalog.yaml`). It has no confirmed Ollama tag,
> so it is intentionally *not* an `ollama-local` default or an open-weight
> download candidate. Verify the exact local build/card before relying on any
> tag or context window — published sizes/context here are conservative floors.

## What Gemma 4 is **not** allowed to do

- It does **not** bypass owner gates (spend/deploy/publish/etc.).
- It does **not** write durable memory directly — every curator suggestion is
  **SESSION / PROPOSED** and low-trust (`SourceTrust.COMMUNITY`, confidence
  capped at 0.45, below the 0.6 durable floor). The owner promotes.
- It does **not** resolve memory contradictions — it can only *flag* a candidate.
- It does **not** replace **Claude Code** as the primary builder or **Codex** as
  the primary reviewer by default. Those lanes (`coding_build`, `coding_review`)
  keep their worker defaults via `TASK_PROFILES[...].preferred_tiers`.
- It does **not** self-promote routing on vendor benchmarks — only measured
  scorecards can move a route, and only through an owner-visible proposal.
- Its **thinking / scratchpad blocks are stripped** before anything reaches
  memory extraction, the Memory Tree, session persistence, logs, or scorecards
  (`gemma_memory_curator.strip_gemma_thought_blocks`).

## Scorecard-gated lanes (Gemma is a fallback until proven)

`coding_plan`, `coding_build`, `coding_review`, `test_debug`, `research`,
`citation_verification`, `deep_research` — Gemma is a fallback. It can overtake
the incumbent default for one of these lanes only when measured scorecards meet
**all** gates (`model_scorecard.promotion_eligible`):

- ≥ 20 samples for the task class (configurable),
- mean task-class score ≥ baseline + 0.05,
- hallucination corrections ≤ baseline, owner corrections ≤ baseline,
- tool reliability ≥ 0.98 on tool-use lanes,
- citation accuracy ≥ baseline on research/citation lanes,
- memory usefulness ≥ baseline on the memory lane,
- latency within the lane budget.

The baseline is the best measured model of a **different family** — i.e. the
incumbent Gemma would actually overtake.

## Memory curation (owner-gated)

The Gemma memory curator (`hermes_cli/jarvis_prime/gemma_memory_curator.py`)
runs after a turn (on by default, but **inert until a runner is configured or
auto-detected** — see "Making the curator actually run" below; disable the lane
with `HERMES_JARVIS_GEMMA_CURATOR=0`). It
proposes `{title, summary, namespace, tags, contradiction_candidate,
freshness_due, source_note, confidence}` — all written through the same
`capture_to_tree` path as deterministic capture, so the secret /
chain-of-thought / sensitivity write policy applies. Unapproved proposals are
excluded from live recall (`include_pending=False`); after
`set_approval(..., OWNER_APPROVED)` they become recall-eligible.

Deterministic capture remains the safety baseline — Gemma only *enhances* it.

### Making the curator actually run

The curator ships wired but **off by default** (no runner). To make it run a
local Gemma:

1. Install Ollama and a Gemma model (see below), e.g. `ollama pull gemma4:e4b`.
2. Opt in: `HERMES_JARVIS_GEMMA_AUTO_RUNNER=1`.

On first use the runtime then auto-detects Ollama + the best installed Gemma tag
(prefers `e4b`, then `e2b`) and builds the `(prompt) -> completion` runner
(`hermes_cli/jarvis_prime/gemma_runner.py`, which pipes the prompt to
`ollama run <tag>`). With no flag, no Ollama, or no Gemma model installed it
stays a no-op — byte-identical to before. An explicit `JarvisConfig.gemma_runner`
(or an injected `gemma_runner_factory`) always wins.

## Install locally (Ollama)

```bash
# Install Ollama: https://ollama.com
ollama pull gemma4:e4b          # laptop/desktop default
ollama pull gemma4:e2b          # mobile/voice
# workstation/server:
ollama pull gemma4:26b
ollama pull gemma4:31b
```

Hermes never downloads weights on a normal install. `muse models bootstrap`
plans downloads but pulls only with explicit consent (`--force`, not `--no-pull`,
not `--dry-run`).

## Inspect / operate

```bash
muse models gemma status         # configured / installed / promoted matrix
muse models gemma doctor         # wiring + safety doctor
muse models gemma recommend --tier laptop
muse models gemma smoke --variant gemma4-e4b   # opt-in; needs Ollama
muse models gemma scorecards     # measured Gemma scorecards
muse models gemma promote --task-class memory_curator --dry-run
```

The same commands are available via the module CLI:
`python -m hermes_cli.jarvis_prime gemma <subcommand>`.

Availability is reported with distinct states: **configured** (in catalog) /
**installed** (`ollama list`) / **smoke-tested** (a completion succeeded) /
**promoted** (scorecards moved a route). Missing Gemma is always a **warning**,
never a launch blocker.

## Auto-learning: promote / demote

1. MUSE records per-turn scorecards for Gemma-backed turns
   (`JarvisPrime.record_route_outcome`, evidence-only — unknown values stay
   unknown, never fabricated).
2. When the gates above are met, `muse models gemma promote --task-class <t>`
   produces an **owner-visible** `routing_rule_update` proposal (queued in
   `~/.hermes/jarvis_prime/proposals.jsonl`) with the sample count, mean-score
   delta, latency delta, correction/hallucination deltas, and a rollback plan.
3. The owner approves/rejects via
   `python -m hermes_cli.jarvis_prime proposals list / approve / reject`.
   **Nothing auto-applies.**

## Roll back Gemma route changes

- **A promotion** is a pinned owner override: clear it with
  `task_router.set_task_override('<task_class>', None)` (atomic, owner-gated).
- **The curator**: set `HERMES_JARVIS_GEMMA_CURATOR=0` (or leave `gemma_runner`
  unset — it is inert without one).
- **The catalog default**: `ollama-local/llama3.2` remains a fallback in both the
  `local` and `fast` tiers, so removing the Gemma defaults reverts cleanly.
- **Memory layers**: `HERMES_MEMORY_LAYERS=0` reverts to legacy recollection.

## Where it lives

- Catalog: `config/model-catalog.yaml` (`ollama-local` models + `open_weight_candidates`)
- OSS brain: `docs/ai-intelligence/oss-model-catalog.yaml` + `hermes_cli/oss_model_brain.py`
- Routing: `hermes_cli/jarvis_prime/task_router.py`, `model_bootstrap.py`
- Promotion: `hermes_cli/jarvis_prime/model_scorecard.py`
- Memory curator: `hermes_cli/jarvis_prime/gemma_memory_curator.py`
- Runtime: `hermes_cli/jarvis_prime/runtime.py`
- CLI / doctor: `hermes_cli/jarvis_prime/gemma_cli.py`, `gemma_doctor.py`
  (thin hook in `hermes_cli/main.py`)
- Tests: `tests/test_gemma4_*.py`
