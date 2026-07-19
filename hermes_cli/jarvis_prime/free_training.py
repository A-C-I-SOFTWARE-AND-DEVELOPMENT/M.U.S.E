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
from typing import TYPE_CHECKING, Any, Mapping, Optional, Sequence

if TYPE_CHECKING:  # pragma: no cover - typing only
    from hermes_cli.jarvis_prime.learning_dataset import DatasetStore

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


@dataclass(frozen=True)
class GateReward:
    """A verifiable reward computed from a *real* gate run.

    ``reward`` is the graded [0, 1] signal; ``verifiable`` is the strict 0/1
    pass; ``components`` are the per-gate contributions; ``summary`` is the raw
    ``GateSummary.to_dict()`` the reward was derived from (kept for audit).
    """

    reward: float
    verifiable: bool
    components: dict[str, float]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reward": self.reward,
            "verifiable": self.verifiable,
            "components": self.components,
            "overall": self.summary.get("overall"),
            "remaining_risk": self.summary.get("remaining_risk"),
        }


def reward_for_work(
    packet: Mapping[str, Any],
    *,
    evidence_bundle: Any = None,
    strict_evidence: bool = False,
) -> GateReward:
    """Run a work packet through the **real Hermes gates** and grade it.

    This is the wired counterpart to :func:`reward_from_gate_summary`: rather
    than accept a pre-computed summary dict, it calls
    :func:`gates.run_gate_summary` — the same deterministic gate machinery the
    verification layer uses — then converts the result into the graded +
    verifiable reward. This is the connection that lets the free GRPO loop use
    Hermes' verification gates as the verifiable reward signal end to end, with
    no human/paid judge.

    Deterministic: the gates are deterministic, so the same packet yields the
    same reward — exactly what RLVR/GRPO requires.
    """

    from hermes_cli.jarvis_prime import gates as _gates

    summary = _gates.run_gate_summary(
        packet,
        evidence_bundle=evidence_bundle,
        strict_evidence=strict_evidence,
    ).to_dict()
    return GateReward(
        reward=reward_from_gate_summary(summary),
        verifiable=verifiable_pass(summary),
        components=reward_components(summary),
        summary=summary,
    )


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
    return f'''"""Free GRPO with VERIFIABLE REWARDS = muse verification gates.

The reward runs the model's produced work through muse's gates and returns
``reward_from_gate_summary`` — no human/paid judge. Wire a real verifier (run
tests, scan secrets, score citations) inside ``gate_summary_for`` for your task.
"""
from unsloth import FastLanguageModel, is_bfloat16_supported
from trl import GRPOConfig, GRPOTrainer
from datasets import load_dataset

from hermes_cli.jarvis_prime.free_training import (
    reward_for_work, reward_from_gate_summary)

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name={base_model!r}, max_seq_length=4096, load_in_4bit=True,
    fast_inference=True, max_lora_rank=16)
model = FastLanguageModel.get_peft_model(model, r=16, lora_alpha=16)

dataset = load_dataset("json", data_files={dataset_path!r}, split="train")

def packet_for(prompt, completion):
    # WIRE THIS to your task: turn the model's completion into a muse work
    # packet (e.g. via natural_language_coder.build_work_packet, or by writing
    # the code to a sandbox and attaching captured evidence). reward_for_work
    # then runs the REAL gates (gates.run_gate_summary) and grades it — no
    # human/paid judge. The stub below rewards a non-empty, secret-free answer.
    return None

def gate_reward(prompts, completions, **kwargs):
    rewards = []
    for p, c in zip(prompts, completions):
        packet = packet_for(p, c)
        if packet is not None:
            rewards.append(reward_for_work(packet).reward)  # real gates
        else:
            failed = "fail" if (not c or "sk-" in c) else "pass"
            rewards.append(reward_from_gate_summary(
                {{"results": [{{"name": "test", "outcome": failed}},
                             {{"name": "security", "outcome": "pass"}}]}}))
    return rewards

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
    Colab/Kaggle T4 or a local GPU). For GRPO the reward is the muse gate
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


# Default ordered stages of one free, gated improvement cycle.
DEFAULT_LOOP_STAGES: tuple[TrainingStage, ...] = (
    TrainingStage.SFT,
    TrainingStage.ORPO,
    TrainingStage.GRPO,
)

# Stages that train on PREFERENCE rows ({prompt, chosen, rejected}) rather than
# the generic supervised rows SFT/GRPO consume. They need a different export.
PREFERENCE_STAGES: frozenset[TrainingStage] = frozenset(
    {TrainingStage.ORPO, TrainingStage.DPO}
)


@dataclass(frozen=True)
class FreeLoopReport:
    """Result of one harvest → export → recipe pass of the free loop.

    The loop does the **real local work** that does not need a GPU: it harvests
    the owner-approved traces from the learning dataset, exports the training
    set(s), and generates the runnable Unsloth+TRL recipes (one per stage). It
    then reports the eval + promotion plan.

    Two exports may be produced because the stages consume different shapes:
    SFT/GRPO read generic supervised rows (``export_jsonl``), while ORPO/DPO
    read preference rows ``{prompt, chosen, rejected}`` (``export_preference_pairs``).
    Each recipe is pointed at the matching dataset.

    Honest boundary: it does **not** train (there is no GPU in this process —
    the emitted recipes run on the free hardware you point them at) and it does
    **not** promote (promotion is measure-gated via
    ``model_scorecard.promotion_eligible`` and runs as its own owner-visible
    step — see :func:`jarvis_prime learning promote`).
    """

    harvested: int
    ready: bool
    dataset_path: str
    recipes: tuple[RecipeArtifact, ...]
    plan: FreeContinuousPlan
    preference_pairs: int = 0
    preference_dataset_path: Optional[str] = None
    written_to: Optional[str] = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "harvested": self.harvested,
            "ready": self.ready,
            "dataset_path": self.dataset_path,
            "preference_pairs": self.preference_pairs,
            "preference_dataset_path": self.preference_dataset_path,
            "recipes": [r.to_dict() for r in self.recipes],
            "plan": self.plan.to_dict(),
            "written_to": self.written_to,
            "notes": list(self.notes),
            "paid_api": False,
        }


def run_free_loop(
    *,
    store: Optional["DatasetStore"] = None,
    dataset_path: str | Path | None = None,
    base_model: str = DEFAULT_BASE_MODEL,
    out_dir: str = "data/models/free",
    stages: Sequence[TrainingStage] = DEFAULT_LOOP_STAGES,
    min_examples: int = 1,
    write_dir: str | Path | None = None,
) -> FreeLoopReport:
    """Run one harvest → export → recipe-generation pass of the free loop.

    Steps (all local, free, deterministic):

    1. **Harvest** owner-approved traces from the learning dataset
       (``DatasetStore.load()`` unless an explicit ``store`` is passed).
    2. **Export**, per shape the stages need:
       - SFT/GRPO get a generic supervised JSONL (``export_jsonl``).
       - ORPO/DPO get a preference JSONL ``{chosen, rejected, …}``
         (``export_preference_pairs``) — only produced when a preference stage
         is requested. Each recipe is pointed at its matching dataset so a
         generated ``train_orpo.py``/``train_dpo.py`` loads the columns TRL
         expects rather than the supervised rows.
    3. **Generate** a runnable Unsloth+TRL recipe per requested stage via
       :func:`generate_recipe`, optionally writing each script+config under
       ``write_dir``.

    ``ready`` is ``True`` only when at least ``min_examples`` approved traces
    were harvested — below that the recipes are still emitted (so the wiring is
    inspectable) but the report flags that more owner-approved data is needed
    before a run is worthwhile.
    """

    from hermes_cli.jarvis_prime.learning_dataset import (
        DatasetStore,
        default_dataset_path,
    )

    if store is None:
        store = DatasetStore.load()

    if dataset_path is None:
        dataset_path = default_dataset_path().with_name("free_loop_dataset.jsonl")
    dataset_path = Path(dataset_path)

    harvested = store.export_jsonl(dataset_path)

    # Only export the preference set when a stage actually consumes it.
    wants_preference = any(s in PREFERENCE_STAGES for s in stages)
    preference_pairs = 0
    preference_dataset_path: Optional[Path] = None
    if wants_preference:
        preference_dataset_path = dataset_path.with_name(
            dataset_path.stem + "_prefs.jsonl"
        )
        preference_pairs = store.export_preference_pairs(preference_dataset_path)

    def _dataset_for(stage: TrainingStage) -> Path:
        if stage in PREFERENCE_STAGES and preference_dataset_path is not None:
            return preference_dataset_path
        return dataset_path

    recipes = tuple(
        generate_recipe(
            _dataset_for(stage),
            stage=stage,
            base_model=base_model,
            out_dir=out_dir,
        )
        for stage in stages
    )

    written_to: Optional[str] = None
    if write_dir is not None:
        wd = Path(write_dir)
        for recipe in recipes:
            recipe.write(wd)
        written_to = str(wd)

    notes: list[str] = []
    if harvested < min_examples:
        notes.append(
            f"only {harvested} owner-approved trace(s) harvested "
            f"(want ≥{min_examples}); approve more before a real run."
        )
    if wants_preference and preference_pairs == 0:
        notes.append(
            "preference stage(s) requested but 0 preference pairs exist — "
            "ORPO/DPO need approved positives paired with a labeled negative "
            "on the same task_key; the emitted recipe(s) have an empty dataset."
        )
    notes.append(
        "recipes are generate-only — run them on free Colab/Kaggle T4 or a "
        "local GPU; this process does not train."
    )
    notes.append(
        "promotion is measure-gated: run `jarvis_prime learning promote` "
        "(model_scorecard.promotion_eligible) before any swap."
    )

    return FreeLoopReport(
        harvested=harvested,
        ready=harvested >= min_examples,
        dataset_path=str(dataset_path),
        recipes=recipes,
        plan=FreeContinuousPlan(base_model=base_model),
        preference_pairs=preference_pairs,
        preference_dataset_path=(
            str(preference_dataset_path) if preference_dataset_path else None
        ),
        written_to=written_to,
        notes=tuple(notes),
    )


__all__ = [
    "GATE_WEIGHTS",
    "reward_from_gate_summary",
    "reward_components",
    "verifiable_pass",
    "GateReward",
    "reward_for_work",
    "TrainingStage",
    "RecipeArtifact",
    "generate_recipe",
    "FreeContinuousPlan",
    "FreeLoopReport",
    "run_free_loop",
    "DEFAULT_BASE_MODEL",
    "DEFAULT_LOOP_STAGES",
    "PREFERENCE_STAGES",
]
