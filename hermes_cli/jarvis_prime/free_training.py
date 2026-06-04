"""Free, continuous, gated training — beating paid SFT with method + your data.

The paid path (Together LoRA SFT, see ``hermes_cli/nlp_training.py``) is
*supervised fine-tuning only*. This module is the free alternative and the
reason it can do **better**:

1. **Free compute** — Unsloth + TRL run QLoRA *and RL* on a free Colab/Kaggle
   T4 (or a local GPU) for 1B-10B models (~2x faster, ~70% less VRAM). An 8B
   model fits a free T4. No per-job API cost.
2. **A stronger recipe** — SFT → ORPO/DPO (preference) → **GRPO with verifiable
   rewards**. Published results show preference optimization beats SFT-only and
   that RL-with-verifiable-rewards (DeepSeek-R1's method) lifts capability with
   *no human/paid judge labels*.
3. **A reward you already own** — Hermes' deterministic **verification gates**
   are a verifiable reward signal. :func:`reward_from_gate_summary` turns a
   ``gates.run_gate_summary`` result into a scalar reward for GRPO — tests
   passing, secret-free, reviewer-passed, rollback-ready. That is exactly the
   "verifiable reward" RLVR needs, for free.

This module is deterministic and IO-light: it computes the gate reward and
**generates runnable Unsloth+TRL recipes** (it does not train here — there is no
GPU in this process; the emitted script runs on free hardware you point it at).

See docs/ai-intelligence/free-continuous-training.md.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional

# --------------------------------------------------------------------------
# Verifiable reward from Hermes verification gates (the RLVR signal)
# --------------------------------------------------------------------------

# Per-gate weight in the graded reward (owner_approval is governance, not a
# quality signal, so it is intentionally excluded). Weights sum to 1.0.
GATE_WEIGHTS: dict[str, float] = {
    "planning": 0.10,
    "build": 0.20,
    "review": 0.15,
    "test": 0.25,
    "security": 0.15,
    "release": 0.10,
    "rollback": 0.05,
}

# Credit per gate outcome (gates.GateOutcome values).
_OUTCOME_CREDIT: dict[str, float] = {
    "pass": 1.0,
    "skipped": 0.5,
    "needs_owner_approval": 0.25,
    "fail": 0.0,
}


def _results(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = summary.get("results") or []
    return [r for r in rows if isinstance(r, dict)]


def reward_components(summary: Mapping[str, Any]) -> dict[str, float]:
    """Per-gate reward contributions (weight * outcome credit)."""

    out: dict[str, float] = {}
    for r in _results(summary):
        name = str(r.get("name", ""))
        if name not in GATE_WEIGHTS:
            continue
        credit = _OUTCOME_CREDIT.get(str(r.get("outcome", "")), 0.0)
        out[name] = round(GATE_WEIGHTS[name] * credit, 4)
    return out


def reward_from_gate_summary(summary: Mapping[str, Any]) -> float:
    """Graded verifiable reward in ``[0, 1]`` from a gate summary.

    Normalized by the weight of the gates actually present so a partial gate
    set still yields a calibrated reward. Deterministic — same summary, same
    reward — which is exactly what GRPO/RLVR requires.
    """

    present = [r for r in _results(summary) if str(r.get("name")) in GATE_WEIGHTS]
    if not present:
        return 0.0
    total_weight = sum(GATE_WEIGHTS[str(r["name"])] for r in present)
    earned = sum(
        GATE_WEIGHTS[str(r["name"])] * _OUTCOME_CREDIT.get(str(r.get("outcome", "")), 0.0)
        for r in present
    )
    return round(earned / total_weight, 4) if total_weight else 0.0


def verifiable_pass(summary: Mapping[str, Any]) -> bool:
    """Strict binary reward: no gate failed and at least one gate passed.

    Use as a 0/1 GRPO reward for hard verification (e.g. "tests must pass").
    """

    overall = str(summary.get("overall", ""))
    if overall == "fail":
        return False
    outcomes = [str(r.get("outcome", "")) for r in _results(summary)]
    return "fail" not in outcomes and "pass" in outcomes


# --------------------------------------------------------------------------
# Free recipe generation (Unsloth + TRL, runnable on free GPU)
# --------------------------------------------------------------------------


class TrainingStage(str, Enum):
    SFT = "sft"        # supervised fine-tuning (Unsloth QLoRA)
    ORPO = "orpo"      # preference optimization, single-stage (no ref model)
    DPO = "dpo"        # preference optimization, reference model
    GRPO = "grpo"      # RL with the gate reward (verifiable rewards)


DEFAULT_BASE_MODEL = "unsloth/Qwen3-8B"  # fits a free Colab/Kaggle T4 in 4-bit


def _sft_script(base_model: str, dataset_path: str, out_dir: str) -> str:
    return f'''"""Free QLoRA SFT via Unsloth + TRL. Run on a free Colab/Kaggle T4."""
from unsloth import FastLanguageModel, is_bfloat16_supported
from trl import SFTConfig, SFTTrainer
from datasets import load_dataset

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name={base_model!r}, max_seq_length=4096, load_in_4bit=True)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=16, lora_dropout=0.0,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"])

dataset = load_dataset("json", data_files={dataset_path!r}, split="train")

trainer = SFTTrainer(
    model=model, tokenizer=tokenizer, train_dataset=dataset,
    args=SFTConfig(
        output_dir={out_dir!r}, per_device_train_batch_size=2,
        gradient_accumulation_steps=4, num_train_epochs=3,
        learning_rate=2e-4, warmup_ratio=0.03, logging_steps=10,
        optim="adamw_8bit", lr_scheduler_type="cosine",
        fp16=not is_bfloat16_supported(), bf16=is_bfloat16_supported()))
trainer.train()
model.save_pretrained_merged({out_dir!r}, tokenizer, save_method="lora")
'''


def _orpo_script(base_model: str, dataset_path: str, out_dir: str) -> str:
    return f'''"""Free ORPO preference optimization (beats SFT-only; no reference model)."""
from unsloth import FastLanguageModel, is_bfloat16_supported
from trl import ORPOConfig, ORPOTrainer
from datasets import load_dataset

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name={base_model!r}, max_seq_length=4096, load_in_4bit=True)
model = FastLanguageModel.get_peft_model(model, r=16, lora_alpha=16)

# Preference rows: {{"prompt", "chosen", "rejected"}} (e.g. HelpSteer3 / UltraFeedback).
dataset = load_dataset("json", data_files={dataset_path!r}, split="train")

trainer = ORPOTrainer(
    model=model, processing_class=tokenizer, train_dataset=dataset,
    args=ORPOConfig(
        output_dir={out_dir!r}, per_device_train_batch_size=2,
        gradient_accumulation_steps=4, num_train_epochs=1,
        learning_rate=8e-6, beta=0.1, logging_steps=10,
        optim="adamw_8bit", lr_scheduler_type="cosine",
        fp16=not is_bfloat16_supported(), bf16=is_bfloat16_supported()))
trainer.train()
model.save_pretrained_merged({out_dir!r}, tokenizer, save_method="lora")
'''


def _dpo_script(base_model: str, dataset_path: str, out_dir: str) -> str:
    return f'''"""Free DPO preference optimization (reference-model variant)."""
from unsloth import FastLanguageModel, is_bfloat16_supported
from trl import DPOConfig, DPOTrainer
from datasets import load_dataset

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name={base_model!r}, max_seq_length=4096, load_in_4bit=True)
model = FastLanguageModel.get_peft_model(model, r=16, lora_alpha=16)

# Preference rows: {{"prompt", "chosen", "rejected"}} (e.g. HelpSteer3 / UltraFeedback).
dataset = load_dataset("json", data_files={dataset_path!r}, split="train")

trainer = DPOTrainer(
    model=model, ref_model=None, processing_class=tokenizer,
    train_dataset=dataset,
    args=DPOConfig(
        output_dir={out_dir!r}, per_device_train_batch_size=2,
        gradient_accumulation_steps=4, num_train_epochs=1,
        learning_rate=5e-6, beta=0.1, logging_steps=10,
        optim="adamw_8bit", lr_scheduler_type="cosine",
        fp16=not is_bfloat16_supported(), bf16=is_bfloat16_supported()))
trainer.train()
model.save_pretrained_merged({out_dir!r}, tokenizer, save_method="lora")
'''


def _grpo_script(base_model: str, dataset_path: str, out_dir: str) -> str:
    return f'''"""Free GRPO with VERIFIABLE REWARDS = Hermes verification gates.

