# Free, continuous, gated training (beating paid SFT)

The paid path ([`docs/nlp_training.md`](../nlp_training.md), Together AI) does
**supervised fine-tuning only**. This is the free alternative — and the reason
it can do **better**, not just cheaper. Module:
`hermes_cli/jarvis_prime/free_training.py`.

## Why free can beat the paid option

"Free" doesn't beat "paid" because the GPU is magic — it wins on **method** and
**data**, while free compute is now *sufficient*:

1. **Free compute is enough.** [Unsloth](https://unsloth.ai/) runs QLoRA **and
   RL** on a free Colab/Kaggle **T4** for 1B–10B models — ~2× faster, ~60–70%
   less VRAM. An 8B model fits a free T4 in 4-bit. [TRL v1.0](https://github.com/huggingface/trl)
   (Apr 2026) unifies SFT/DPO/GRPO and uses Unsloth kernels. No per-job API fee.
2. **A stronger recipe than SFT-only.** Together's managed offering is LoRA SFT.
   Published results: **ORPO outperforms SFT (~78% win) and SFT+DPO**; Tülu 3
   uses SFT→DPO; and **GRPO / RLVR** (DeepSeek-R1's method) lifts capability
   with *no human or paid-judge labels*. SFT alone can even degrade
   out-of-distribution; RL/preference *amplify* in-distribution skill.
3. **A verifiable reward you already own.** RLVR's hard requirement is a
   *verifiable* reward. Hermes' **verification gates** (build/review/test/
   security/release/rollback) are exactly that — deterministic, no judge.
   `reward_from_gate_summary(gate_summary)` turns a `gates.run_gate_summary`
   result into a scalar reward in `[0, 1]` for GRPO.
4. **On-distribution data.** Your owner-approved traces + the clustered open
   datasets ([`training-data-clusters.md`](training-data-clusters.md)) are
   closer to what the agent actually does than any generic paid SFT mix.

| | Paid (Together) | Free (this) |
|---|---|---|
| Method | LoRA SFT only | SFT → ORPO/DPO → **GRPO (gate reward)** |
| Reward | n/a | **Hermes gates** (verifiable, free) |
| Compute | paid per job | free T4 / Kaggle / local |
| Promotion | manual | measure-gated (`scorecard.promotion_eligible`) |

## The loop

```
harvest owner-approved traces (DatasetStore + clusters)
   → recipe: SFT (Unsloth QLoRA) → ORPO/DPO (preference-safety cluster)
            → GRPO with reward = reward_for_work (real gates)  [free GPU]
   → evaluate on the held-out benchmark_wall  (never trained on)
   → promote ONLY if it beats the incumbent
        (model_scorecard.promotion_eligible: ≥20 samples, ≥+0.05 mean delta,
         no extra hallucinations/owner-corrections, within latency budget)
   → repeat on a schedule           ← "train continuously"
```

Every cycle uses only **owner-approved data** + **free compute**, and promotion
is **measure-driven** (the existing scorecard gate), so a worse model is never
shipped. This reuses what the repo already has: `learning_dataset.DatasetStore`,
`gates.run_gate_summary`, the `benchmark_wall` partition of the registry, and
`model_scorecard.promotion_eligible`.

## Commands

```bash
# Describe the loop
python -m hermes_cli.jarvis_prime learning free-plan

# ONE wired pass: harvest owner-approved traces → export JSONL → emit the
# SFT→ORPO→GRPO recipes (and optionally write the scripts). This is the loop
# runner — it does the real local work, then reports the eval+promotion plan.
python -m hermes_cli.jarvis_prime learning free-loop \
    --base-model unsloth/Qwen3-8B --write data/models/free
python -m hermes_cli.jarvis_prime learning free-loop --stage sft --json  # one stage

# Emit a single runnable recipe for a stage from an explicit dataset
python -m hermes_cli.jarvis_prime learning free-recipe data/approved/together_train.jsonl \
    --stage sft  --base-model unsloth/Qwen3-8B --write data/models/free
python -m hermes_cli.jarvis_prime learning free-recipe data/approved/prefs.jsonl --stage orpo
python -m hermes_cli.jarvis_prime learning free-recipe data/approved/tasks.jsonl --stage grpo

# Measure-gated promotion: assess a candidate against the measured incumbent.
# Exit code 0 only when promotion_eligible (≥20 samples, ≥+0.05 mean delta, …).
python -m hermes_cli.jarvis_prime learning promote \
    --candidate unsloth/Qwen3-8B-free-lora --task-class coding_build
```

The emitted script runs **where you point it** — a free Colab/Kaggle T4 or a
local GPU. This process never trains (no GPU here); it generates the recipe and
computes the gate reward.

**The reward is wired to the real gates.** `free_training.reward_for_work(packet)`
calls `gates.run_gate_summary` (the same deterministic gate machinery the
verification layer uses) and grades the result into a `GateReward`
(graded `[0,1]` + strict verifiable pass). The GRPO recipe references it: turn
the model's completion into a Hermes work packet inside the script's
`packet_for(...)` and `reward_for_work(packet).reward` is your fully verifiable,
free reward — no human/paid judge.

## Continuous scheduling

Drive the loop from the repo's existing scheduler (cron/gateway tick): on each
tick, export newly owner-approved traces, regenerate the recipe, run it on the
free runner, evaluate on the benchmark wall, record a `ModelScorecard`, and call
`promotion_eligible` — promote the adapter only on a measured win. The
`benchmark_wall` set stays decontaminated (never trained on).

## Sources

- [Unsloth — free LoRA/RL on Colab/Kaggle](https://unsloth.ai/) · [RL guide](https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide)
- [Hugging Face TRL (SFT/DPO/GRPO)](https://github.com/huggingface/trl)
- [RLVR overview](https://www.promptfoo.dev/blog/rlvr-explained/) · [GRPO vs SFT — Scalpel vs Hammer](https://arxiv.org/abs/2507.10616)
- [ORPO outperforms SFT/DPO](https://arxiv.org/abs/2403.07691) · [Tülu 3 post-training](https://allenai.org/blog/tulu-3-technical)
- [Post-training in 2026: GRPO, DAPO, RLVR](https://llm-stats.com/blog/research/post-training-techniques-2026)
