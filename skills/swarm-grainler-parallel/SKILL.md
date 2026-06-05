---
name: swarm-grainler-parallel
description: >-
  Run a code goal as a Swarm Grainler Parallel job — decompose into
  non-overlapping grains, prove their file-domains disjoint, run each as its own
  specialized LLM in an isolated git worktree, write a dated Decision Ledger, and
  auto-apply reversible self-update learnings. Use when the user says "swarm",
  "grainler", "run this in parallel without agents overlapping", "build X with
  the swarm", "parallel code agents", or asks for an auditable, collision-free
  parallel build.
---

# Swarm Grainler Parallel

Turn one code goal into a **swarm of non-overlapping, specialized, auditable
agents**. This skill is the front door to [`hermes_cli/swarm/`](../../hermes_cli/swarm/).
Read [`docs/orchestration/swarm-grainler-parallel.md`](../../docs/orchestration/swarm-grainler-parallel.md)
for the full architecture.

## When to use

- "Run this in parallel but don't let the agents step on each other."
- "Build the API and the web layer as separate agents."
- "I want an auditable, dated, collision-free parallel build."
- Any code task large enough to split into independent file-domains.

**Do not** swarm a trivial change (a typo, a one-file tweak) — the coordinator
already detects a single-grain plan and runs it inline to avoid the multi-agent
token tax.

## How to run it

1. **Decompose into grains.** Each grain is `{intent, globs, model_lane?}` and
   must own a **disjoint** set of file globs. Assign non-overlapping domains up
   front — this is the guarantee that agents never overlap.

   ```json
   [
     {"intent": "API endpoints", "globs": ["src/api/**"], "model_lane": "claude"},
     {"intent": "Web UI",        "globs": ["src/web/**"], "model_lane": "codex"}
   ]
   ```

2. **Run.**

   ```bash
   python -m hermes_cli.swarm "<goal>" --repo . --grains grains.json
   ```

   or in Python:

   ```python
   from hermes_cli.swarm import run_swarm
   result = run_swarm("<goal>", repo=".", grains=[...])
   ```

3. **Read the output.** The result names each grain's state, its isolated
   worktree/branch, the Decision Ledger path, and any applied/queued
   self-update records.

## Guarantees

- **Non-overlap (3 layers):** static disjointness proof (rejects overlapping
  plans before any agent runs), per-grain git worktree/branch, and lease claims.
- **Each grain is its own specialized LLM:** own model lane, toolset, iteration
  budget, a token-juice context pack, and a dedicated JARVIS Memory Tree
  namespace.
- **Audit / dated:** per-grain dated `status.json`, a 15-section Decision
  Ledger, and the `swarm/<job>` blackboard memory namespace.
- **Self-update:** reversible learnings auto-apply; prompt/skill/risk changes
  are queued for the owner's `"Yes, with authorization."`.

## Owner gates

If any grain carries an owner-gated action (spend, deploy, publish, OAuth,
main-branch merge, package publish, credential change, regulated claim), the
Decision Ledger's *Approval Required* says `yes`, and the grain's system prompt
forbids the action until the owner replies exactly `Yes, with authorization.`

## Safety

The default executor is `PROMPT_ONLY`: it isolates each grain and materialises
its specialized prompt + context, but **launches no model and pushes nothing**.
Nothing is merged or deployed automatically.
