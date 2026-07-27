"""The Swarm Coordinator — the end-to-end Swarm Grainler Parallel pipeline.

``run_swarm`` composes the existing Hermes primitives into one auditable,
non-overlapping, dated, self-improving flow:

    decompose (Grainler)            → proven-disjoint SwarmPlan
      → claim each grain's domain   → runtime non-overlap backstop (leases)
      → build specialized agents    → token-juice + dedicated memory namespace
      → run in parallel             → ParallelRunner, per-grain git worktrees
      → record on the blackboard    → dated, traceable swarm memory namespace
      → write a Decision Ledger     → 15-section, sequence-numbered, timestamped
      → self-update (auto-apply)    → reversible tier applied, rest owner-gated
      → release claims

Every heavy collaborator (agent execution, memory writes, the apply hook) is an
injectable seam, so the orchestration logic is unit-testable without a network.
The default executor is ``PROMPT_ONLY`` — it materialises each grain's
specialized prompt + token-juice context into its isolated workspace and
records dated status, without launching a model. Pass an ``executor`` (or a
``command_builder``) to run real per-grain agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, Sequence
import json

from hermes_cli.swarm.grain import Grain, SwarmPlan, now_iso
from hermes_cli.swarm import grainler as _grainler
from hermes_cli.swarm import specialist as _specialist
from hermes_cli.swarm.specialist import GrainAgentSpec
from hermes_cli.swarm.ai_executor import AIAgentExecutor, AIAgentExecutorConfig  # noqa: E402,F401  (re-exported)

__all__ = [
    "SwarmGrainResult",
    "SwarmResult",
    "GrainExecutor",
    "PromptOnlyExecutor",
    "AIAgentExecutor",
    "AIAgentExecutorConfig",
    "resolve_executor",
    "run_swarm",
    "run_swarm_niche",
    "muse_local_executor_config",
]


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass
class SwarmGrainResult:
    grain_id: str
    state: str = "pending"
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    worktree_path: Optional[str] = None
    branch: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "grain_id": self.grain_id,
            "state": self.state,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "worktree_path": self.worktree_path,
            "branch": self.branch,
            "error": self.error,
        }


@dataclass
class SwarmResult:
    job_id: str
    goal: str
    created_at: str
    trivial: bool
    grains: list[SwarmGrainResult] = field(default_factory=list)
    ledger_path: Optional[str] = None
    applied_updates: list[dict[str, Any]] = field(default_factory=list)
    queued_updates: list[dict[str, Any]] = field(default_factory=list)
    blackboard_namespace: str = ""
    convergence: Optional[dict[str, Any]] = None
    notes: list[str] = field(default_factory=list)
    scout_packets: int = 0
    niches_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "goal": self.goal,
            "created_at": self.created_at,
            "trivial": self.trivial,
            "grains": [g.to_dict() for g in self.grains],
            "ledger_path": self.ledger_path,
            "applied_updates": self.applied_updates,
            "queued_updates": self.queued_updates,
            "blackboard_namespace": self.blackboard_namespace,
            "convergence": self.convergence,
            "notes": self.notes,
            "scout_packets": self.scout_packets,
            "niches_used": self.niches_used,
        }


# ---------------------------------------------------------------------------
# Executor seam
# ---------------------------------------------------------------------------


class GrainExecutor(Protocol):
    """Runs the grains of a plan and returns their per-grain results."""

    def run(
        self,
        repo: Path,
        plan: SwarmPlan,
        specs: dict[str, GrainAgentSpec],
    ) -> list[SwarmGrainResult]: ...


class PromptOnlyExecutor:
    """Default executor: isolate + materialise, never launch a model.

    Each grain gets a git worktree (physical isolation) and its specialized
    prompt + token-juice context written into the worktree, with dated status
    persisted by :class:`ParallelRunner`. Safe, deterministic, fully auditable —
    the conservative "decides, does not act" default.
    """

    def __init__(self, *, timeout_seconds: int = 600, allow_dirty: bool = False) -> None:
        self.timeout_seconds = timeout_seconds
        self.allow_dirty = allow_dirty

    def run(
        self,
        repo: Path,
        plan: SwarmPlan,
        specs: dict[str, GrainAgentSpec],
    ) -> list[SwarmGrainResult]:
        from hermes_cli.orchestrator_parallel import ParallelRunner

        exec_plan = _grainler.to_execution_plan(
            plan,
            timeout_seconds=self.timeout_seconds,
            allow_dirty=self.allow_dirty,
        )
        runner = ParallelRunner(repo, exec_plan)
        statuses = runner.run()

        out: list[SwarmGrainResult] = []
        for grain in plan.grains:
            st = statuses.get(grain.grain_id)
            spec = specs.get(grain.grain_id)
            res = SwarmGrainResult(grain_id=grain.grain_id)
            if st is not None:
                res.state = st.state.value if hasattr(st.state, "value") else str(st.state)
                res.started_at = st.started_at
                res.ended_at = st.ended_at
                res.worktree_path = st.worktree_path
                res.branch = st.branch
                res.error = st.error
                # Drop the specialized prompt + context into the grain workspace.
                if spec is not None and st.worktree_path:
                    try:
                        wt = Path(st.worktree_path)
                        wt.mkdir(parents=True, exist_ok=True)
                        (wt / "GRAIN_PROMPT.md").write_text(
                            spec.system_prompt + "\n", encoding="utf-8"
                        )
                        if spec.context:
                            (wt / "GRAIN_CONTEXT.md").write_text(
                                spec.context, encoding="utf-8"
                            )
                    except OSError:
                        pass
            out.append(res)
        return out


def resolve_executor(
    executor: Any = None,
    *,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    max_iterations: int = 25,
    concurrency: int = 2,
    quiet_mode: bool = True,
    allow_dirty: bool = False,
) -> "GrainExecutor | PromptOnlyExecutor | AIAgentExecutor":
    """Resolve the ``executor=`` argument into a concrete :class:`GrainExecutor`.

    Accepts either:

    * a :class:`GrainExecutor` instance (returned as-is, no wrapping);
    * the string ``"prompt_only"`` → :class:`PromptOnlyExecutor` (the safe
      default; launched no model);
    * the string ``"ai"`` → :class:`AIAgentExecutor` driving the model
      described by ``base_url`` / ``api_key`` / ``model`` / ``provider``
      (all four are required for the ``"ai"`` selector);
    * ``None`` → :class:`PromptOnlyExecutor` (preserves prior default).

    Raises :class:`ValueError` for an unknown selector string or when
    ``"ai"`` is requested without complete credentials.
    """

    if executor is None or executor == "prompt_only":
        return PromptOnlyExecutor(allow_dirty=allow_dirty)
    if isinstance(executor, str):
        if executor == "ai":
            from hermes_cli.swarm.ai_executor import AIAgentExecutor  # lazy

            missing = [
                name
                for name, value in (
                    ("base_url", base_url),
                    ("api_key", api_key),
                    ("model", model),
                    ("provider", provider),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    "executor='ai' requires " + ", ".join(missing)
                    + " — pass them as run_swarm(... base_url=..., api_key=..., "
                    "model=..., provider=...) or via the CLI --executor ai "
                    "--base_url ... --api_key ... --model ... --provider ... flags"
                )
            return AIAgentExecutor(
                base_url=str(base_url),
                api_key=str(api_key),
                model=str(model),
                provider=str(provider),
                max_iterations=max_iterations,
                concurrency=concurrency,
                quiet_mode=quiet_mode,
            )
        raise ValueError(
            f"unknown executor selector {executor!r}; expected 'prompt_only', 'ai', or a GrainExecutor instance"
        )
    # Assume it's already a GrainExecutor.
    return executor


# ---------------------------------------------------------------------------
# Decision ledger
# ---------------------------------------------------------------------------


def _write_decision_ledger(
    plan: SwarmPlan,
    results: Sequence[SwarmGrainResult],
    *,
    niches_used: Optional[Sequence[str]] = None,
    scout_packets: int = 0,
) -> Optional[str]:
    try:
        from hermes_cli.decision_ledger import DecisionLedger, write_ledger
    except Exception:
        return None

    grain_lines = "\n".join(
        f"- `{g.grain_id}` (risk {g.risk_class}, lane {g.model_lane}) owns: "
        + ", ".join(g.domain.globs)
        for g in plan.grains
    )
    result_lines = "\n".join(
        f"- `{r.grain_id}`: {r.state}"
        + (f" (branch {r.branch})" if r.branch else "")
        + (f" — {r.error}" if r.error else "")
        for r in results
    )
    owner_gated = [g.grain_id for g in plan.grains if g.owner_gated]
    niche_line = ", ".join(niches_used) if niches_used else "(none)"
    scout_line = f"{scout_packets} Scout packet(s) prefetched onto the blackboard before grain decode."

    ledger = DecisionLedger(
        decision=f"Run swarm job {plan.job_id} as {len(plan.grains)} non-overlapping grain(s).",
        plain_english_summary=(
            f"Broke the goal into {len(plan.grains)} independent piece(s), each owning a "
            "separate set of files, and ran them in isolated git worktrees so they could "
            "not interfere with each other."
        ),
        context=(
            f"Goal: {plan.goal}\nTriggered via Swarm Grainler Parallel coordinator.\n"
            f"Niches used: {niche_line}\n{scout_line}"
        ),
        evidence_reviewed=(
            "Grain file-domains (proven pairwise disjoint before any agent started):\n"
            + grain_lines
            + f"\nNiches routed: {niche_line}\n{scout_line}"
        ),
        options_considered=(
            "Option A — swarm with proven-disjoint file-domains + worktree isolation "
            "(chosen). Option B — single sequential agent (rejected: no parallelism, "
            "but is the fallback for trivial goals). Defer is always available."
        ),
        selected_model_worker=(
            "Per-grain specialized agents: "
            + ", ".join(f"{g.grain_id}->{g.model_lane}" for g in plan.grains)
        ),
        why_this_choice=(
            "Disjoint file-domains + git worktrees + lease claims give a three-layer "
            "non-overlap guarantee; each grain is a specialized LLM with its own token "
            "budget and memory namespace."
        ),
        rejected_alternatives=(
            "Worktrees-only (rejected: cannot warn on same-file edits across worktrees). "
            "Single shared tree with locks only (rejected: weaker isolation)."
        ),
        cost_latency_quality_tradeoff=(
            f"{len(plan.grains)} parallel grain(s); each token-budget-bounded via "
            "TokenJuice. Trivial goals run inline to avoid the multi-agent token tax."
        ),
        validation_plan="\n".join(
            "- " + vp for g in plan.grains for vp in (g.verification_plan or ())
        )
        or "- Per-grain verification commands run inside each worktree before merge.",
        approval_required=(
            "yes - owner gate(s) present on grains: " + ", ".join(owner_gated)
            if owner_gated
            else "no - all grains are below the owner-gate threshold."
        ),
        final_decision="Option A — proven-disjoint swarm.",
        confidence="medium - static disjointness proven; runtime backed by leases + worktrees.",
        open_risks=(
            "Runtime file drift outside declared domains is caught by lease claims and "
            "merge-time conflict detection, not prevented a priori."
        ),
        rollback_plan=(
            "Each grain runs on branch hermes/<job>/<grain>; discard a grain by deleting "
            "its worktree/branch (nothing is merged or pushed automatically)."
        )
        + "\nResults:\n"
        + (result_lines or "- (no results recorded)"),
    )
    try:
        path = write_ledger(ledger, session_id=plan.job_id, validate=True)
        return str(path)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Self-update (auto-apply reversible)
# ---------------------------------------------------------------------------


def _emit_self_update(
    plan: SwarmPlan,
    results: Sequence[SwarmGrainResult],
    *,
    apply_fn: Optional[Callable[[Any], dict[str, Any]]] = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build self-update proposals from the swarm outcome and route them.

    Reversible, low-blast-radius proposals (``promotion_decision`` == "apply")
    are auto-applied via ``apply_fn`` (default: record-only, undone by deleting
    the record). Everything else is queued for the owner. Returns
    ``(applied, queued)`` dicts for the result + ledger.
    """

    try:
        from hermes_cli.self_improvement import Proposal, promotion_decision
    except Exception:
        return [], []

    proposals: list[Proposal] = []

    # A grain that failed is weak evidence for a one-notch routing nudge away
    # from its lane on this task class. Reversible + carries rollback metadata,
    # so promotion_decision can return "apply" once the K=3 rule is satisfied.
    for r in results:
        if r.state in {"failed", "timed-out"}:
            proposals.append(
                Proposal(
                    kind="routing_miss",
                    target=f"lane:{_lane_for(plan, r.grain_id)}/grain:{r.grain_id}",
                    summary=f"Grain {r.grain_id} ended {r.state}.",
                    rationale="Observed grain failure in a swarm job.",
                    evidence=(f"swarm:{plan.job_id}:{r.grain_id}:{r.state}",),
                    reversible=True,
                    extra={
                        "additive_nudge": True,
                        "previous_value": _lane_for(plan, r.grain_id),
                        "nudge_delta": 1,
                        # The coordinator does not self-confirm; the K=3 rule
                        # decides. Set by the owner/monitor for single events.
                    },
                )
            )

    applied: list[dict[str, Any]] = []
    queued: list[dict[str, Any]] = []
    for p in proposals:
        decision = promotion_decision(p)
        record = {"decision": decision, "proposal": p.as_dict()}
        if decision == "apply":
            if apply_fn is not None:
                try:
                    record["applied"] = apply_fn(p)
                except Exception as exc:  # apply must never break the job
                    record["apply_error"] = repr(exc)
                    queued.append(record)
                    continue
            applied.append(record)
        elif decision == "promote":
            queued.append(record)
        # "defer" → dropped silently (K=3 / weak-evidence rule).
    return applied, queued


