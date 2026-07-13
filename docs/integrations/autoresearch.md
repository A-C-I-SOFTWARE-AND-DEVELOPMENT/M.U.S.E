# Autoresearch — the owner-gated training engine

muse's self-improvement layer wraps engines: SIA rewrites scaffolds, the
retrospective loop proposes routing changes. **Autoresearch is the engine that
trains models** — Karpathy's autonomous pretraining loop
(<https://github.com/karpathy/autoresearch>, MIT), vendored byte-identical and
dropped into the same socket SIA uses, with the four things it deliberately
omits added by muse **gates, owner approval, cost ceiling, provenance**.

## How the pieces map

| autoresearch primitive | muse primitive |
|---|---|
| `results.tsv` row | `flywheel.record("autoresearch.experiment", ...)` (+ TSV kept as local mirror) |
| keep / discard / crash | driver statuses incl. `killed`/`infeasible`; failures auto-queue improvements |
| `val_bpb` (lower better) | `benchmark_gate.evaluate_improvement` on the `bpb_gate_score` transform |
| `git reset` on no-improve | same, inside the disposable workspace repo |
| "advance the branch" on a win | RC4 proposal, `NEEDS_OWNER_APPROVAL` |
| `program.md` | `skills/autoresearch/SKILL.md` (program.md itself stays byte-identical) |
| edits only `train.py` | only the **workspace copy**; vendor payload is sha256-enforced |
| "NEVER STOP" | superseded by the cost ceiling (`max_experiments` / wall-clock / `$`) |
| single CUDA GPU | local CUDA lane or `modal:<gpu>` lanes; swarm coordinator for N lanes |

Modules: `hermes_cli/jarvis_prime/research_fabric/autoresearch/`
(`vendor/`, `platform.py`, `engine.py`, `ideas.py`, `swarm.py`),
`hermes_cli/workers/autoresearch.py` (the five-step adapter),
`hermes_cli/jarvis_prime/autoresearch_improve.py` (the bridge — reuses
`sia_self_improve.run_self_improvement`).

## Setup (owner GPU hardware)

```bash
# 1. One-time: seed a workspace and prepare data (downloads from HF).
python - <<'PY'
from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import (
    ExperimentConfig, seed_workspace)
print(seed_workspace(ExperimentConfig(tag="setup")))
PY
cd ~/.hermes/autoresearch/workspaces/setup
uv sync && uv run prepare.py      # data + tokenizer -> ~/.cache/autoresearch/

# 2. Open the spawn gate (per shell, deliberate).
export MUSE_AUTORESEARCH_ALLOW_SPAWN=1
```

The workspace runs against the **vendored `pyproject.toml`** (which carries
the `pytorch-cu128` index). There is deliberately **no `[autoresearch]` extra**
in muse's own pyproject: the engine's `torch==2.9.1` pin would force a
repo-wide torch downgrade (uv unifies versions across extras), so — exactly
like SIA — the engine lives in its own per-workspace environment.

## Running

See `skills/autoresearch/SKILL.md` for the runtime snippets (single run,
swarm, nightly `autoresearch_train` background job). Idea sources: workers
default to the **built-in knob catalog** (`ideas.DEFAULT_IDEAS` — LR/warmdown/
weight-decay/window/depth/batch tweaks from the vendored README's guidance,
never repeating, always `ast`-validated), optionally chained with any
`(prompt) -> str` LLM runner via `ideas.default_edit_provider(llm_runner)`
(fenced-code extraction, hard validation, bounded idea budget). The flow is
always:
loop in the workspace → constraints gate (VRAM/cost, named failures) →
benchmark gate → **owner-gated proposal**. On approval, `record_promotion()`
writes the HIGH-risk AXIOM classification + chain event.

## Platform notes

- **RTX 5070 (sm_120, 12 GB):** FA3 resolves to `kernels-community/flash-attn3`
  (the Hopper-only repo is skipped); the stock depth-8 baseline was tuned on
  an H100 (~45 GB peak) and **will OOM** — tune the workspace `train.py` with
  the vendored README's small-platform knobs (DEPTH↓, `DEVICE_BATCH_SIZE`↓,
  `WINDOW_PATTERN="L"`). That's the loop working as designed.
