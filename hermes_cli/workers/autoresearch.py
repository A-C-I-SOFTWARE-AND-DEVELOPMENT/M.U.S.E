"""Autoresearch worker adapter — Karpathy's training loop as a Hermes worker.

autoresearch (https://github.com/karpathy/autoresearch, MIT — vendored
byte-identical at ``hermes_cli/jarvis_prime/research_fabric/autoresearch/
vendor/``) is an autonomous pretraining experiment loop: edit ``train.py``,
train for a fixed 5-minute budget, read ``val_bpb`` (lower is better), keep or
git-reset, repeat. This adapter runs that loop **inside a disposable
workspace** under ``$HERMES_HOME/autoresearch/`` via the governed driver
(:mod:`...research_fabric.autoresearch.engine` — cost ceiling, watchdog, VRAM
feasibility, flywheel provenance) and drives it through the standard
five-step contract (``detect → prepare_prompt → run → collect → score``).

Promotion of a winning ``train.py`` is **not** done here — it is owner-gated
via :mod:`hermes_cli.jarvis_prime.autoresearch_improve`, which reuses the SIA
``run_self_improvement`` orchestration (benchmark gate → RC4 proposal →
``NEEDS_OWNER_APPROVAL``). This module only produces and scores candidates.

Live spawning is opt-in via ``MUSE_AUTORESEARCH_ALLOW_SPAWN=1`` (the ue5.py
pattern); without it ``detect()`` reports unavailable and nothing runs. torch
is never imported at module import time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from hermes_cli.workers.base import (
    WorkerAdapter,
    WorkerArtifacts,
    WorkerDetection,
    WorkerPrompt,
    WorkerRunResult,
    WorkerScore,
    detect_command,
)
from hermes_cli.workers.registry import register

WORKER_NAME = "autoresearch"
SPAWN_ENV = "MUSE_AUTORESEARCH_ALLOW_SPAWN"
DATA_CACHE = Path("~/.cache/autoresearch").expanduser()  # prepare.py's CACHE_DIR


def _spawn_allowed() -> bool:
    return os.environ.get(SPAWN_ENV, "").strip() == "1"


@dataclass
class AutoresearchWorkerConfig:
    """Everything a run needs; tests inject fakes for every seam."""

    experiment: Any  # engine.ExperimentConfig (typed loosely: lazy import)
    propose_edit: Optional[Any] = None  # engine.EditProvider — required live
    subprocess_runner: Optional[Any] = None
    git_runner: Optional[Any] = None
    data_cache: Path = DATA_CACHE


class AutoresearchWorker(WorkerAdapter):
    id = WORKER_NAME
    display_name = "Autoresearch (autonomous pretraining loop)"

    def __init__(
        self,
        repo_root: str = ".",
        config: Optional[AutoresearchWorkerConfig] = None,
    ) -> None:
        self.repo_root = repo_root
        self.config = config
        self._run_result: Optional[Any] = None  # engine.AutoresearchRun

    # ── five-step contract ───────────────────────────────────────────────

    def detect(self) -> WorkerDetection:
        """Fail-closed availability: owner gate, launcher, data, device."""

        if not _spawn_allowed():
            return WorkerDetection(
                available=False,
                reason=f"live spawning is owner-gated: set {SPAWN_ENV}=1",
            )
        if not detect_command("uv"):
            return WorkerDetection(
                available=False, reason="`uv` not on PATH (engine launcher)"
            )
        cache = self.config.data_cache if self.config else DATA_CACHE
        tokenizer = Path(cache) / "tokenizer" / "tokenizer.pkl"
        data_dir = Path(cache) / "data"
        if not tokenizer.exists() or not data_dir.is_dir() or not any(data_dir.glob("*.parquet")):
            return WorkerDetection(
                available=False,
                reason=(
                    f"training data/tokenizer missing under {cache} — run "
                    "`uv run prepare.py` in a seeded workspace on owner hardware "
                    "(downloads from Hugging Face)"
                ),
            )
        device = self.config.experiment.device if self.config else "cuda:0"
        if str(device).startswith("modal"):
            return WorkerDetection(
                available=True, reason=f"modal lane {device}", details={"device": device}
            )
        from hermes_cli.jarvis_prime.research_fabric.autoresearch import platform as ar_platform

        profile = ar_platform.detect()
        if profile is None:
            return WorkerDetection(
                available=False, reason="no CUDA device detected (torch/cuda unavailable)"
            )
        return WorkerDetection(
            available=True,
            reason=f"{profile.name} (sm_{profile.capability[0]}{profile.capability[1]})",
            details={
                "device": device,
                "name": profile.name,
                "total_vram_mb": profile.total_vram_mb,
                "fa3_repo": profile.fa3_repo,
            },
        )

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        """Vendored program.md + the muse governance addendum."""

        from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import VENDOR_DIR

        program = (VENDOR_DIR / "program.md").read_text(encoding="utf-8")
        cfg = self.config.experiment if self.config else None
        addendum_lines = [
            "",
            "## muse governance addendum (supersedes the loop above where they conflict)",
            "",
            "- muse's cost ceiling SUPERSEDES 'NEVER STOP': the run halts at",
        ]
        if cfg is not None:
            addendum_lines += [
                f"  max_experiments={cfg.max_experiments}, "
                f"max_wall_clock_seconds={cfg.max_wall_clock_seconds:.0f}, "
                f"max_cost_usd={cfg.max_cost_usd:.2f} — whichever hits first.",
                f"- VRAM budget: {cfg.vram_budget_mb:.0f} MB — over-budget runs are",
                "  infeasible (reset, never champion).",
                f"- Branch: {cfg.resolved_branch()} inside the disposable workspace",
                f"  {cfg.resolved_workspace()} — the muse repo is never touched.",
            ]
        addendum_lines += [
            "- Every experiment is recorded to the muse flywheel; results.tsv is a",
            "  local mirror only.",
            "- Nothing is ever promoted without the owner's explicit approval.",
        ]
        objective = getattr(job, "objective", "") or getattr(job, "prompt", "")
        return WorkerPrompt(
            text=program + "\n".join(addendum_lines) + "\n",
            role="autoresearch-loop",
            metadata={"objective": objective},
        )

    def run(self, job: Any) -> WorkerRunResult:
        detection = self.detect()  # fail-closed re-check at run time
        if not detection.available:
            return WorkerRunResult(ok=False, error=detection.reason)
        if self.config is None:
            return WorkerRunResult(
                ok=False, error="no worker config — autoresearch needs an ExperimentConfig"
            )
        from hermes_cli.jarvis_prime.research_fabric.autoresearch import (
            engine as ar_engine,
        )
        from hermes_cli.jarvis_prime.research_fabric.autoresearch import (
            platform as ar_platform,
        )

        propose_edit = self.config.propose_edit
        if propose_edit is None:
            # Built-in idea source: the deterministic knob catalog (ideas.py).
            from hermes_cli.jarvis_prime.research_fabric.autoresearch.ideas import (
                default_edit_provider,
            )

            propose_edit = default_edit_provider()

        try:
            profile = (
                None
                if str(self.config.experiment.device).startswith("modal")
                else ar_platform.detect()
            )
            run = ar_engine.run_experiment_loop(
                self.config.experiment,
                propose_edit=propose_edit,
                subprocess_runner=self.config.subprocess_runner,
                git_runner=self.config.git_runner,
                profile=profile,
            )
        except Exception as exc:  # the host never sees engine exceptions
            return WorkerRunResult(ok=False, error=f"{type(exc).__name__}: {exc}")
        self._run_result = run
        # A completed loop with no improvement is still a successful run —
        # the benchmark gate (not the worker) decides whether it was a win.
        return WorkerRunResult(
            ok=True,
            duration_seconds=run.finished_at - run.started_at,
            details={"stopped_reason": run.stopped_reason},
        )

    def collect(self, job: Any) -> WorkerArtifacts:
        run = self._run_result
        if run is None:
            return WorkerArtifacts(notes="no run recorded")
        from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import (
            bpb_gate_score,
        )

        champion = run.champion
        generations = [
            {
                "gen": r.index,
                "score": bpb_gate_score(r.val_bpb) if r.val_bpb is not None else 0.0,
                "target_agent": str(Path(run.workspace_path) / "train.py"),
                "improvement": run.results_tsv_path,
                "execution": "",
            }
            for r in run.results
        ]
        baseline_bpb = run.config.baseline_bpb
        if baseline_bpb is None and run.baseline is not None:
            baseline_bpb = run.baseline.val_bpb
        return WorkerArtifacts(
            workspace_path=run.workspace_path,
            logs=(str(Path(run.workspace_path) / "run.log"),),
            details={
                # keys run_self_improvement reads:
                "best_gen": champion.index if champion else None,
                "generations": generations,
                # autoresearch-specific provenance:
                "experiments": [r.to_dict() for r in run.results],
                "champion": champion.to_dict() if champion else None,
                "best_infeasible": (
                    run.best_infeasible.to_dict() if run.best_infeasible else None
                ),
                "baseline_bpb": baseline_bpb,
                "results_tsv": run.results_tsv_path,
                "total_cost_usd": run.total_cost_usd,
                "stopped_reason": run.stopped_reason,
                "branch": run.config.resolved_branch(),
                "device": run.config.device,
                "tag": run.config.tag,
            },
        )

    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        details = dict(artifacts.details or {})
        champion = details.get("champion")
        if not champion or champion.get("val_bpb") is None:
            reason = details.get("stopped_reason", "no run")
            infeasible = details.get("best_infeasible")
            if infeasible:
                reason = f"best result infeasible: {infeasible.get('reason', '')}"
            return WorkerScore(value=0.0, confidence=0.0, rationale=reason)
        from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import (
            bpb_gate_score,
        )

        val_bpb = float(champion["val_bpb"])
        experiments = details.get("experiments") or []
        completed = sum(1 for e in experiments if e.get("val_bpb") is not None)
        components: dict[str, float] = {}
        peak = champion.get("peak_vram_mb")
        budget = getattr(self.config.experiment, "vram_budget_mb", 0.0) if self.config else 0.0
        if peak is not None and budget:
            components["vram_headroom"] = max(0.0, min(1.0, 1.0 - float(peak) / budget))
        cost_ceiling = (
            getattr(self.config.experiment, "max_cost_usd", 0.0) if self.config else 0.0
        )
        if cost_ceiling > 0:
            spent = float(details.get("total_cost_usd") or 0.0)
            components["cost_utilization"] = max(0.0, min(1.0, 1.0 - spent / cost_ceiling))
        return WorkerScore(
            value=bpb_gate_score(val_bpb),
            confidence=min(1.0, completed / 8.0),
            rationale=(
                f"champion val_bpb={val_bpb:.6f} (raw, lower is better) at "
                f"commit {champion.get('commit')} after {completed} completed "
                f"experiment(s); gate score is the bounded transform 1/(1+bpb)"
            ),
            components=components,
        )


# Self-register on import so the orchestrator can dispatch to it. ``replace``
# keeps re-imports (tests, reloads) idempotent.
register(AutoresearchWorker(), replace=True)
