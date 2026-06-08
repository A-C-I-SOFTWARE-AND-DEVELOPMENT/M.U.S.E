# MUSE — Open-Source Model Brain

> The open-weight models MUSE can **learn from** and **route work
> to**, cross-referenced against public benchmarks and kept refreshable.

This is the narrative companion to
[`oss-model-catalog.yaml`](./oss-model-catalog.yaml) (the machine-readable
source of truth) and the loader at
[`hermes_cli/oss_model_brain.py`](../../hermes_cli/oss_model_brain.py).

**Snapshot date:** 2026-05-28. Scores move fast — treat everything here as
a *validated snapshot*, not a permanent ranking.

> The `gemma4` family (Google DeepMind, Apache-2.0, local) leads the local /
> memory / mobile / voice / summary / multimodal lanes and is a scorecard-gated
> fallback for coding/review/research. See
> [`gemma4-integration.md`](./gemma4-integration.md).

---

## Why this exists

Hermes already runs on top of *any* model and already ships provider
plugins for essentially every major open-weight vendor (`deepseek`,
`zai`/GLM, `kimi-coding`, `minimax`, `qwen-oauth`, `huggingface`,
`novita`, `nvidia`/NIM, `openrouter`, `ollama-cloud`, …). What it lacked
was a **curated, benchmark-backed answer to "which open model is best for
*this kind of task*, and how do I reach it?"**

Three layers, kept separate on purpose:

| Layer | Question it answers | Where it lives |
|---|---|---|
| **Transport** | How do I physically call a provider's API? | `providers/`, `plugins/model-providers/<name>/` |
| **Worker** | Which *agent* executes the task? | `model-registry.yaml` → `model_router.py` |
| **OSS model brain** | Which *open model* should that agent run? | `oss-model-catalog.yaml` → `oss_model_brain.py` |

The brain maps a **task category** → an ordered list of model *families* →
a concrete `(provider, model)` pair resolved against the providers you
actually have installed.

---

## How MUSE uses it

```text
# best open coders for general coding, on this host
python -m hermes_cli.jarvis_prime models coding

# only models you can run locally (privacy / offline)
python -m hermes_cli.jarvis_prime models local_reasoning --local

# only permissively licensed (e.g. for redistribution)
python -m hermes_cli.jarvis_prime models bug_fix --license MIT

# every reachable option, ignoring what's installed
python -m hermes_cli.jarvis_prime models agentic_coding --all-providers

# list the task categories
python -m hermes_cli.jarvis_prime models tasks
```

`--json` emits the structured payload (including the resolved provider)
for the Android app, skills, or the orchestrator to consume.

It is **recommendation only**: choosing the live inference model still
goes through the existing `/model` machinery and owner gates. The brain
informs the choice; it never silently switches your model.

---

## The validated landscape (2026-05)

Scores are the best cross-referenced public numbers as of the snapshot
date; "—" means not consistently reported. SWE = SWE-bench Verified,
LCB = LiveCodeBench, HE = HumanEval, AIME = AIME 2025, M500 = MATH-500.

### Frontier coding / agentic

| Family | Vendor | License | Params | Ctx | SWE | LCB | Notes |
|---|---|---|---|---|---|---|---|
| **deepseek-v4** | DeepSeek | MIT | ~1.6T/49B MoE | 1M | **80.6** | 93.5 | Top open SWE-bench; 1M context |
| **glm-5** | Z.ai (Zhipu) | MIT | ~744B/40B MoE | 200K | 77.8 | 84.9 | Best real-bug fixer + agentic/terminal |
| **kimi-k2** | Moonshot | MIT* | ~1T/32B MoE | 256K | 76.8 | 89.6 | HE ~99; strong thinking variant |
| **minimax-m2** | MiniMax | Apache-2.0 | ~230B/10B MoE | 1M | 80.2 | — | Frontier SWE at small active params |
| **qwen3-coder** | Alibaba | Apache-2.0 | ~80B/3B MoE | 256K | 71.3 | — | Best permissive coder; workstation-runnable |

### Local-first coding (run on your own hardware)

| Family | Vendor | License | Params | Ctx | SWE | Runner |
|---|---|---|---|---|---|---|
| **qwen3-27b** | Alibaba | Apache-2.0 | 27B dense | 262K | 77.2 | Ollama / vLLM |
| **devstral-small** | Mistral | Apache-2.0 | 24B dense | 128K | 68.0 | Ollama / llama.cpp |
| **qwen3-coder** | Alibaba | Apache-2.0 | ~80B/3B MoE | 256K | 71.3 | vLLM |
| **gpt-oss-20b** | OpenAI (OW) | Apache-2.0 | 21B/3.6B MoE | 131K | — | Ollama (16GB RAM) |

### Reasoning / math

