"""The Grainler — partitions a code goal into non-overlapping grains.

The Grainler is deliberately split into two halves:

* a **decomposition** seam (``decomposer``) that proposes grain specs — this is
  where an LLM or a heuristic decides *how* to carve the work; and
* a **deterministic** core that turns specs into :class:`~hermes_cli.swarm.grain.Grain`
  objects, **proves their file-domains disjoint**, and lowers the plan to an
  :class:`~hermes_cli.orchestrator_parallel.ExecutionPlan`.

Keeping the proof + lowering deterministic (no I/O, no model) means the
collision-freedom and complexity-gate behaviour are unit-testable without a
network. The default decomposer derives a single grain from a JARVIS work
packet (reusing ``natural_language_coder.build_work_packet``), so a goal with
no explicit partition still runs — as a *trivial* (no-swarm) plan, honouring the
"don't 15× a typo" cost lesson.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence
import hashlib
import re

from hermes_cli.swarm.grain import FileDomain, Grain, SwarmPlan

__all__ = [
    "GrainSpec",
    "Decomposer",
    "default_decomposer",
    "partition",
    "to_execution_plan",
]


# A decomposer takes ``(goal, repo_root)`` and returns an ordered list of grain
# specs (plain dicts). Returning one spec yields a trivial, no-swarm plan.
GrainSpec = Mapping[str, Any]
Decomposer = Callable[[str, str], Sequence[GrainSpec]]


def _slug(text: str, *, fallback: str = "grain") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return (s[:40].rstrip("-") or fallback)


def _job_id(goal: str) -> str:
    digest = hashlib.sha1((goal or "").encode("utf-8")).hexdigest()[:8]
    return f"swarm-{_slug(goal, fallback='job')[:24]}-{digest}".strip("-")


def default_decomposer(goal: str, repo_root: str) -> list[GrainSpec]:
    """Derive a single grain from a JARVIS work packet.

    This is the conservative default: it does not *split* the goal (that needs
    judgement an LLM provides), it just lifts the existing work-packet scope
    into one grain so the pipeline runs end-to-end. Callers wanting a real
    multi-grain swarm pass their own ``decomposer`` (or explicit specs).
    """

    try:
        from hermes_cli.jarvis_prime.natural_language_coder import build_work_packet

        packet = build_work_packet(goal, repo_root=repo_root)
        globs = tuple(packet.allowed_files) or ("**",)
        return [
            {
                "intent": packet.mission or goal,
                "globs": globs,
                "forbidden": tuple(packet.forbidden_files),
                "risk_class": packet.risk_class,
                "model_lane": packet.model_lane_hint,
                "acceptance_criteria": tuple(packet.acceptance_criteria),
                "verification_plan": tuple(packet.verification_plan),
                "rollback_plan": tuple(packet.rollback_plan),
                "owner_gated_actions": tuple(packet.owner_gated_actions),
            }
        ]
    except Exception:
        # Never let work-packet derivation break partitioning; fall back to a
        # whole-repo single grain (still a valid, if coarse, plan).
        return [{"intent": goal, "globs": ("**",)}]


def _grain_from_spec(index: int, spec: GrainSpec) -> Grain:
    intent = str(spec.get("intent") or spec.get("mission") or "").strip()
    if not intent:
        raise ValueError(f"grain spec #{index} is missing an 'intent'")
    globs = tuple(spec.get("globs") or spec.get("allowed_files") or ())
    if not globs:
        raise ValueError(f"grain spec #{index} ({intent!r}) declares no file globs")
    grain_id = str(spec.get("grain_id") or f"g{index:02d}-{_slug(intent)}")
    domain = FileDomain(globs=globs, forbidden=tuple(spec.get("forbidden") or ()))
    return Grain(
        grain_id=grain_id,
        intent=intent,
        domain=domain,
        risk_class=str(spec.get("risk_class") or "RC1"),
        model_lane=str(spec.get("model_lane") or "claude"),
        toolset_hint=tuple(spec.get("toolset_hint") or ()),
        acceptance_criteria=tuple(spec.get("acceptance_criteria") or ()),
        verification_plan=tuple(spec.get("verification_plan") or ()),
        rollback_plan=tuple(spec.get("rollback_plan") or ()),
        owner_gated_actions=tuple(spec.get("owner_gated_actions") or ()),
        iteration_budget=int(spec.get("iteration_budget") or 50),
        token_budget=int(spec.get("token_budget") or 8000),
    )


@dataclass(frozen=True)
class _PartitionResult:
    plan: SwarmPlan


def partition(
    goal: str,
    repo_root: str = ".",
    *,
    job_id: Optional[str] = None,
    grains: Optional[Sequence[GrainSpec]] = None,
    decomposer: Optional[Decomposer] = None,
) -> SwarmPlan:
    """Decompose ``goal`` into a proven-disjoint :class:`SwarmPlan`.

    ``grains`` — explicit grain specs (skip decomposition). Otherwise
    ``decomposer`` (default :func:`default_decomposer`) proposes them.

    The returned plan is **guaranteed non-overlapping**: :meth:`SwarmPlan.prove_disjoint`
    is run here and raises :class:`~hermes_cli.swarm.grain.OverlapError` before
    any worker is created.
    """

    if not goal or not goal.strip():
        raise ValueError("goal is required")

    specs: Sequence[GrainSpec]
    if grains is not None:
        specs = list(grains)
        if not specs:
            raise ValueError("explicit 'grains' was empty")
    else:
        specs = (decomposer or default_decomposer)(goal, repo_root)
        if not specs:
            raise ValueError("decomposer returned no grains")

    built = tuple(_grain_from_spec(i, s) for i, s in enumerate(specs))
    plan = SwarmPlan(job_id=job_id or _job_id(goal), goal=goal.strip(), grains=built)
    # The non-overlap guarantee: rejects before anything runs.
    plan.prove_disjoint()
    return plan


def to_execution_plan(
    plan: SwarmPlan,
    *,
    concurrency: Optional[int] = None,
    max_concurrency: int = 8,
    base_ref: Optional[str] = None,
    allow_dirty: bool = False,
    command_builder: Optional[Callable[[Grain], Sequence[str]]] = None,
    timeout_seconds: int = 600,
):
    """Lower a :class:`SwarmPlan` to an :class:`ExecutionPlan` of isolated workers.

    Each grain becomes one ``WorkerPlan`` with ``use_worktree=True`` (physical
    isolation). With no ``command_builder`` the workers are ``PROMPT_ONLY`` —
    the safe default that materialises each grain's prompt/context without
    launching a process. Supply ``command_builder`` to run a real per-grain
    agent command (``LOCAL_RUN``).
    """

    from hermes_cli.orchestrator_parallel import (
        ExecutionMode,
        ExecutionPlan,
        WorkerPlan,
    )

    workers: list[WorkerPlan] = []
    for grain in plan.grains:
        if command_builder is not None:
            command = list(command_builder(grain))
            mode = ExecutionMode.LOCAL_RUN
        else:
            command = None
            mode = ExecutionMode.PROMPT_ONLY
        workers.append(
            WorkerPlan(
                worker_id=grain.grain_id,
                profile=grain.model_lane,
                mode=mode,
                prompt=grain.intent,
                command=command,
                timeout_seconds=timeout_seconds,
                use_worktree=True,
            )
        )

    eff_conc = concurrency if concurrency is not None else min(len(workers), max_concurrency)
    eff_conc = max(1, min(eff_conc, max_concurrency))
    return ExecutionPlan(
        job_id=plan.job_id,
        workers=tuple(workers),
        concurrency=eff_conc,
        use_worktrees=True,
        base_ref=base_ref,
        allow_dirty=allow_dirty,
    )
