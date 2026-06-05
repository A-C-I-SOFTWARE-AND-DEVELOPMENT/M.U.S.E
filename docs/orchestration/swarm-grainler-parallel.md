# Swarm Grainler Parallel

> Every code-producing task can run as a **swarm**: a goal is decomposed into
> **grains** that each own a *provably disjoint file-domain*, each grain becomes
> its own **specialized LLM** (own model lane, toolset, iteration budget,
> token-juice context pack, and a dedicated JARVIS Memory Tree namespace), and
> the grains run **in parallel** in isolated git worktrees so they never overlap
> on each other's work. Every step is dated, traceable, and recorded in a
> Decision Ledger, and a self-update loop auto-applies the safe/reversible
> learnings.

This is an **additive** layer that *composes* existing Hermes primitives. It
does not replace `/orchestrate`; it gives code tasks a single canonical,
auditable, collision-free pipeline. Code lives in
[`hermes_cli/swarm/`](../../hermes_cli/swarm/).

## The five moves

```
decompose (Grainler)            → proven-disjoint SwarmPlan          grainler.partition
  → claim each grain's domain   → runtime non-overlap backstop       specialist.claim_grain
  → build specialized agents    → token-juice + dedicated memory     specialist.build_grain_agent_spec
  → run in parallel             → ParallelRunner + git worktrees     coordinator.PromptOnlyExecutor
  → record + learn              → Decision Ledger + self-update       coordinator.run_swarm
```

## Vocabulary

| Term | What it is | Code |
|---|---|---|
| **Grain** | A bounded unit of code work owning a disjoint file-domain, with intent, risk class, owner-gates, verification, rollback, and a model lane. | `grain.Grain` |
| **FileDomain** | The set of path globs a grain may write. | `grain.FileDomain` |
| **Grainler** | The partitioner: decomposes a goal into grains and **proves their domains pairwise disjoint** before anything runs. | `grainler.partition` |
| **SwarmPlan** | The proven-disjoint set of grains for a job. | `grain.SwarmPlan` |
| **Swarm Blackboard** | Append-only, dated coordination/audit trace in memory namespace `swarm/<job>`. | `coordinator._record_blackboard` |

## The non-overlap guarantee (three layers)

Defense-in-depth, because git worktrees alone *cannot warn when two worktrees
modify the same file on different branches*:

1. **Static — `SwarmPlan.prove_disjoint()`.** Conservative glob-intersection:
   two domains are declared disjoint only when no concrete path could match a
   glob in both. Any uncertainty is reported as an overlap, and the plan is
   rejected **before a single agent starts** (zero workers run). See
   `grain.globs_overlap`.
2. **Physical — git worktree + branch per grain.** Each grain runs on
   `hermes/<job>/<grain-id>` in its own checkout (reuses
   [`worktrees.py`](../../hermes_cli/worktrees.py) /
   [`workers/isolation.py`](../../hermes_cli/workers/isolation.py)).
3. **Dynamic — lease claims.** Each grain acquires a `worker_lease` claim over
   its file-domain; a second *active* claim that overlaps is rejected
   (`specialist.DomainClaimError`). This catches runtime drift (e.g. a second
   concurrent swarm on the same checkout) the static check could not foresee.
   Merge-time `FileConflict` detection ([`merge_engine.py`](../../hermes_cli/merge_engine.py))
   is the final backstop.

## Each grain is its own specialized LLM

`specialist.build_grain_agent_spec` bundles, per grain:

- a **token-juice** context pack (`TokenJuiceCompiler`) scoped to the grain's
  mission, its *private* memory namespace, and the shared swarm blackboard —
  priority-ordered, budget-bounded, provenance-tagged, secret-screened;
- its **own** model lane, restricted toolset, and `IterationBudget`;
- a **dedicated Memory Tree namespace** (`swarm/grain/<id>`) so grains never
  cross-write memory.

`specialist.spawn_agent` lazily instantiates the specialized `AIAgent` from that
spec (model lane + toolset + budget + token-juice context as the system prompt).
The default `PromptOnlyExecutor` instead *materialises* the spec into each
grain's worktree (`GRAIN_PROMPT.md` + `GRAIN_CONTEXT.md`) without launching a
model — the safe, deterministic "decides, does not act" default.

