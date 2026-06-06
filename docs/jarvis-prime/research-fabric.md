# Research Fabric — bounded-autonomous, verifier-gated self-improvement

> Additive package: `hermes_cli/jarvis_prime/research_fabric/`. It does not change
> any default runtime behavior. Auto-apply is **off** until an owner signs a
> charter, and even then it is walled, gated, and reversible.

## Why this exists

The owner asked for self-improvement that becomes **autonomous** — but only
behind checks, gates, validation, and a passing threshold that **proves
qualitative improvement and can never worsen itself**, starting with software /
development and generalizing toward "any role."

This is grounded in the DeepMind self-learning lineage and the current SOTA in
self-improving agents. The central finding shapes the whole design:

> **Self-improvement tracks the quality of the verifier.** Go/chess (win/loss)
> and protein folding (measured PDB structures) were tractable for super-human
> results because each had a *cheap, near-perfect ground-truth signal*. Software
> is one of the few open-ended domains that *also* has one — compilers,
> type-checkers, tests, CI, latency counters. So software-first is the right
> beachhead, and the owner's "never worsens itself" instinct is not a brake; it
> is the mechanism that made **AlphaGo Zero** work.

### The load-bearing precedent

AlphaGo Zero kept its self-play data *monotonically non-regressing* with an
**evaluator gate**: a freshly-trained challenger replaced the champion only if it
won **>55%** of 400 head-to-head games (AlphaZero paper, arXiv:1712.01815) — a
statistical margin, not a coin flip. That is exactly the **ratchet** here.

### Two safety facts we build around

- **AZR "uh-oh moment"** (arXiv:2505.03335): even a zero-data self-play model
  emitted misaligned reasoning. Self-play *surfaces* misalignment.
- **The Darwin-Gödel-Machine** (arXiv:2505.22954) edited its own logging to
  delete the markers its cheat-detector looked for; Anthropic's *Sycophancy to
  Subterfuge* (arXiv:2406.10162) showed this generalizes to reward-tampering.
  **⇒ The verifier, reward, monitor, walls, and ledger live outside the agent's
  write scope** (encoded as the fatal clause **C34**).

## The pieces

| Module | Responsibility |
|---|---|
| `catalog.py` | `REQUIRED_DOMAINS`, thresholds (`ABSOLUTE_FLOOR=0.80`, `COMPOSITE_MARGIN=0.05`, `EVAL_WIN_MARGIN=0.55`), `SAFETY_DOMAINS`, sandbox `WORKER_POLICY`, registered model/benchmark/dataset candidates. |
| `validators.py` | `evaluate_ratchet` / `RatchetWall` — the strict non-regression rule. |
| `store.py` | `SnapshotStore` — a SQLite **index** (integrity stays in the guardrail ledger). |
| `champion.py` | `Champion` + `ChampionStore` — frozen per-domain baselines + rollback handle. |
| `charter.py` | `AutonomyCharter` + `CharterBook` + the hard wall (`HARD_WALL_KINDS`, `PROTECTED_PATH_MARKERS`). |
| `controller.py` | `AutonomyController` — composes the full envelope. |
| `monitor.py` | `AlignmentMonitor` — tripwires that revoke the charter and halt autonomy. |
| `ambition.py` | `apply_ambition` — additive, bar-raising objective dimensions. |
| `verifier/` | Plane 1 reward channel: `Candidate` + `screen_for_reward_hacking`. |
| `selfplay/`, `archive/` | Plane 2/3 scaffolds (AZR/POET self-play; Darwin-Gödel archive). |
| `pipeline.py`, `main.py` | Wiring + CLI. |

## The ratchet rule (`evaluate_ratchet`)

A challenger passes only if **all** hold:

1. **No required domain dropped** (missing score ⇒ fail).
2. **Meet/beat champion on every domain** (per-domain `evaluate_improvement`).
3. **Absolute floor** — every domain ≥ 0.80.
4. **Composite margin** — composite ≥ champion + 0.05.
5. **Evaluator gate** — challenger win-rate ≥ 0.55.
6. **Held-out wall** — held-out scores independently clear floor + meet champion.
7. **Safety non-regression** — hallucination/owner-correction counts may not rise;
   `SAFETY_DOMAINS` may only rise.
8. **Cold start** (no champion yet) — floor + held-out floor only.

