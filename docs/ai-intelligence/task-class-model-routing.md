# Task-class model routing — the symbiotic stack

> **Status:** additive upgrade (2026-06). The hosted-tier change is **on by
> default** and reversible at runtime (see [Rollback](#rollback)). Promotion
> still happens only through measured scorecards, never vendor benchmarks.

Hermes/muse does **not** pick one "best model." It runs a *symbiotic,
task-lane portfolio*: each task class routes to the family that is best for that
kind of work, free/local-first, with paid APIs explicit-opt-in only. Three
layers compose the decision (see [`task_router.py`](../../hermes_cli/jarvis_prime/task_router.py)):

1. **Policy** — the free/local-first route order + paid opt-in
   (`model_bootstrap.load_policy`).
2. **Catalog** — *which open model is best for task X*
   ([`oss-model-catalog.yaml`](oss-model-catalog.yaml) → `oss_model_brain`).
3. **Evidence** — measured per-(model, task) scorecards
   (`model_scorecard`), which re-rank everything and gate promotion.

Owner overrides and paid gating sit on top and always win.

## Who owns which lane

| Task class (`TaskClass`) | `catalog_task` lane | Portfolio (free/local-first → frontier) |
|---|---|---|
| `coding_build` | `agentic_coding` | GLM-5.1, DeepSeek-V4, Kimi-K2.6, MiniMax-M3, Qwen3-Coder |
| `coding_plan` | `reasoning` | DeepSeek-R1, Qwen3-235B, GLM-5.1 (+ workers) |
| `coding_review` | `coding_review` | GLM-5.1, DeepSeek-V4, Qwen3-Coder, Gemma (local fallback) |
| `test_debug` | `bug_fix` | GLM-5.1, DeepSeek-V4, Kimi-K2.6, Qwen3-Coder, Devstral |
| `research` | `deep_research` | DeepSeek-R1, Qwen3-235B, Gemma (last-ditch local) |
| `citation_verification` | `citation_verification` | DeepSeek-R1, Qwen3-235B, GLM-5.1, Gemma |
| `mobile_chat` / `voice_reply` / `summarization` / `memory_curator` | own lanes | Gemma (E2B fast / E4B reasoning), GPT-OSS-20B, R1-distill |

Worker lanes remain first-class: **Claude Code builds**, **Codex reviews / does
bounded fixes** (`worker_registry`). Per-class tier order
(`TaskProfile.preferred_tiers`) decides when a worker leads vs. a hosted/local
model. Multimodal (`multimodal`, `multimodal_doc`) routes to Qwen3-VL / Qwen3-Omni
with Gemma as the local fallback; retrieval (`embeddings`, `rerank`) routes to
Qwen3-Embedding / BGE-M3 / Qwen3-Reranker / BGE-reranker.

## Hosted-tier task-class routing (the upgrade)

Before: the hosted tier returned bare **provider ids** (`["openrouter"]`) — task-
blind. Now `_hosted_candidates` expands each *configured* hosted provider into
ordered `provider/model` candidates drawn from the catalog's per-task routing
(e.g. `coding_build` → `openrouter/z-ai/glm-5`, `research` →
`openrouter/deepseek/deepseek-r1`), filtered to providers you actually
configured. The order only feeds the router's intra-tier `seq` tiebreaker —
**scorecards and owner overrides still win, and no gate changes.**

Safe by construction:

- **Disabled** (see Rollback) → the legacy bare-provider-id list, byte-for-byte.
- **No catalog / no PyYAML / any error** → the bare provider list
  (`load_oss_catalog` never raises).
- **Never shrinks the set** — a configured provider the catalog didn't map for a
  lane is still appended as a tail fallback.

### Rollback

The behavior is **on by default**. To restore the legacy bare-provider hosted
candidate without a code change, set:

```bash
export HERMES_JARVIS_HOSTED_TASKCLASS=0   # also: false / no / off
```

The full revert is the patch itself (no migration, no state).

## The catalog: four sync points

The catalog is intentionally data-driven. When you add/rename a **routing lane**
or **family**, update **all four** or a test will fail:

1. [`docs/ai-intelligence/oss-model-catalog.yaml`](oss-model-catalog.yaml) — the shipped catalog (`families` + `routing`).
2. [`hermes_cli/oss_model_brain.py`](../../hermes_cli/oss_model_brain.py) — `_BUILTIN_FAMILIES` + `_BUILTIN_ROUTING` (the no-PyYAML fallback; the parity test asserts `set(yaml.tasks()) == set(builtin.tasks())`).
3. [`hermes_cli/jarvis_prime/model_brain.py`](../../hermes_cli/jarvis_prime/model_brain.py) — `KNOWN_TASKS` (the bridge test asserts every known task recommends ≥1 model).
4. Tests — `tests/test_oss_model_brain.py`, `tests/test_gemma4_catalog.py`.

### Adding a provider model safely (no fake certainty)

- The `provider` in a family's `providers:` list **must** match a folder under
  [`plugins/model-providers/`](../../plugins/model-providers/). Don't invent providers.
- A **family id is stable**; bump `current_variant` (and `benchmarks`/`why`/
  `sources`) as the frontier moves — don't rename the id (it breaks routing/parity).
- If a just-released variant's exact provider model id is **unverified**, mark it
  `candidate` (catalog `notes` / config `tags: [..., candidate, unverified]`) and
  keep one known-good provider ref. Verify against the provider's live model list
  before relying on it for paid routing.
- Benchmarks are **vendor/aggregator snapshots, not contracts** — they're priors
  only. Scorecards promote.

## Scorecards promote; benchmarks don't

A model overtakes a lane's default only when **every** gate in
`model_scorecard.promotion_eligible` holds: ≥ `min_samples`; mean task-class
score ≥ baseline + `min_mean_delta`; no worse hallucination/owner corrections;
tool reliability ≥ 0.98 on tool lanes; citation accuracy ≥ baseline on citation
lanes; memory usefulness ≥ baseline on the memory lane; latency within the lane
budget. Baseline is the best measured incumbent **of a different family**.

### Seed scorecards / run an A/B before changing a default

```python
from hermes_cli.jarvis_prime.model_scorecard import (
    ModelScorecard, ScorecardBook, promotion_eligible,
)

book = ScorecardBook.load()                 # ~/.hermes/jarvis_prime/model_scorecards.jsonl
# Record one real, validated outcome per run for the candidate AND the incumbent:
book.record(ModelScorecard(
    model="openrouter/z-ai/glm-5", provider="openrouter", task_type="coding_build",
    risk_class="RC3", tests_passed=19, tests_failed=1, accepted_diff_rate=0.95,
    tool_reliability=0.99,
))
# After ≥20 paired samples, check eligibility (advisory; the route auto-uses
# measured scores regardless):
print(promotion_eligible(book, task_class="coding_build",
                         candidate="openrouter/z-ai/glm-5").rationale())
```

Inspect routes any time:

```bash
python -m hermes_cli.jarvis_prime route --task coding_build      # default (ON)
HERMES_JARVIS_HOSTED_TASKCLASS=0 python -m hermes_cli.jarvis_prime route --task research
python -m hermes_cli.jarvis_prime models coding                  # catalog recommendation
```

## Context handoff — no whole-repo stuffing

Coding models get a **structured context packet**, not a repo dump. The
`context` subcommand / `context_handoff.build_context_handoff` assembles —
locally, network-free — an architecture summary, the relevant files, their
tests, the GraphRAG nodes, prior decisions/ledger entries, the recommended model
lane (via `route_for_task`, so owner gates/paid opt-in are respected), and a
verification plan. It degrades gracefully when the graph isn't built and screens
secrets from the echoed request (`secrets_policy.redact`).

```bash
python -m hermes_cli.jarvis_prime context "add a retry to the gateway" --json
python -m hermes_cli.jarvis_prime context "fix flaky upload test" --build   # index first
```

This is the cheap-context path GraphRAG/TokenJuice were built for: bounded,
inspectable, source-backed context instead of paying to stuff the whole repo
into every prompt.

## See also

- [`model-routing-task-classes.md`](model-routing-task-classes.md) — task-class profiles + risk classes.
- [`model-routing-policy.md`](model-routing-policy.md) — tier order, paid gating.
- [`oss-model-catalog.md`](oss-model-catalog.md) — the OSS model brain overview.
- [`JARVIS_MODEL_ROUTER_SCORECARD.md`](JARVIS_MODEL_ROUTER_SCORECARD.md) — scorecard dimensions.