## Audit, traceability, dating

Every grain emits a dated `status.json` (ISO-8601 `created_at` / `started_at` /
`ended_at`), append-only logs, and a usage/cost sidecar. The coordinator writes
one **15-section Decision Ledger** per job
(`$HERMES_HOME/decisions/<job>/NNNN-*.md`, sequence-numbered + timestamped),
and the Swarm Blackboard memory namespace gives a single queryable, dated trace
that the GraphRAG indexers already understand.

## Self-update loop — auto-apply reversible

At job end the coordinator builds self-update `Proposal`s from the outcome and
routes each through `self_improvement.promotion_decision`:

- **apply** (auto, no gate) — additive, reversible, low-blast-radius changes
  (tag-only edits, ≤1-notch routing nudges carrying rollback metadata). Applied
  via an injectable `apply_fn` (default: record-only, undone by deleting the
  record) and logged with its rollback recipe.
- **promote** (owner-gated) — prompt edits, new/removed skills, risk
  reclassification: queued for the owner's exact `"Yes, with authorization."`.
- **defer** — single-event/weak-evidence findings wait for the K=3 rule.

## Cost discipline

A **trivial** (single-grain) plan runs inline with no swarm fan-out, honouring
the multi-agent token lesson (don't pay 15× to fix a typo). Token budgets are
bounded per grain by TokenJuice. As the system learns (skills + knowledge
graph), repeated work amortizes the parallelism cost.

## Usage

```bash
# Decompose + isolate + ledger (PROMPT_ONLY, launches no model, pushes nothing):
python -m hermes_cli.swarm "build the api and the web layer separately" \
    --repo . --grains grains.json

# grains.json:
# [{"intent":"api endpoints","globs":["src/api/**"],"model_lane":"claude"},
#  {"intent":"web ui","globs":["src/web/**"],"model_lane":"codex"}]
```

```python
from hermes_cli.swarm import run_swarm

result = run_swarm(
    "build api and web separately",
    repo=".",
    grains=[
        {"intent": "api endpoints", "globs": ["src/api/**"]},
        {"intent": "web ui", "globs": ["src/web/**"]},
    ],
)
print(result.ledger_path, [g.state for g in result.grains])
```

An overlapping decomposition raises `OverlapError` and runs **zero** grains.

## Validation

```bash
python -m pytest tests/hermes_cli/swarm/ -q
python -m hermes_cli.swarm "<small goal>" --repo /path/to/scratch/repo --grains grains.json
```

## Research basis

The design is grounded in 2025–2026 practice and literature:

- Orchestrator–worker with parallel, **non-coordinating** subagents and clear
  task boundaries — [Anthropic, *How we built our multi-agent research
  system*](https://www.anthropic.com/engineering/multi-agent-research-system)
  (also the ~15× token lesson → the trivial-plan cost gate).
- **Assign non-overlapping file domains up front**; worktrees can't warn on
  same-file edits — [Augment Code](https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution),
  [MindStudio](https://www.mindstudio.ai/blog/git-worktrees-parallel-ai-coding-agents).
- Prefer **test-based verification** over biased LLM-judges for convergence —
  [Multi-Agent Verification (arXiv 2502.20379)](https://arxiv.org/pdf/2502.20379),
  [AI21 on judge bias](https://www.ai21.com/blog/gold-like-answers-benchmarks/).
- **Benchmark-gated** self-improvement with a lineage archive —
  [Darwin-Gödel Machine (arXiv 2505.22954)](https://arxiv.org/abs/2505.22954),
  [SICA](https://www.emergentmind.com/topics/self-improving-coding-agent-sica).
- **Context engineering** (offload / reduce / retrieve / isolate) via
  TokenJuice + Memory Tree —
  [Anthropic, *Effective context engineering*](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).
- **Blackboard / stigmergy** coordination over brittle message-passing —
  [Blackboard MAS (arXiv 2507.01701)](https://arxiv.org/html/2507.01701v1).
