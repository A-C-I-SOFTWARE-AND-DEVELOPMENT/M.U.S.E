"""Governed driver for the LLM-JEPA fine-tune experiment (torch-free).

This module is the muse-side control plane for the vendored ``train.py`` loop.
It never imports torch: it plans runs, seeds disposable workspaces, invokes the
vendored trainer via ``uv run`` (injectable for tests), parses its summary, and
disposes of the result through the same benchmark gate the rest of MUSE uses
(:func:`hermes_cli.jarvis_prime.benchmark_gate.evaluate_improvement`).

Governance mirrors the autoresearch engine:

* **dry-run by default** — :func:`plan_finetune` describes the run without
  touching a GPU; callers must opt in to a live run.
* **owner-gated live spawn** — a live run requires the caller to pass
  ``allow_spawn=True`` (the worker maps this to ``MUSE_LLM_JEPA_ALLOW_SPAWN``).
* **promotion is a proposal, never an apply** — a winning objective is an RC4
  ``SELF_RUNTIME_UPDATE`` proposal that lands as ``NEEDS_OWNER_APPROVAL``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

VENDOR_DIR = Path(__file__).resolve().parent / "vendor"

# The JEPA loss adds ~2x compute; loss-dropout (LD) recovers most of it. The
# report's LD=0.75 => ~1.25x. This is documentation for the plan summary only.
_JEPA_COMPUTE_MULTIPLIER_FULL = 2.0

SubprocessRunner = Callable[..., "subprocess.CompletedProcess[str]"]


def _default_workspace_root() -> Path:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "llm_jepa" / "workspaces"


@dataclass
class JepaFinetuneConfig:
    """Everything a fine-tune run needs. Small defaults so it fits 12 GB."""

    tag: str = "jepa"
    base_model: str = "Qwen/Qwen2.5-0.5B"  # <=1B for a 12 GB box
    lora_rank: int = 512  # LoRA at r=512 matched full FT in the paper
    jepa_lambda: float = 0.5
    jepa_loss_dropout: float = 0.75  # LD=0.75 -> ~1.25x compute
    epochs: int = 1
    max_pairs: int = 512
    eval_holdout: float = 0.2
    seed: int = 0
    device: str = "cuda:0"
    load_in_8bit: bool = True
    task: str = "llm_jepa_finetune"
    min_margin: float = 0.02
    workspace_root: Optional[Path] = None
    uv_argv: Sequence[str] = ("uv", "run", "train.py")
    watchdog_seconds: float = 3600.0

    def resolved_workspace(self) -> Path:
        root = self.workspace_root or _default_workspace_root()
        return Path(root) / self.tag

    def compute_multiplier(self) -> float:
        """Effective compute vs a plain fine-tune, given loss-dropout."""

        keep = max(0.0, min(1.0, 1.0 - self.jepa_loss_dropout))
        # Baseline next-token pass is always paid; the JEPA aux pass is paid on
        # the kept fraction of steps.
        return 1.0 + keep


@dataclass
class JepaFinetuneResult:
    """Parsed outcome of one vendored trainer invocation."""

    baseline_accuracy: Optional[float] = None
    jepa_accuracy: Optional[float] = None
    status: str = "unknown"  # keep | no_improvement | crash | killed | plan
    workspace_path: str = ""
    log_path: str = ""
    stdout_tail: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_accuracy": self.baseline_accuracy,
            "jepa_accuracy": self.jepa_accuracy,
            "status": self.status,
            "workspace_path": self.workspace_path,
            "log_path": self.log_path,
            "details": self.details,
        }


def jepa_gate_score(accuracy: Optional[float]) -> float:
    """Map a downstream accuracy into the gate's bounded ``[0, 1]`` space.

    Accuracy is already higher-is-better in ``[0, 1]``; this clamps and treats
    a missing value as 0.0 so a crashed run can never look like a win. Kept as
    a named transform to parallel autoresearch's ``bpb_gate_score``.
    """

    if accuracy is None:
        return 0.0
    return max(0.0, min(1.0, float(accuracy)))


_SUMMARY_KEYS = ("baseline_accuracy", "jepa_accuracy")


def parse_summary(log_text: str) -> dict[str, float]:
    """Extract ``key: float`` summary lines emitted by the vendored trainer."""

    found: dict[str, float] = {}
    for key in _SUMMARY_KEYS:
        m = re.search(rf"^{key}:\s*([0-9]*\.?[0-9]+)\s*$", log_text, re.MULTILINE)
        if m:
            try:
                found[key] = float(m.group(1))
            except ValueError:
                pass
    return found


def plan_finetune(config: JepaFinetuneConfig, n_pairs: int) -> dict[str, Any]:
    """Describe a run without touching a GPU (the dry-run default)."""

    return {
        "mode": "plan",
        "objective": "L = L_LLM + lambda * d(Pred(Enc(text)), Enc(code))",
        "base_model": config.base_model,
        "lora_rank": config.lora_rank,
        "jepa_lambda": config.jepa_lambda,
        "jepa_loss_dropout": config.jepa_loss_dropout,
        "effective_compute_multiplier": round(config.compute_multiplier(), 3),
        "n_pairs": n_pairs,
        "n_train": int(n_pairs * (1.0 - config.eval_holdout)),
        "n_eval": n_pairs - int(n_pairs * (1.0 - config.eval_holdout)),
        "device": config.device,
        "workspace": str(config.resolved_workspace()),
        "gate": {
            "metric": "downstream_accuracy",
            "task": config.task,
            "min_margin": config.min_margin,
        },
        "summary": (
            f"plan-only: JEPA fine-tune of {config.base_model} (LoRA r="
            f"{config.lora_rank}, lambda={config.jepa_lambda}, LD="
            f"{config.jepa_loss_dropout} ~"
            f"{config.compute_multiplier():.2f}x compute) on {n_pairs} "
            f"(text, code) pairs vs a baseline fine-tune, gated by "
            f"evaluate_improvement(min_margin={config.min_margin})."
        ),
    }


def seed_workspace(config: JepaFinetuneConfig, pairs_jsonl: Path) -> Path:
    """Copy the vendored harness into a disposable workspace + drop the pairs.

    The muse tree's ``vendor/`` is never mutated; the trainer only ever edits
    files inside this workspace copy (the autoresearch discipline).
    """

    ws = config.resolved_workspace()
    ws.mkdir(parents=True, exist_ok=True)
    for item in VENDOR_DIR.iterdir():
        if item.is_file():
            shutil.copy2(item, ws / item.name)
    dest_pairs = ws / "pairs.jsonl"
    if Path(pairs_jsonl) != dest_pairs:
        shutil.copy2(pairs_jsonl, dest_pairs)
    return ws


def run_finetune(
    config: JepaFinetuneConfig,
    pairs_jsonl: Path,
    *,
    allow_spawn: bool,
    runner: Optional[SubprocessRunner] = None,
) -> JepaFinetuneResult:
    """Run the vendored trainer in a workspace (owner-gated live spawn).

    With ``allow_spawn=False`` this is a hard no-op that returns a ``plan``
    status — nothing is trained. With ``allow_spawn=True`` it seeds a workspace
    and invokes ``uv run train.py`` (or an injected ``runner`` in tests),
    parsing ``baseline_accuracy`` / ``jepa_accuracy`` from the log.
    """

    if not allow_spawn:
        return JepaFinetuneResult(status="plan", details={"reason": "spawn not allowed"})

    ws = seed_workspace(config, pairs_jsonl)
    argv = list(config.uv_argv) + [
        "--pairs", "pairs.jsonl",
        "--model", config.base_model,
        "--lora-rank", str(config.lora_rank),
        "--jepa-lambda", str(config.jepa_lambda),
        "--jepa-dropout", str(config.jepa_loss_dropout),
        "--epochs", str(config.epochs),
        "--eval-holdout", str(config.eval_holdout),
        "--seed", str(config.seed),
    ]
    run = runner or subprocess.run
    try:
        completed = run(
            argv,
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=config.watchdog_seconds,
        )
    except subprocess.TimeoutExpired:
        return JepaFinetuneResult(
            status="killed", workspace_path=str(ws), details={"reason": "watchdog"}
        )
    except Exception as exc:  # never surface a raw subprocess error to the host
        return JepaFinetuneResult(
            status="crash",
            workspace_path=str(ws),
            details={"reason": f"{type(exc).__name__}: {exc}"},
        )

    stdout = getattr(completed, "stdout", "") or ""
    stderr = getattr(completed, "stderr", "") or ""
    log_text = stdout + "\n" + stderr
    log_path = ws / "run.log"
    try:
        log_path.write_text(log_text, encoding="utf-8")
    except OSError:
        pass
    if getattr(completed, "returncode", 1) != 0:
        return JepaFinetuneResult(
            status="crash",
            workspace_path=str(ws),
            log_path=str(log_path),
            stdout_tail=stdout[-2000:],
            details={"returncode": getattr(completed, "returncode", 1)},
        )
    summary = parse_summary(log_text)
    base = summary.get("baseline_accuracy")
    jepa = summary.get("jepa_accuracy")
    status = "keep" if (base is not None and jepa is not None and jepa > base) else "no_improvement"
    return JepaFinetuneResult(
        baseline_accuracy=base,
        jepa_accuracy=jepa,
        status=status,
        workspace_path=str(ws),
        log_path=str(log_path),
        stdout_tail=stdout[-2000:],
        details={"summary": summary},
    )


def evaluate_finetune(result: JepaFinetuneResult, config: JepaFinetuneConfig) -> Any:
    """Dispose of a result through the shared benchmark gate.

    Returns the ``GateResult`` from ``evaluate_improvement`` comparing the
    baseline fine-tune vs the JEPA fine-tune on downstream accuracy (higher is
    better). Missing scores -> SKIPPED (never a false win).
    """

    from hermes_cli.jarvis_prime.benchmark_gate import evaluate_improvement

    ran = result.baseline_accuracy is not None and result.jepa_accuracy is not None
    return evaluate_improvement(
        jepa_gate_score(result.baseline_accuracy),
        jepa_gate_score(result.jepa_accuracy),
        task=config.task,
        min_margin=config.min_margin,
        benchmark_ran=ran,
    )


def propose_promotion(
    book: Any,
    config: JepaFinetuneConfig,
    result: JepaFinetuneResult,
    gate: Any,
) -> Optional[Any]:
    """Queue an RC4 owner-gated proposal iff the gate PASSed. Else return None.

    The promotion target is the vendored ``train.py`` (a runtime surface), so
    it maps to ``SELF_RUNTIME_UPDATE`` / RC4 and lands as
    ``NEEDS_OWNER_APPROVAL`` — a worker never applies it.
    """

    from hermes_cli.jarvis_prime.gates import GateOutcome
    from hermes_cli.jarvis_prime.self_update import (
        ProposalEvidence,
        ProposalKind,
    )

    if getattr(gate, "outcome", None) is not GateOutcome.PASS:
        return None
    evidence = (
        ProposalEvidence(
            kind="research_finding",
            text=(
                f"JEPA fine-tune beat baseline on {config.task}: "
                f"accuracy {result.baseline_accuracy} -> {result.jepa_accuracy} "
                f"(margin >= {config.min_margin})."
            ),
            citation=result.log_path or config.resolved_workspace().as_posix(),
        ),
    )
    return book.propose(
        kind=ProposalKind.SELF_RUNTIME_UPDATE,
        target_path=str(VENDOR_DIR / "train.py"),
        rationale=(
            "The LLM-JEPA objective outperformed a plain fine-tune on MUSE's own "
            "(text, code) history; consider adopting it as a training variant."
        ),
        diff_intent=(
            "Adopt the JEPA auxiliary loss (lambda="
            f"{config.jepa_lambda}, LD={config.jepa_loss_dropout}) for the "
            "fine-tune lane, pending owner review."
        ),
        evidence=evidence,
        risk_class="RC4",
    )