def _converge(results: Sequence[SwarmGrainResult]) -> dict[str, Any]:
    """Cooperative convergence: read each grain's changed files + conflict check."""

    try:
        from hermes_cli.swarm.converge import converge_cooperative
    except Exception:
        return {"mode": "cooperative", "kept": [r.grain_id for r in results]}

    changed_by_grain: dict[str, list[str]] = {}
    for r in results:
        files: list[str] = []
        if r.worktree_path:
            cf = Path(r.worktree_path) / "changed-files.txt"
            try:
                files = [
                    line.strip()
                    for line in cf.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                ]
            except OSError:
                files = []
        changed_by_grain[r.grain_id] = files
    return converge_cooperative(changed_by_grain).to_dict()


def _lane_for(plan: SwarmPlan, grain_id: str) -> str:
    for g in plan.grains:
        if g.grain_id == grain_id:
            return g.model_lane
    return "claude"


# ---------------------------------------------------------------------------
# Blackboard
# ---------------------------------------------------------------------------


def _record_blackboard(
    plan: SwarmPlan, results: Sequence[SwarmGrainResult], memory_store: Optional[Any]
) -> None:
    """Post each grain's outcome + a job summary to the Swarm Blackboard.

    Stigmergic coordination: grains and the coordinator communicate indirectly
    via dated traces in the shared ``swarm/<job>`` namespace, never directly.
    """

    try:
        from hermes_cli.swarm.blackboard import SwarmBlackboard

        board = SwarmBlackboard(plan.job_id, memory_store=memory_store)
        for r in results:
            board.post(
                r.grain_id,
                f"ended {r.state}" + (f": {r.error}" if r.error else ""),
                kind="decision",
            )
        board.post(
            "coordinator",
            f"Swarm job {plan.job_id} for goal: {plan.goal}; "
            + "; ".join(f"{r.grain_id}={r.state}" for r in results),
            kind="note",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Orchestration entrypoint
# ---------------------------------------------------------------------------


def muse_local_executor_config(
    *,
    concurrency: int = 2,
    max_iterations: int = 25,
    quiet_mode: bool = True,
) -> AIAgentExecutorConfig:
    """Build AIAgentExecutorConfig pointing at local MUSE fusion router."""
    return AIAgentExecutorConfig(
        base_url="http://127.0.0.1:11436/v1",
        api_key="muse-local",
        model="muse",
        provider="openai",
        max_iterations=max_iterations,
        concurrency=max(2, min(8, concurrency)),
        quiet_mode=quiet_mode,
    )


def _match_niches(goal: str, limit: int = 5) -> list[Any]:
    try:
        from hermes_cli.jarvis_prime.agent_pool import route, CAT_NICHE

        matches = route(goal, limit=limit, min_score=0.5)
        return [m for m in matches if m.entry.category == CAT_NICHE]
    except Exception:
        return []


def _niche_scout_queries(goal: str, niche_matches: Sequence[Any]) -> list[str]:
    queries: list[str] = []
    try:
        from hermes_cli.jarvis_prime.niches.loader import load_niche
    except Exception:
        load_niche = None  # type: ignore
    for m in niche_matches:
        niche_id = m.entry.name
        if load_niche:
            spec = load_niche(niche_id)
            if spec:
                queries.extend(list(spec.scout_queries))
                continue
        queries.append(str(niche_id))
    if not queries:
        queries.append(goal)
    return queries[:12]


def run_swarm(
    goal: str,
    repo: Path | str = ".",
    *,
    grains: Optional[Sequence[_grainler.GrainSpec]] = None,
    decomposer: Optional[_grainler.Decomposer] = None,
    job_id: Optional[str] = None,
    executor: Any = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    max_iterations: int = 25,
    concurrency: int = 2,
    quiet_mode: bool = True,
    memory_store: Optional[Any] = None,
    lease_store: Optional[Any] = None,
    apply_reversible: bool = True,
    apply_fn: Optional[Callable[[Any], dict[str, Any]]] = None,
    claim_domains: bool = True,
    scout: bool = False,
    niche_mode: bool = False,
    allow_dirty: bool = False,
) -> SwarmResult:
    """Run the full Swarm Grainler Parallel pipeline for ``goal``.

    When ``scout=True`` (or ``niche_mode=True``), runs Scout prefetch into the
    blackboard and injects packets into each grain's context before execution.
    When ``niche_mode=True`` and ``executor`` is None, defaults to muse-local
    :class:`AIAgentExecutor` (falls back to prompt_only if construction fails).
    """

    repo_path = Path(repo)
    # Default to the directory-aware decomposer for real multi-grain splitting;
    # it falls back to a single whole-repo grain when it can't find ≥2 distinct
    # components (which then runs inline as a trivial plan).
    if decomposer is None and grains is None:
        from hermes_cli.swarm.decompose import directory_decomposer

        decomposer = directory_decomposer
    plan = _grainler.partition(
        goal, str(repo_path), job_id=job_id, grains=grains, decomposer=decomposer
    )

    niche_matches = _match_niches(goal) if niche_mode or scout else []
    niches_used = [m.entry.name for m in niche_matches]

    result = SwarmResult(
        job_id=plan.job_id,
        goal=plan.goal,
        created_at=plan.created_at,
        trivial=plan.is_trivial,
        blackboard_namespace=plan.blackboard_namespace,
        niches_used=niches_used,
    )
    if plan.is_trivial:
        result.notes.append(
            "Trivial goal: single grain, no swarm fan-out (avoids the multi-agent "
            "token tax). The grain still runs in isolation with a Decision Ledger."
        )
    if niches_used:
        result.notes.append("niches: " + ", ".join(niches_used))

    # Claim each grain's file-domain (runtime non-overlap backstop).
    claimed: list[Grain] = []
    if claim_domains:
        for grain in plan.grains:
            _specialist.claim_grain(repo_path, plan.job_id, grain, lease_store=lease_store)
            claimed.append(grain)

    try:
        # Build the specialized agent spec (token-juice + memory namespace) per grain.
        specs: dict[str, GrainAgentSpec] = {
            grain.grain_id: _specialist.build_grain_agent_spec(
                grain,
                goal=plan.goal,
                blackboard_namespace=plan.blackboard_namespace,
                memory_store=memory_store,
            )
            for grain in plan.grains
        }

        # Scout prefetch (before any model decode)
        if scout or niche_mode:
            try:
                from hermes_cli.swarm.blackboard import SwarmBlackboard
                from hermes_cli.swarm.scout import (
                    prefetch_for_plan,
                    inject_scout_into_specs,
                )

                board = SwarmBlackboard(plan.job_id, memory_store=memory_store)
                scout_result = prefetch_for_plan(
                    plan,
                    repo_path,
                    niche_queries=_niche_scout_queries(goal, niche_matches),
                    blackboard=board,
                )
                specs = inject_scout_into_specs(specs, scout_result)
                result.scout_packets = len(scout_result.packets)
                result.notes.append(
                    f"scout: {result.scout_packets} packets in {scout_result.elapsed_ms:.0f}ms"
                )
            except Exception as exc:
                result.notes.append(f"scout skipped: {exc}")

        # Niche mode defaults to muse-local AI executor when caller didn't pick one
        effective_executor = executor
        if niche_mode and effective_executor is None:
            try:
                cfg = muse_local_executor_config(
                    concurrency=concurrency,
                    max_iterations=max_iterations,
                    quiet_mode=quiet_mode,
                )
                effective_executor = AIAgentExecutor(
                    base_url=cfg.base_url,
                    api_key=cfg.api_key,
                    model=cfg.model,
                    provider=cfg.provider,
                    max_iterations=cfg.max_iterations,
                    concurrency=cfg.concurrency,
                    max_concurrency=cfg.max_concurrency,
                    quiet_mode=cfg.quiet_mode,
                )
                result.notes.append("executor: ai/muse-local")
            except Exception as exc:
                effective_executor = "prompt_only"
                result.notes.append(f"muse-local AI executor unavailable ({exc}); prompt_only")

        exec_impl = resolve_executor(
            effective_executor,
            base_url=base_url,
            api_key=api_key,
            model=model,
            provider=provider,
            max_iterations=max_iterations,
            concurrency=concurrency,
            quiet_mode=quiet_mode,
            allow_dirty=allow_dirty,
        )
        result.grains = exec_impl.run(repo_path, plan, specs)

        # Convergence — keep every grain (disjoint domains) and run the runtime
        # conflict backstop. A non-empty conflict set means drift escaped the
        # static + worktree layers and must be surfaced, never silently merged.
        result.convergence = _converge(result.grains)

        # Audit + coordination trails.
        _record_blackboard(plan, result.grains, memory_store)
        result.ledger_path = _write_decision_ledger(
            plan,
            result.grains,
            niches_used=result.niches_used,
            scout_packets=result.scout_packets,
        )

        # Learning capture — a dated, provenance-tagged record of the job.
        try:
            from hermes_cli.swarm.learning import capture_swarm_trace

            capture_swarm_trace(
                plan,
                result.grains,
                convergence=result.convergence,
                ledger_path=result.ledger_path,
            )
        except Exception:
            pass

        # Self-update loop (auto-apply reversible). Default apply hook records the
        # change + its rollback recipe (reversible by deletion; no silent edit).
        if apply_reversible:
            effective_apply = apply_fn
            if effective_apply is None:
                try:
                    from hermes_cli.swarm.learning import record_applied_update

                    effective_apply = record_applied_update
                except Exception:
                    effective_apply = None
            applied, queued = _emit_self_update(
                plan, result.grains, apply_fn=effective_apply
            )
            result.applied_updates = applied
            result.queued_updates = queued
    finally:
        if claim_domains:
            for grain in claimed:
                _specialist.release_grain(repo_path, plan.job_id, grain.grain_id)

    return result


def run_swarm_niche(
    goal: str,
    repo: Path | str = ".",
    **kwargs: Any,
) -> SwarmResult:
    """Niche AXIOM swarm: Scout prefetch + muse-local AI grains (prompt_only fallback).

    Pass ``executor="prompt_only"`` for deterministic smoke without a live model.
    Omit ``executor`` (or pass ``None``) to try muse-local AIAgentExecutor.
    """
    kwargs.pop("scout", None)
    kwargs.pop("niche_mode", None)
    return run_swarm(goal, repo, scout=True, niche_mode=True, **kwargs)
