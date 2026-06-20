"""Background-learner job handlers (LEARN-1).

Implements the *live* behavior for allowed job kinds — but every effect is
**read-mostly or proposal-only**. Anything that would change code/skills/durable
memory is routed through the EXISTING owner-approval gate
(`hermes_cli/jarvis_prime/self_update.py::ProposalBook`) as a pending Proposal;
nothing is ever applied here. Disallowed kinds never reach the runner (the queue
rejects them at enqueue).

Wiring: construct a `JobQueue(executor=BackgroundLearnerRunner(...).handle)` and
call `queue.drain()` from an idle hook (e.g. the cron scheduler tick). See
`run_idle_cycle` for a ready-made entry point.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from hermes_cli.jarvis_prime.self_update import (
    Proposal,
    ProposalBook,
    ProposalEvidence,
    ProposalKind,
)

from .queue import ALLOWED_KINDS, Job, JobQueue

logger = logging.getLogger(__name__)


@dataclass
class JobOutcome:
    job_id: int
    kind: str
    status: str  # "ran" | "proposed" | "skipped" | "error"
    detail: str = ""
    proposal: Optional[Proposal] = None


class BackgroundLearnerRunner:
    """Maps allowed job kinds to safe handlers.

    `book` is the owner-approval ProposalBook for proposal-emitting kinds. An
    `eval_fn` (defaults to the EVAL-1 harness) backs `evaluate_model_routing` /
    `run_local_benchmark`. No handler performs any external/network/side effect.
    """

    def __init__(
        self,
        book: Optional[ProposalBook] = None,
        eval_fn: Optional[Callable[..., Any]] = None,
        autoresearch_fn: Optional[Callable[..., Any]] = None,
    ):
        self.book = book or ProposalBook()
        self._eval_fn = eval_fn
        self._autoresearch_fn = autoresearch_fn

    # ── dispatch ─────────────────────────────────────────────────────────
    def handle(self, job: Job) -> JobOutcome:
        handler = getattr(self, f"_h_{job.kind}", None)
        if handler is None:
            # Allowed but no live handler yet → safe no-op (still auditable).
            return JobOutcome(job.id, job.kind, "skipped", "no live handler; dry-noop")
        try:
            return handler(job)
        except Exception as err:  # never propagate into the queue loop
            logger.warning("[background-learner] handler %s failed: %s", job.kind, err)
            return JobOutcome(job.id, job.kind, "error", str(err))

    # ── read-mostly handlers (no external effect) ────────────────────────
    def _h_scan_outdated_deps(self, job: Job) -> JobOutcome:
        # Read-only: counts declared deps; never installs or upgrades.
        from pathlib import Path

        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        n = 0
        try:
            n = sum(1 for ln in pyproject.read_text(encoding="utf-8").splitlines() if "==" in ln)
        except OSError:
            pass
        return JobOutcome(job.id, job.kind, "ran", f"scanned ~{n} pinned dep lines (read-only)")

    def _h_summarize_session(self, job: Job) -> JobOutcome:
        # Local heuristic summary of provided text; no model call, no storage.
        text = str(job.payload.get("text", ""))
        lines = [ln for ln in text.splitlines() if ln.strip()]
        head = lines[:3]
        summary = " / ".join(head) if head else "(empty session)"
        return JobOutcome(job.id, job.kind, "ran", f"summary: {summary[:200]}")

    def _h_evaluate_model_routing(self, job: Job) -> JobOutcome:
        worker_id = str(job.payload.get("worker_id", "unknown"))
        run_suite = self._eval_fn or self._default_eval
        report = run_suite(worker_id)
        passed = getattr(report, "passed", False)
        return JobOutcome(job.id, job.kind, "ran", f"eval worker={worker_id} passed={passed}")

    def _h_run_local_benchmark(self, job: Job) -> JobOutcome:
        return self._h_evaluate_model_routing(job)

    @staticmethod
    def _default_eval(worker_id: str):
        from hermes_cli.evals import run_suite

        return run_suite(worker_id, threshold=0.7)

    # ── proposal-only handlers (owner-gated; never applied) ──────────────
    def _h_propose_code_patch(self, job: Job) -> JobOutcome:
        target = str(job.payload.get("target_path", "UNKNOWN"))
        rationale = str(job.payload.get("rationale", "background learner suggestion"))
        intent = str(job.payload.get("diff_intent", "(high-level change description)"))
        p = self.book.propose(
            kind=ProposalKind.SELF_RUNTIME_UPDATE,
            target_path=target,
            rationale=rationale,
            diff_intent=intent,
            evidence=(ProposalEvidence(kind="research_finding", text="auto-proposed by background learner"),),
            risk_class="RC3",  # RC3+ ⇒ NEEDS_OWNER_APPROVAL
        )
        return JobOutcome(job.id, job.kind, "proposed", f"proposal for {target}", proposal=p)

    def _h_autoresearch_train(self, job: Job) -> JobOutcome:
        """Nightly autoresearch runs — plan-only unless EVERY gate is open.

        payload: {"tag": str (required), "objective": str, "lanes": int |
        [{"device": str, "cost_per_hour_usd": float}], "max_experiments": int,
        "max_wall_clock_seconds": float, "max_cost_usd": float,
        "vram_budget_mb": float, "baseline_bpb": float, "min_bpb_delta": float}

        dry_run (the default; non-dry_run already required an approval token
        at enqueue) => a pure plan report, nothing spawned. A live run
        additionally requires ``muse_AUTORESEARCH_ALLOW_SPAWN=1``; when the
        env gate is closed the job degrades to plan-only and says so.
        """

        import os

        from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import (
            ExperimentConfig,
        )
        from hermes_cli.jarvis_prime.research_fabric.autoresearch.swarm import (
            LaneSpec,
            plan_swarm,
        )

        payload = job.payload or {}
        tag = str(payload.get("tag", "")).strip()
        if not tag:
            return JobOutcome(job.id, job.kind, "error", "payload.tag is required")

        base_config = ExperimentConfig(
            tag=tag,
            objective=str(payload.get("objective", "minimize val_bpb")),
            max_experiments=int(payload.get("max_experiments", 12)),
            max_wall_clock_seconds=float(
                payload.get("max_wall_clock_seconds", 4 * 3600.0)
            ),
            max_cost_usd=float(payload.get("max_cost_usd", 0.0)),
            vram_budget_mb=float(payload.get("vram_budget_mb", 0.0)),
        )
        lanes_spec = payload.get("lanes", 1)
        if isinstance(lanes_spec, list):
            lanes: Any = [
                LaneSpec(
                    device=str(lane.get("device", "cuda:0")),
                    cost_per_hour_usd=float(lane.get("cost_per_hour_usd", 0.0)),
                )
                for lane in lanes_spec
            ]
        else:
            lanes = int(lanes_spec)
        plan = plan_swarm(tag, lanes, base_config=base_config)

        if job.dry_run:
            return JobOutcome(
                job.id, job.kind, "ran", f"plan-only (dry_run): {plan.summary()}"
            )
        if os.environ.get("muse_AUTORESEARCH_ALLOW_SPAWN", "").strip() != "1":
            return JobOutcome(
                job.id,
                job.kind,
                "ran",
                "plan-only: live run blocked — muse_AUTORESEARCH_ALLOW_SPAWN "
                f"is not set to 1. {plan.summary()}",
            )
        baseline_bpb = payload.get("baseline_bpb")
        if self._autoresearch_fn is None and baseline_bpb is None:
            # The built-in runner gates on a known baseline; an injected
            # runner may establish its own.
            return JobOutcome(
                job.id,
                job.kind,
                "ran",
                "plan-only: payload.baseline_bpb is required for a live run — "
                f"establish it with an unedited baseline run first. {plan.summary()}",
            )
        run_fn = self._autoresearch_fn or _default_autoresearch_swarm
        outcome = run_fn(
            plan,
            book=self.book,
            baseline_bpb=float(baseline_bpb) if baseline_bpb is not None else None,
            min_bpb_delta=float(payload.get("min_bpb_delta", 0.0)),
        )
        proposal = getattr(
            getattr(outcome, "proposal_outcome", None), "proposal", None
        )
        if proposal is not None:
            return JobOutcome(
                job.id,
                job.kind,
                "proposed",
                f"swarm '{tag}' produced an owner-gated proposal",
                proposal=proposal,
            )
        return JobOutcome(
            job.id, job.kind, "ran", f"swarm '{tag}' completed without a promotable champion"
        )

    def _h_propose_skill(self, job: Job) -> JobOutcome:
        target = str(job.payload.get("target_path", "skills/UNKNOWN/SKILL.md"))
        rationale = str(job.payload.get("rationale", "candidate skill from background learner"))
        intent = str(job.payload.get("diff_intent", "(new skill description)"))
        p = self.book.propose(
            kind=ProposalKind.NEW_SKILL,
            target_path=target,
            rationale=rationale,
            diff_intent=intent,
            risk_class="RC3",
        )
        return JobOutcome(job.id, job.kind, "proposed", f"skill proposal for {target}", proposal=p)


def _default_autoresearch_swarm(plan, *, book, baseline_bpb, min_bpb_delta):
    """The built-in live runner: real workers + the default idea catalog.

    Reached only when every gate is already open (approval token at enqueue,
    ``muse_AUTORESEARCH_ALLOW_SPAWN=1``); each worker still re-checks
    ``detect()`` fail-closed at run time (uv, training data, CUDA/modal).
    """

    from hermes_cli.jarvis_prime.research_fabric.autoresearch.swarm import run_swarm
    from hermes_cli.workers.autoresearch import (
        AutoresearchWorker,
        AutoresearchWorkerConfig,
    )

    def worker_factory(assignment):
        return AutoresearchWorker(
            config=AutoresearchWorkerConfig(experiment=assignment.config)
        )

    return run_swarm(
        plan,
        worker_factory=worker_factory,
        book=book,
        baseline_bpb=baseline_bpb,
        min_bpb_delta=min_bpb_delta,
        vram_budget_mb=plan.assignments[0].config.vram_budget_mb if plan.assignments else 0.0,
    )


def run_idle_cycle(
    queue: JobQueue,
    runner: Optional[BackgroundLearnerRunner] = None,
    max_jobs: int = 50,
) -> int:
    """Idle-gated drain entry point for a scheduler tick.

    Attach as: ``JobQueue(idle_check=..., executor=runner.handle)`` then call
    this from the cron scheduler's idle hook. Returns the number of jobs run.
    Safe to call unconditionally — the queue's own ``idle_check`` gates it.
    """
    return queue.drain(max_jobs=max_jobs)


# Convenience: a queue pre-wired with a live runner (still owner-gated).
def make_live_queue(
    idle_check: Optional[Callable[[], bool]] = None,
    book: Optional[ProposalBook] = None,
) -> tuple[JobQueue, BackgroundLearnerRunner]:
    runner = BackgroundLearnerRunner(book=book)
    queue = JobQueue(idle_check=idle_check, executor=runner.handle)
    return queue, runner
