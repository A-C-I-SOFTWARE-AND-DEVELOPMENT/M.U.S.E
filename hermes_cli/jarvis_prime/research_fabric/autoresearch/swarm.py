"""Swarm coordinator — N autoresearch lanes, one scorecard book, ONE proposal.

Each lane is an independent experiment search: its own branch
(``autoresearch/<tag>-gpuK`` / ``-modalK``), its own disposable workspace, its
own per-lane share of the total cost ceiling. Lanes never share writable
state; while they run, the swarm writes nothing. After all lanes return, the
coordinator is the **single writer**: it merges every lane's champion
scorecard into the one :class:`ScorecardBook`, picks the single best feasible
champion across lanes, and emits exactly ONE owner-gated proposal through the
canonical ``run_self_improvement`` path (via a replay worker that re-presents
the winning lane's artifacts).

Built and tested against fake workers — multi-GPU execution happens on owner
hardware via the ``worker_factory`` (real :class:`AutoresearchWorker` per
device / Modal lane, ``CUDA_VISIBLE_DEVICES`` set per assignment).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Optional, Sequence, Union

from .engine import ExperimentConfig


@dataclass(frozen=True)
class LaneSpec:
    device: str  # "cuda:0", "modal:H100", ...
    cost_per_hour_usd: float = 0.0
    label: str = ""


@dataclass(frozen=True)
class LaneAssignment:
    lane_id: int
    branch: str
    device: str
    workspace_dir: str
    config: ExperimentConfig


@dataclass(frozen=True)
class SwarmPlan:
    tag: str
    assignments: tuple[LaneAssignment, ...]

    def summary(self) -> str:
        lines = [f"swarm '{self.tag}': {len(self.assignments)} lane(s)"]
        for a in self.assignments:
            cfg = a.config
            lines.append(
                f"  lane {a.lane_id}: {a.device} branch={a.branch} "
                f"ceilings=({cfg.max_experiments} exp, "
                f"{cfg.max_wall_clock_seconds:.0f}s, ${cfg.max_cost_usd:.2f})"
            )
        return "\n".join(lines)


@dataclass
class LaneOutcome:
    assignment: LaneAssignment
    improvement: Optional[Any] = None  # AutoresearchImprovementOutcome
    error: str = ""

    def champion(self) -> Optional[dict[str, Any]]:
        if self.improvement is None:
            return None
        return (self.improvement.run_details or {}).get("champion")

    def feasible_champion_bpb(self) -> Optional[float]:
        champion = self.champion()
        if self.improvement is None or not champion or champion.get("val_bpb") is None:
            return None
        from hermes_cli.jarvis_prime.gates import GateOutcome

        if self.improvement.constraints_gate.outcome is not GateOutcome.PASS:
            return None
        return float(champion["val_bpb"])


@dataclass
class SwarmOutcome:
    plan: SwarmPlan
    lanes: tuple[LaneOutcome, ...]
    scorecard_book: Any  # the ONE merged ScorecardBook
    best_lane: Optional[LaneOutcome]
    proposal_outcome: Optional[Any]  # AutoresearchImprovementOutcome (the single proposal)


def plan_swarm(
    tag: str,
    lanes: Union[int, Sequence[LaneSpec]],
    *,
    base_config: ExperimentConfig,
) -> SwarmPlan:
    """Assign branches/workspaces/ceilings; total spend stays bounded."""

    specs: list[LaneSpec]
    if isinstance(lanes, int):
        specs = [LaneSpec(device=f"cuda:{k}") for k in range(lanes)]
    else:
        specs = list(lanes)
    if not specs:
        raise ValueError("a swarm needs at least one lane")

    base_workspace = Path(base_config.resolved_workspace())
    per_lane_cost = (
        base_config.max_cost_usd / len(specs) if base_config.max_cost_usd > 0 else 0.0
    )
    assignments: list[LaneAssignment] = []
    for k, spec in enumerate(specs):
        kind = "modal" if spec.device.startswith("modal") else "gpu"
        branch = f"autoresearch/{tag}-{kind}{k}"
        workspace = str(base_workspace / f"lane{k}")
        config = replace(
            base_config,
            tag=f"{tag}-{kind}{k}",
            branch=branch,
            workspace_dir=workspace,
            device=spec.device,
            max_cost_usd=per_lane_cost,
            cost_per_hour_usd=spec.cost_per_hour_usd or base_config.cost_per_hour_usd,
        )
        assignments.append(
            LaneAssignment(
                lane_id=k,
                branch=branch,
                device=spec.device,
                workspace_dir=workspace,
                config=config,
            )
        )

    branches = [a.branch for a in assignments]
    workspaces = [a.workspace_dir for a in assignments]
    if len(set(branches)) != len(branches) or len(set(workspaces)) != len(workspaces):
        raise ValueError("lane branches/workspaces must be unique (no shared state)")
    return SwarmPlan(tag=tag, assignments=tuple(assignments))


class _ReplayWorker:
    """Re-presents a finished lane's artifacts through the canonical path.

    The swarm's single proposal still flows through ``run_self_improvement``
    (gate → RC4 → NEEDS_OWNER_APPROVAL) — this worker just replays the
    winning lane's already-collected artifacts and score instead of running
    the loop again.
    """

    def __init__(self, artifacts: Any, score: Any) -> None:
        self._artifacts = artifacts
        self._score = score

    def detect(self):
        from hermes_cli.workers.base import WorkerDetection

        return WorkerDetection(available=True, reason="swarm replay")

    def prepare_prompt(self, job: Any):
        from hermes_cli.workers.base import WorkerPrompt

        return WorkerPrompt(text="swarm replay of winning lane artifacts")

    def run(self, job: Any):
        from hermes_cli.workers.base import WorkerRunResult

        return WorkerRunResult(ok=True)

    def collect(self, job: Any):
        return self._artifacts

    def score(self, artifacts: Any):
        return self._score


def run_swarm(
    plan: SwarmPlan,
    *,
    worker_factory: Callable[[LaneAssignment], Any],
    book: Any,  # ProposalBook
    baseline_bpb: float,
    min_bpb_delta: float = 0.0,
    vram_budget_mb: float = 0.0,
    scorecard_book: Optional[Any] = None,
    memory_store: Optional[Any] = None,
) -> SwarmOutcome:
    """Run every lane (proposal-suppressed), merge once, propose once."""

    from hermes_cli.jarvis_prime.autoresearch_improve import (
        run_autoresearch_improvement,
    )
    from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook

    merged_book = scorecard_book if scorecard_book is not None else ScorecardBook()

    lanes: list[LaneOutcome] = []
    for assignment in plan.assignments:
        try:
            worker = worker_factory(assignment)
            improvement = run_autoresearch_improvement(
                f"swarm {plan.tag} lane {assignment.lane_id}: minimize val_bpb",
                book=book,
                worker=worker,
                baseline_bpb=baseline_bpb,
                min_bpb_delta=min_bpb_delta,
                vram_budget_mb=vram_budget_mb,
                max_cost_usd=assignment.config.max_cost_usd,
                scorecard_book=None,  # single-writer rule: merge below
                memory_store=memory_store,
                emit_proposal=False,  # ONE proposal, from the coordinator
            )
            lanes.append(LaneOutcome(assignment=assignment, improvement=improvement))
        except Exception as exc:
            lanes.append(
                LaneOutcome(assignment=assignment, error=f"{type(exc).__name__}: {exc}")
            )

    # ── single-writer merge: only the coordinator records scorecards ──
    for lane in lanes:
        if lane.improvement is not None:
            for card in lane.improvement.scorecards:
                merged_book.record(card, persist=merged_book.path is not None)

    # ── select the single best feasible, IMPROVING champion across lanes ──
    # (feasibility alone is not enough: a lane whose best result regressed
    # vs baseline has nothing worth replaying through the proposal path)
    best_lane: Optional[LaneOutcome] = None
    best_bpb = float("inf")
    for lane in lanes:
        bpb = lane.feasible_champion_bpb()
        if bpb is not None and bpb < baseline_bpb and bpb < best_bpb:
            best_bpb = bpb
            best_lane = lane

    proposal_outcome: Optional[Any] = None
    if best_lane is not None and best_lane.improvement is not None:
        winner = worker_factory(best_lane.assignment)
        job_probe = type("J", (), {"objective": "", "prompt": ""})()
        try:
            artifacts = winner.collect(job_probe)
            score = winner.score(artifacts)
        except Exception:
            artifacts = score = None
        if artifacts is not None and score is not None:
            replay = _ReplayWorker(artifacts, score)
            proposal_outcome = run_autoresearch_improvement(
                f"swarm {plan.tag}: adopt lane {best_lane.assignment.lane_id} champion",
                book=book,
                worker=replay,
                baseline_bpb=baseline_bpb,
                min_bpb_delta=min_bpb_delta,
                vram_budget_mb=vram_budget_mb,
                max_cost_usd=best_lane.assignment.config.max_cost_usd,
                scorecard_book=None,  # cards already merged above
                memory_store=None,  # lane runs already consolidated
                emit_proposal=True,
            )

    return SwarmOutcome(
        plan=plan,
        lanes=tuple(lanes),
        scorecard_book=merged_book,
        best_lane=best_lane,
        proposal_outcome=proposal_outcome,
    )


__all__ = [
    "LaneSpec",
    "LaneAssignment",
    "SwarmPlan",
    "LaneOutcome",
    "SwarmOutcome",
    "plan_swarm",
    "run_swarm",
]
