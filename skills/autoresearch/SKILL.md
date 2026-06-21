---
name: autoresearch
description: "Run Karpathy's autoresearch loop — autonomous 5-minute pretraining experiments on the vendored nanochat-style engine — inside a disposable workspace, governed by muse's cost ceiling, VRAM feasibility gate, and benchmark gate, with every experiment on the flywheel. The winning train.py surfaces as an owner-gated proposal; val_bpb LOWER is better; nothing is ever applied without the owner."
version: 1.0.0
author: "muse (engine: Andrej Karpathy, MIT)"
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [autoresearch, karpathy, pretraining, gpu, benchmark, owner-gated, self-improvement, swarm]
    related_skills: [sia-self-improve, self-improvement-loop, best-coding-tool-mission]
    owner_gated: true
    intelligence_sources:
      - https://github.com/karpathy/autoresearch
      - hermes_cli/jarvis_prime/research_fabric/autoresearch/vendor/program.md
      - docs/integrations/autoresearch.md
---

# Autoresearch (owner-gated training engine)

> autoresearch (https://github.com/karpathy/autoresearch, MIT — vendored
> byte-identical at `hermes_cli/jarvis_prime/research_fabric/autoresearch/vendor/`)
> is an autonomous research loop: an agent edits `train.py`, trains a small
> GPT for a fixed 5-minute budget, reads **val_bpb (lower is better)**, keeps
> the commit if it improved or `git reset`s if not — ~12 experiments/hour.
> muse runs that loop **inside a disposable workspace** and treats the winner
> as a *proposal*, not an applied change. **muse never silently adopts a
> training recipe.**

Load this skill when the owner asks to "train a better small model", "run
autoresearch overnight", "autoresearch swarm", or "improve the pretraining
recipe".

## What it does

1. **Seed** — copy the vendored payload into
   `$HERMES_HOME/autoresearch/workspaces/<tag>/`, `git init`, branch
   `autoresearch/<tag>` (the muse repo is never touched; vendored files stay
   byte-identical — experiments mutate only workspace copies).
2. **Loop** (the vendored `program.md`, governed) — edit the workspace
   `train.py` → commit → `uv run train.py > run.log` → parse the summary →
   keep if `val_bpb` dropped, reset if not. Watchdog kills hangs at 10
   minutes; over-VRAM-budget runs are **infeasible** (reset, never champion);
   every experiment is recorded to the flywheel
   (`autoresearch.experiment`; crash/killed/infeasible auto-queue an
   improvement). `results.tsv` is a local mirror only.
3. **Stop** — muse's **cost ceiling supersedes program.md's NEVER STOP**:
   the run halts at `max_experiments` / `max_wall_clock_seconds` /
   `max_cost_usd`, whichever hits first.
4. **Gates** — constraints gate first (named "wins bpb but blew VRAM/cost"
   FAIL), then the benchmark gate
   (`benchmark_gate.evaluate_improvement` on the order-preserving
   `bpb_gate_score` transform — raw bpb stays in all evidence).
5. **Propose** — a genuine winner becomes an RC4 `SELF_RUNTIME_UPDATE`
   proposal with status `NEEDS_OWNER_APPROVAL` (the exact phrase
   `Yes, with authorization.` + PR flow). Champions also get a
   `ModelScorecard` row, an AXIOM `autoresearch.champion` chain event, a
   durable Memory-Tree "what worked" note, and a PENDING learning-dataset
   candidate.

## Inputs

`tag` (run name), `objective`, ceilings (`max_experiments`,
`max_wall_clock_seconds`, `max_cost_usd` + `cost_per_hour_usd` for Modal),
`vram_budget_mb` (default 90% of detected VRAM), `baseline_bpb` (per-device;
first run establishes it when omitted), `min_bpb_delta`, `lanes` (swarm).

## Runtime

```python
from hermes_cli.jarvis_prime.autoresearch_improve import run_autoresearch_improvement
from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import ExperimentConfig
from hermes_cli.jarvis_prime.self_update import ProposalBook
from hermes_cli.workers.autoresearch import AutoresearchWorker, AutoresearchWorkerConfig

config = ExperimentConfig(tag="jun12", max_experiments=12, vram_budget_mb=11059)
# propose_edit is optional: omitted, the built-in idea source is used — the
# deterministic knob catalog (ideas.DEFAULT_IDEAS), optionally chained with an
# LLM via ideas.default_edit_provider(llm_runner).
worker = AutoresearchWorker(
    config=AutoresearchWorkerConfig(experiment=config, propose_edit=my_idea_provider)
)
outcome = run_autoresearch_improvement(
    "minimize val_bpb", book=ProposalBook(), worker=worker,
    baseline_bpb=1.0, vram_budget_mb=config.vram_budget_mb,
)
```

Swarm (N lanes, one merged scorecard book, exactly ONE proposal):

```python
from hermes_cli.jarvis_prime.research_fabric.autoresearch.swarm import plan_swarm, run_swarm
plan = plan_swarm("jun12", 2, base_config=config)
outcome = run_swarm(plan, worker_factory=make_worker, book=book, baseline_bpb=1.0)
```

Nightly: enqueue a `"autoresearch_train"` background-learner job (dry_run
default = plan-only report; live needs the approval token AND the spawn env).

## Guardrails (non-negotiable)

- **Spawn gate:** nothing runs without `muse_AUTORESEARCH_ALLOW_SPAWN=1`.
- **Data prep on owner hardware only:** `uv run prepare.py` in a seeded
  workspace downloads from Hugging Face (blocked in CI containers).
- **Cost ceiling supersedes NEVER STOP.** Modal spend requires an explicit
  `max_cost_usd > 0` from the owner.
- **Vendored files are never edited in-repo** (sha256-enforced); the
  workspace copy of `train.py` is the only mutable surface;
  `prepare.py`/`evaluate_bpb` stay the fixed ground truth everywhere.
- **Honesty:** this is a 5-minute pretraining proxy (depth 8, 8192 vocab) —
  not a production model. MFU is re-normalized per device
  (`platform.honest_mfu`); raw H100-normalized numbers are never reported as
  device-true. Baselines are per-machine and never comparable across hosts.
- **RTX 5070 note (sm_120, 12 GB):** the stock `DEPTH=8`/`DEVICE_BATCH_SIZE=128`
  baseline may OOM; tuning the workspace `train.py` down (README's
  small-platform knobs) is allowed and expected. FA3 falls back to
  `kernels-community/flash-attn3` off-Hopper.
- **Promotion:** owner approval → PR flow → `record_promotion()` writes the
  HIGH-risk AXIOM classification + `autoresearch.promotion` chain event.