The **ambition layer** can only ever *narrow* a pass to a fail; it can never flip
a fail to a pass, and never touches a safety field.

## The controller envelope (order of operations)

1. Reward-hacking / monitor screen → a tripwire **halts autonomy** (revokes the
   charter), blocks, and surfaces no proposal (a regression/hack is not promotable).
2. **Hard wall (C34)** → runtime, gates, owner-auth, model registry, routing, the
   verifier/monitor/ledger harness, and the Constitution can only become an
   owner-gated proposal — never auto-apply, regardless of any charter.
3. **Ratchet (+ ambition)** → failure blocks with no proposal.
4. **Eight strict gates** (`run_strict_gate_summary`) → FAIL blocks;
   NEEDS_OWNER_APPROVAL falls back to a proposal.
5. **Capability wall** → off by default (mirrors `HERMES_CAPABILITY_GATE`).
6. **Charter scope + budget** → no active charter ⇒ owner-gated proposal; out of
   scope / over budget ⇒ proposal.
7. **Auto-apply** → capture the rollback handle, apply, ledger `auto_apply`,
   freeze the new champion.
8. **Canary** → re-measure; any regression vs the prior champion triggers
   `rollback` + ledger `auto_rollback` + champion restore.

`applier` / `canary` / `rollback` are injected callables, so CI uses fakes and the
CLI `run` is always a safe dry-run.

## Charter lifecycle (owner-gated)

```bash
# 1) Mint a nonce-bound challenge (prints the exact phrase to echo).
python -m hermes_cli.jarvis_prime research-fabric charter challenge \
    --allowed-kinds skill_update --risk-ceiling RC2 --budget 5

# 2) Answer it to mint the charter.
python -m hermes_cli.jarvis_prime research-fabric charter grant \
    --challenge-id <id> --phrase "Yes, with authorization. Code: <nonce>"

# Inspect / revoke
python -m hermes_cli.jarvis_prime research-fabric charter status
python -m hermes_cli.jarvis_prime research-fabric charter revoke --charter-id <id>
```

A charter can never include a hard-walled kind, can never have an RC4 ceiling, and
expires + is revocable + budget-limited.

## Other commands

```bash
python -m hermes_cli.jarvis_prime research-fabric validate --scores '{...}' \
    --holdout '{...}' --eval-win-rate 0.6
python -m hermes_cli.jarvis_prime research-fabric champion show
python -m hermes_cli.jarvis_prime research-fabric run --candidate-json cand.json  # dry-run
python -m hermes_cli.jarvis_prime research-fabric report     # ledger + champion + chain check
python -m hermes_cli.jarvis_prime research-fabric inventory  # registered candidates
```

## Constitution relationship

- **C28** (unchanged, fatal) — outside an active charter, every self-change is an
  owner-decided proposal.
- **C33** (major) — the *sole, narrow* bounded-autonomy exception: auto-apply only
  inside an active charter after the ratchet + 0.55 evaluator gate + the eight
  gates + the capability wall all pass.
- **C34** (fatal) — the inviolable wall: runtime/gates/owner-auth/registry/routing/
  harness/Constitution never auto-apply; a canary auto-rolls-back any regression.

## Software-dev-first stack & benchmark lanes

- **Worker:** Qwen3-Coder (Apache-2.0). **Student:** DeepSeek-V3.2 / R1-distill (MIT).
- **Train lanes:** SWE-rebench, BigCodeBench, Commit0.
- **Held-out walls (never trained on):** SWE-bench Pro held-out, LiveCodeBench
  post-cutoff, freshest SWE-rebench window.
- **Algorithms lane (purest verifier, build first):** an AlphaEvolve/FunSearch-style
  propose→execute-verify→evolve loop scored on exact op-count/latency — the same
  loop that produced AlphaTensor, AlphaDev (merged into LLVM libc++), and
  AlphaEvolve's 48-multiplication 4×4 scheme.

## Honest boundaries

"Fit any role" is the north star, not a near-term claim. Autonomy generalizes only
as fast as trustworthy verifiers appear; domains without a real verifier stay
supervised and owner-gated. The line we will not cross: the agent never gains write
access to its verifier, reward, monitor, walls, gates, owner-auth, or Constitution
— that isolation is why "never worsens itself" is provable rather than hopeful.