| Family | Vendor | License | Params | AIME | M500 | Notes |
|---|---|---|---|---|---|---|
| **deepseek-r1** | DeepSeek | MIT | ~671B/37B MoE | — | **97.3** | Reference open reasoner |
| **qwen3-235b** | Alibaba | Apache-2.0 | 235B/22B MoE | 89.2 | — | Top permissive reasoning+math |
| **gpt-oss-120b** | OpenAI (OW) | Apache-2.0 | 117B/5.1B MoE | — | — | ~o4-mini; 20B local sibling |
| **deepseek-r1-distill-8b** | DeepSeek | MIT | 8B dense | 87.5 | — | Best *local* reasoner |

\* Kimi K2 ships under a modified-MIT license; treat as MIT-compatible for
internal use, but read the license before redistribution.

### Default routing

```text
coding          → deepseek-v4, glm-5, kimi-k2, minimax-m2, qwen3-coder
agentic_coding  → glm-5, deepseek-v4, kimi-k2, minimax-m2, qwen3-coder
bug_fix         → glm-5, deepseek-v4, kimi-k2, qwen3-coder, devstral-small
code_edit       → qwen3-coder, kimi-k2, glm-5, devstral-small, deepseek-v4
reasoning       → deepseek-r1, qwen3-235b, glm-5, gpt-oss-120b, deepseek-v4
math            → deepseek-r1, qwen3-235b, deepseek-r1-distill-8b
local_coding    → qwen3-coder, qwen3-27b, devstral-small, gpt-oss-20b
local_reasoning → deepseek-r1-distill-8b, gpt-oss-20b, qwen3-27b
```

---

## Keeping it current

The frontier moves monthly (GLM-4.7 → 5 → 5.1; Kimi K2 → K2.5 → K2.6;
Qwen 3.5 → 3.6 → 3.7; DeepSeek V3.2 → V4). The catalog is built to absorb
that without code changes:

1. Re-run the research (or feed findings through
   [`hermes_cli/ai_radar.py`](../../hermes_cli/ai_radar.py), which already
   tracks the agent/model landscape and emits *recommendations only*).
2. Update each family's `current_variant`, `benchmarks`, `providers`, and
   the top-level `updated_at` + `sources` in `oss-model-catalog.yaml`.
3. Keep the built-in fallback in `oss_model_brain.py` and the YAML routing
   in sync — `tests/test_oss_model_brain.py` asserts they cover the same
   task set and that every routed id resolves to a real family.

Promotion stays **human-gated**, consistent with the rest of Hermes
routing policy. The brain proposes; the owner disposes.

---

## Sources (validated 2026-05-28)

- SWE-bench Verified leaderboard — https://llm-stats.com/benchmarks/swe-bench-verified
- Best open-source/open-weight coding models (2026) — https://kilo.ai/open-source-models
- Top open-source reasoning models (2026) — https://www.clarifai.com/blog/top-10-open-source-reasoning-models-in-2026
- Best open-source LLMs 2026 (license/benchmark survey) — https://huggingface.co/blog/daya-shankar/open-source-llms
- SWE-bench Verified (48+ model scores) — https://benchlm.ai/benchmarks/sweVerified

---

## Local bootstrap layer (`hermes_cli/local_models/`)

The brain above answers *which* open model to prefer. The
`hermes_cli/local_models/` package added in Phase 6 answers *how to actually run one
locally* — without bloating a normal install:

| Module | Role |
|---|---|
| `hardware_probe.py` | stdlib-only, Termux-safe detection of CPU/RAM/VRAM/OS/disk → hardware **tier** |
| `server_adapters.py` | launch-plan builders for Ollama / llama.cpp / vLLM / SGLang / OpenAI-compatible (never executes) |
| `catalog.py` | loads the `open_weight_candidates:` section of `config/model-catalog.yaml` (license, runtime, RAM/VRAM, lanes, `verify`) |
| `bootstrap.py` | tiered plan; downloads **only** with `--accept-downloads` |
| `scorecards.py` | record outcomes; `select_model()` ranks by composite, not hype |

```bash
hermes models bootstrap --tier laptop                 # plan only, zero downloads
hermes models bootstrap --tier workstation --accept-downloads   # explicit consent
```

See [`oss-model-catalog.md` companion → operating guide](./model-routing-policy.md)
for how scorecards feed routing. The candidate list, its license fields, and
checksum/source-verification guidance live in `config/model-catalog.yaml` under
`open_weight_candidates:`. **Nothing is downloaded on a normal install.**

---

## Credits

The **local-first** emphasis of this brain — that a capable assistant
should be able to run real models on the owner's own hardware — is
inspired by **OpenHuman** (https://github.com/tinyhumansai/openhuman, by
the tinyhumans.ai team, GPL-3.0). This catalog, loader, and CLI are
original work and remain under hermes-agent's MIT license; **no OpenHuman
code was copied** (it is GPL-3.0 and a different stack — Rust/Tauri).
Concept credit to the OpenHuman authors.