The reward runs the model's produced work through Hermes' gates and returns
``reward_from_gate_summary`` — no human/paid judge. Wire a real verifier (run
tests, scan secrets, score citations) inside ``gate_summary_for`` for your task.
"""
from unsloth import FastLanguageModel, is_bfloat16_supported
from trl import GRPOConfig, GRPOTrainer
from datasets import load_dataset

from hermes_cli.jarvis_prime.free_training import reward_from_gate_summary

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name={base_model!r}, max_seq_length=4096, load_in_4bit=True,
    fast_inference=True, max_lora_rank=16)
model = FastLanguageModel.get_peft_model(model, r=16, lora_alpha=16)

dataset = load_dataset("json", data_files={dataset_path!r}, split="train")

def gate_summary_for(prompt, completion):
    # TODO: run the completion through your verifier (tests / secret scan /
    # citation check) and return a gates.run_gate_summary().to_dict(). The
    # stub below rewards a non-empty, secret-free completion.
    failed = "fail" if (not completion or "sk-" in completion) else "pass"
    return {{"results": [{{"name": "test", "outcome": failed}},
                        {{"name": "security", "outcome": "pass"}}]}}

def gate_reward(prompts, completions, **kwargs):
    return [reward_from_gate_summary(gate_summary_for(p, c))
            for p, c in zip(prompts, completions)]

trainer = GRPOTrainer(
    model=model, processing_class=tokenizer, reward_funcs=[gate_reward],
    train_dataset=dataset,
    args=GRPOConfig(
        output_dir={out_dir!r}, per_device_train_batch_size=4,
        gradient_accumulation_steps=2, num_generations=4, num_train_epochs=1,
        learning_rate=5e-6, logging_steps=10, optim="adamw_8bit",
        fp16=not is_bfloat16_supported(), bf16=is_bfloat16_supported()))
trainer.train()
model.save_pretrained_merged({out_dir!r}, tokenizer, save_method="lora")
'''


_SCRIPTS = {
    TrainingStage.SFT: _sft_script,
    TrainingStage.ORPO: _orpo_script,
    TrainingStage.DPO: _dpo_script,
    TrainingStage.GRPO: _grpo_script,
}


@dataclass(frozen=True)
class RecipeArtifact:
    stage: TrainingStage
    base_model: str
    dataset_path: str
    out_dir: str
    script: str
    config: dict[str, Any] = field(default_factory=dict)

    def valid_python(self) -> bool:
        try:
            ast.parse(self.script)
            return True
        except SyntaxError:
            return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "base_model": self.base_model,
            "dataset_path": self.dataset_path,
            "out_dir": self.out_dir,
            "config": self.config,
            "script_valid_python": self.valid_python(),
        }

    def write(self, directory: str | Path) -> Path:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        script_path = d / f"train_{self.stage.value}.py"
        script_path.write_text(self.script, encoding="utf-8")
        (d / f"recipe_{self.stage.value}.json").write_text(
            json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return script_path


def generate_recipe(
    dataset_path: str | Path,
    *,
    stage: TrainingStage = TrainingStage.SFT,
    base_model: str = DEFAULT_BASE_MODEL,
    out_dir: str = "data/models/free",
) -> RecipeArtifact:
    """Emit a runnable Unsloth+TRL training script for a free GPU run.

    Generate-only — the actual training runs where you point the script (free
    Colab/Kaggle T4 or a local GPU). For GRPO the reward is the Hermes gate
    reward (verifiable, no paid judge).
    """

    builder = _SCRIPTS[stage]
    script = builder(base_model, str(dataset_path), out_dir)
    return RecipeArtifact(
        stage=stage, base_model=base_model, dataset_path=str(dataset_path),
        out_dir=out_dir, script=script,
        config={
            "framework": "unsloth+trl",
            "method": stage.value,
            "quantization": "4bit-qlora",
            "free_compute": ["colab-t4", "kaggle-t4", "local-gpu"],
            "paid_api": False,
        })


# --------------------------------------------------------------------------
# The free continuous gated loop (descriptor)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FreeContinuousPlan:
    """Describes the free, continuous, gated self-improvement loop.

    harvest -> recipe (SFT -> ORPO -> GRPO) -> eval(benchmark_wall) ->
    promote(scorecard.promotion_eligible) -> repeat. Each cycle uses only
    owner-approved data and free compute; promotion is measure-driven.
    """

    base_model: str = DEFAULT_BASE_MODEL
    stages: tuple[str, ...] = ("sft", "orpo", "grpo")
    reward: str = "hermes-verification-gates"
    eval_set: str = "benchmark_wall (held out; never trained on)"
    promotion: str = "model_scorecard.promotion_eligible (>=20 samples, >=+0.05 delta)"
    compute: tuple[str, ...] = ("colab-t4", "kaggle-t4", "local-gpu")

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_model": self.base_model,
            "stages": list(self.stages),
            "reward": self.reward,
            "eval_set": self.eval_set,
            "promotion": self.promotion,
            "compute": list(self.compute),
            "paid_api": False,
        }


__all__ = [
    "GATE_WEIGHTS",
    "reward_from_gate_summary",
    "reward_components",
    "verifiable_pass",
    "TrainingStage",
    "RecipeArtifact",
    "generate_recipe",
    "FreeContinuousPlan",
    "DEFAULT_BASE_MODEL",
]