- **MFU honesty:** `train.py` prints H100-normalized MFU; the driver records
  both `mfu_percent_raw` and `mfu_percent_honest`
  (`platform.honest_mfu`, per-device peak table).
- **Watchdog:** `TIME_BUDGET` (300 s) + compile + the ~21M-token eval can
  exceed 600 s on slow GPUs — raise `watchdog_seconds` rather than treating
  slow eval as a hang.
- **Termux/aarch64:** not supported (GPU deps have no wheels; markers guard
  the extra). The engine is a laptop/desktop/Modal lane.
- **Reproducibility:** fixed wall-clock means results are comparable only on
  the same machine. `baseline_bpb` is per-device; establish it with an
  unedited first run.

## Owner-gated inventory

1. Any live spawn: `MUSE_AUTORESEARCH_ALLOW_SPAWN=1`.
2. Background live runs: approval token at enqueue AND the spawn env.
3. Champion adoption: RC4 proposal → exact `Yes, with authorization.` → PR.
4. Modal spend: explicit `max_cost_usd > 0` (+ `cost_per_hour_usd`).
5. Learning-dataset export: candidates land `PENDING`.
6. Data download: `uv run prepare.py` run manually by the owner.

Rollback: unset the spawn env (everything degrades to plan-only/unavailable);
workspaces are disposable (`rm -rf ~/.hermes/autoresearch/`); all provenance
stores are append-only JSONL.

## LLM-JEPA fine-tune engine (sibling)

`hermes_cli/jarvis_prime/research_fabric/llm_jepa/` is a **sibling** engine that
runs the LLM-JEPA objective (Huang, LeCun & Balestriero, arXiv 2509.14252) as an
owner-gated experiment variant — Phase 2 (Option D) of the JEPA integration
plan. It follows every autoresearch convention (torch-free lazy import,
`vendor/` do-not-edit + `checksums.json`, isolated `uv` env, dry-run default,
RC4 promotion), differing only in that it *fine-tunes* a small (≤1B) base model
rather than pretraining from scratch.

| Concept | Where |
|---|---|
| Objective (clean-room) | `llm_jepa/vendor/train.py` — `L = L_LLM + λ·d(Pred(Enc(text)), Enc(code))`, LoRA, loss-dropout |
| Two-view builder | `llm_jepa/views.py` — `(text, code)` pairs from git issue→diff and prompt→result history |
| Governed driver | `llm_jepa/engine.py` — `plan_finetune` (dry-run), `run_finetune` (gated), `evaluate_finetune` (benchmark gate), `propose_promotion` (RC4) |
| Worker | `hermes_cli/workers/llm_jepa.py` — id `llm-jepa`, five-step contract, `WorkerScore` from downstream accuracy |

Gates:

1. **Dry-run by default** — the worker only produces a plan unless `dry_run=False`.
2. **Live spawn** — `MUSE_LLM_JEPA_ALLOW_SPAWN=1` (mirrors the autoresearch spawn gate).
3. **Promotion** — a winning objective is an RC4 `SELF_RUNTIME_UPDATE` proposal that lands `NEEDS_OWNER_APPROVAL` (exact `Yes, with authorization.`); a worker never applies it. On a FAIL the gate emits no proposal — keep the baseline.

Isolated env: `torch` / `transformers` / `peft` live **only** in the vendored
`llm_jepa/vendor/pyproject.toml` (cu128 index), never in the MUSE root
`pyproject.toml` — there is deliberately **no `[llm-jepa]` extra**, exactly as
autoresearch avoids a `torch` extra.

### Clean-room + license boundary

`vendor/train.py` is a **clean-room** implementation of the published objective
(like the tokenjuice port), credited to the upstream reference
`rbalestr-lab/llm-jepa` (MIT) in `VENDOR.md`; it is not a byte copy. This keeps
MUSE on a permissive path: prefer training your **own** weights with the
LLM-JEPA *objective* over shipping the CC-BY-NC vision checkpoints
(facebookresearch `jepa`/`vjepa2`), which are non-commercial and must stay off
any commercial path.
