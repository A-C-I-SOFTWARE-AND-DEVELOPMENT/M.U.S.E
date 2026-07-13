"""LLM-JEPA worker adapter — the JEPA fine-tune objective as a Hermes worker.

Runs the LLM-JEPA fine-tune experiment (clean-room implementation of
arXiv 2509.14252, vendored at
``hermes_cli/jarvis_prime/research_fabric/llm_jepa/vendor/``) through the
standard five-step contract (``detect -> prepare_prompt -> run -> collect ->
score``). It trains a small (<=1B) base model twice on MUSE's own
``(text, code)`` history — a baseline fine-tune vs a JEPA-objective fine-tune —
and scores the JEPA run so the benchmark gate can decide whether it beat
baseline.

Governance (mirrors the autoresearch worker):

* **dry-run by default** — with ``dry_run=True`` (the default) the worker only
  produces a plan; nothing trains and ``detect`` is always available.
* **owner-gated live spawn** — a live run needs ``dry_run=False`` AND
  ``MUSE_LLM_JEPA_ALLOW_SPAWN=1``; otherwise ``detect`` reports unavailable.
* **promotion is never done here** — a winning objective becomes an RC4
  ``SELF_RUNTIME_UPDATE`` proposal (``engine.propose_promotion``) that lands as
  ``NEEDS_OWNER_APPROVAL``. torch is never imported at module import time.
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

WORKER_NAME = "llm-jepa"
SPAWN_ENV = "MUSE_LLM_JEPA_ALLOW_SPAWN"


def _spawn_allowed() -> bool:
    return os.environ.get(SPAWN_ENV, "").strip() == "1"


@dataclass
class LlmJepaWorkerConfig:
    """Everything a run needs; tests inject fakes for every seam."""

    finetune: Any  # engine.JepaFinetuneConfig (loose type: lazy import)
    pairs_jsonl: Optional[Path] = None
    dry_run: bool = True
    subprocess_runner: Optional[Any] = None

    def n_pairs(self) -> int:
        if not self.pairs_jsonl or not Path(self.pairs_jsonl).exists():
            return 0
        from hermes_cli.jarvis_prime.research_fabric.llm_jepa.views import (
            views_from_jsonl,
        )

        return len(views_from_jsonl(Path(self.pairs_jsonl)))


class LlmJepaWorker(WorkerAdapter):
    id = WORKER_NAME
    display_name = "LLM-JEPA (JEPA fine-tune objective)"

    def __init__(
        self,
        repo_root: str = ".",
        config: Optional[LlmJepaWorkerConfig] = None,
    ) -> None:
        self.repo_root = repo_root
        self.config = config
        self._result: Optional[Any] = None  # engine.JepaFinetuneResult

    def _dry_run(self) -> bool:
        return self.config.dry_run if self.config else True

    # ── five-step contract ───────────────────────────────────────────────

    def detect(self) -> WorkerDetection:
        if self._dry_run():
            return WorkerDetection(
                available=True,
                reason=(
                    "plan-only (dry run); set dry_run=False + "
                    f"{SPAWN_ENV}=1 to train on owner hardware"
                ),
                details={"mode": "plan"},
            )
        if not _spawn_allowed():
            return WorkerDetection(
                available=False,
                reason=f"live spawning is owner-gated: set {SPAWN_ENV}=1",
            )
        if not detect_command("uv"):
            return WorkerDetection(
                available=False, reason="`uv` not on PATH (engine launcher)"
            )
        return WorkerDetection(available=True, reason="live fine-tune enabled")

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        from hermes_cli.jarvis_prime.research_fabric.llm_jepa.engine import VENDOR_DIR

        program = (VENDOR_DIR / "program.md").read_text(encoding="utf-8")
        objective = getattr(job, "objective", "") or getattr(job, "prompt", "")
        return WorkerPrompt(
            text=program,
            role="llm-jepa-finetune",
            metadata={"objective": objective},
        )

    def run(self, job: Any) -> WorkerRunResult:
        if self.config is None:
            return WorkerRunResult(
                ok=False, error="no worker config — llm-jepa needs a JepaFinetuneConfig"
            )
        from hermes_cli.jarvis_prime.research_fabric.llm_jepa.engine import (
            JepaFinetuneResult,
            plan_finetune,
            run_finetune,
        )

        ft = self.config.finetune
        n_pairs = self.config.n_pairs()

        if self._dry_run():
            plan = plan_finetune(ft, n_pairs)
            self._result = JepaFinetuneResult(status="plan", details={"plan": plan})
            return WorkerRunResult(ok=True, details={"mode": "plan", **plan})

        detection = self.detect()  # fail-closed re-check at run time
        if not detection.available:
            return WorkerRunResult(ok=False, error=detection.reason)
        if not self.config.pairs_jsonl:
            return WorkerRunResult(ok=False, error="no (text, code) pairs to train on")

        result = run_finetune(
            ft,
            Path(self.config.pairs_jsonl),
            allow_spawn=True,
            runner=self.config.subprocess_runner,
        )
        self._result = result
        return WorkerRunResult(
            ok=result.status not in ("crash", "killed"),
            error="" if result.status not in ("crash", "killed") else str(result.details),
            details=result.to_dict(),
        )

    def collect(self, job: Any) -> WorkerArtifacts:
        result = self._result
        if result is None:
            return WorkerArtifacts(notes="no run recorded")
        details = dict(result.to_dict())
        details["mode"] = "plan" if result.status == "plan" else "train"
        logs = (result.log_path,) if getattr(result, "log_path", "") else ()
        return WorkerArtifacts(
            workspace_path=getattr(result, "workspace_path", ""),
            logs=logs,
            details=details,
        )

    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        from hermes_cli.jarvis_prime.research_fabric.llm_jepa.engine import (
            jepa_gate_score,
        )

        details = dict(artifacts.details or {})
        if details.get("mode") == "plan" or details.get("status") == "plan":
            return WorkerScore(
                value=0.0,
                confidence=0.0,
                rationale="plan-only dry run; no training performed",
            )
        jepa = details.get("jepa_accuracy")
        base = details.get("baseline_accuracy")
        if jepa is None:
            return WorkerScore(
                value=0.0,
                confidence=0.0,
                rationale=f"no metrics (status={details.get('status')})",
            )
        components = {}
        if base is not None:
            components["baseline"] = jepa_gate_score(base)
        return WorkerScore(
            value=jepa_gate_score(jepa),
            confidence=1.0 if base is not None else 0.5,
            rationale=(
                f"jepa fine-tune downstream accuracy={jepa} vs baseline={base}; "
                "the benchmark gate decides promotion"
            ),
            components=components,
        )


# Self-register on import so the orchestrator can dispatch to it. ``replace``
# keeps re-imports (tests, reloads) idempotent.
register(LlmJepaWorker(), replace=True)
