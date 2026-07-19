"""Hermes model/tool routing engine.

The router answers a single question: **for this task, which worker(s)
should run, in what order, and what approvals does that require?**

It is deterministic, evidence-first, and honest about what it doesn't
know. Two calls with the same inputs produce the same plan.

The companion docs spell out the full policy:

- ``docs/ai-intelligence/model-registry.yaml`` — worker catalog.
- ``docs/ai-intelligence/model-routing-policy.md`` — scoring rubric.
- ``docs/ai-intelligence/tool-capability-matrix.md`` — capabilities.
- ``skills/model-router/SKILL.md`` — runtime entry point.

What this module produces
-------------------------

``route(...)`` returns a :class:`RoutingDecision` with:

- ``selected`` — the workers Hermes intends to run, in order.
- ``rejected`` — every other registered worker plus the reason it
  was passed over (detection failure, capability gap, approval not
  granted, etc.).
- ``explanation`` — one-paragraph human-readable rationale.
- ``ledger_entry`` — a dict suitable for appending to
  ``decision_ledger.jsonl``.
- ``fallback_plan`` — ordered fallback ladder if the primary fails
  validation (terminates at ``hermes-local``).
- ``approval_requirements`` — list of approval tags the user must
  grant before the plan can execute.
- ``validation_plan`` — concrete validation steps Hermes will run
  after the primary worker returns.

The router never *executes* anything. It just produces the plan. The
caller is responsible for running the workers, validating the result,
and walking the fallback ladder if validation fails.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable

from utils import env_var_enabled

from hermes_cli.model_registry import (
    Registry,
    WorkerEntry,
    load_registry,
)


# ---------------------------------------------------------------------------
# Task categories
# ---------------------------------------------------------------------------

# Canonical task categories. The router rejects categories outside this
# set rather than guessing — the caller has to be explicit. (See
# ``model-routing-policy.md`` for what each category means.)
TASK_CATEGORIES: tuple[str, ...] = (
    "mobile-android",
    "voice-pipeline",
    "backend-orchestration",
    "research",
    "planning",
    "implementation",
    "refactor",
    "debug",
    "validation",
    "security",
    "deployment",
    "github-pr",
    "user-profile-learning",
    "remote-execution",
    "secrets-management",
)


# Categories where human approval is mandatory (per the phase routing
# rules). The router will always include ``human-approval`` in the
# selected workers and emit approval requirements when the task falls
# into one of these buckets.
APPROVAL_GATED_CATEGORIES: frozenset[str] = frozenset(
    {
        "secrets-management",
        "deployment",
        "github-pr",
        "remote-execution",
        "security",
    }
)


# Categories where browser research is required because current external
# documentation is part of the answer.
BROWSER_REQUIRED_CATEGORIES: frozenset[str] = frozenset({"research"})


# Maps a task category to its required-capability hints. This is a
# coarse mapping used to disqualify workers that obviously can't do
# the work; the fine-grained scoring happens in :func:`_score`.
_CATEGORY_REQUIRED_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "mobile-android": ("android",),
    "voice-pipeline": ("voice",),
    "backend-orchestration": ("orchestration",),
    "research": ("network_fetch",),
    "planning": (),
    "implementation": ("write_files", "run_terminal"),
    "refactor": ("multi_file_refactor",),
    "debug": ("read_files", "run_tests"),
    "validation": ("validation_local",),
    "security": (),
    "deployment": ("github_write",),
    "github-pr": ("github_write",),
    "user-profile-learning": ("persistent_memory",),
    "remote-execution": ("tunnel",),
    "secrets-management": (),
}


# Preferred workers by category. The router still scores each worker,
# but a category preference acts as a tie-break boost and is used to
# explain why one worker was picked over another. (Mirrors the routing
# rules in the phase spec.)
_CATEGORY_PREFERENCES: dict[str, tuple[str, ...]] = {
    "implementation": ("codex", "aider", "claude-code-local"),
    "refactor": ("claude-code-windows", "claude-code-local", "aider"),
    "debug": ("codex", "aider", "claude-code-local"),
    "validation": ("hermes-local",),
    "research": ("browser-research", "chatgpt-handoff"),
    "planning": ("hermes-local",),
    "mobile-android": ("android-builder",),
    "voice-pipeline": ("hermes-local",),
    "backend-orchestration": ("hermes-local", "claude-code-windows"),
    "deployment": ("github-publisher", "vercel-worker", "supabase-worker"),
    "github-pr": ("github-publisher",),
    "user-profile-learning": ("hermes-local",),
    "remote-execution": ("claude-code-windows",),
    "secrets-management": ("human-approval", "hermes-local"),
    "security": ("hermes-local", "claude-code-local"),
}


# ---------------------------------------------------------------------------
# Routing decision
# ---------------------------------------------------------------------------


@dataclass
class WorkerSelection:
    """One selected worker plus the rationale for picking it."""

    worker_id: str
    role: str  # "primary", "validator", "publisher", "researcher", "approver"
    score: float
    rationale: str
    approval_required: bool = False


@dataclass
class RoutingDecision:
    """The output of :func:`route` — everything a caller needs to act."""

    task_id: str
    task_category: str
    task_summary: str
    selected: list[WorkerSelection]
    rejected: dict[str, str]
    primary: str | None
    fallback_plan: list[str]
    validator: str
    publisher: str | None
    explanation: str
    approval_requirements: list[str]
    validation_plan: list[str]
    ledger_entry: dict[str, Any]
    registry_source: str
    created_at: float

    # ------------------------------------------------------------------
    # Convenience views
    # ------------------------------------------------------------------

    def selected_ids(self) -> list[str]:
        return [s.worker_id for s in self.selected]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_category": self.task_category,
            "task_summary": self.task_summary,
            "selected": [asdict(s) for s in self.selected],
            "rejected": dict(self.rejected),
            "primary": self.primary,
            "fallback_plan": list(self.fallback_plan),
            "validator": self.validator,
            "publisher": self.publisher,
            "explanation": self.explanation,
            "approval_requirements": list(self.approval_requirements),
            "validation_plan": list(self.validation_plan),
            "ledger_entry": dict(self.ledger_entry),
            "registry_source": self.registry_source,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Routing context (what the caller knows about the host)
# ---------------------------------------------------------------------------


@dataclass
class RouterContext:
    """Host facts the router relies on.

    All fields are optional so callers can hand the router only what
    they know. Missing facts are treated as "unknown" — the router
    falls back to conservative defaults.
    """

    available_workers: set[str] | None = None
    tunnel_healthy: bool = False
    prefer_local: bool = False
    offline: bool = False
    needs_external_docs: bool = False
    approvals_granted: set[str] = field(default_factory=set)
    user_preferences: list[str] = field(default_factory=list)
    cost_ceiling: str = "high"  # low | medium | high | unlimited
    quality_floor: str = "draft"  # draft | standard | high | critical
    continuous_listening: bool = False
    # ROUTE-2 eval gate. Opt-in set of task categories for which a worker must
    # have ``eval_passed=True`` to be a candidate. Empty (default) → no change
    # to existing routing behavior. Internal infra workers are exempt.
    require_eval_for: frozenset[str] = field(default_factory=frozenset)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_QUALITY_RANK = {"draft": 0, "standard": 1, "high": 2, "critical": 3}
_SPEED_RANK = {"slow": 0, "medium": 1, "fast": 2, "instant": 3}
_COST_RANK = {"unlimited": 3, "high": 2, "medium": 1, "low": 0, "free": 0}
# For cost as a *score*, cheaper is higher.
_COST_SCORE = {"free": 1.0, "low": 0.75, "medium": 0.5, "high": 0.25}
_SPEED_SCORE = {"instant": 1.0, "fast": 0.75, "medium": 0.5, "slow": 0.25}
_QUALITY_SCORE = {"critical": 1.0, "high": 0.75, "standard": 0.5, "draft": 0.25}


def _task_id(category: str, summary: str) -> str:
    h = hashlib.sha1(f"{category}|{summary}".encode("utf-8")).hexdigest()[:10]
    return f"route-{category}-{h}"


def _passes_cost_ceiling(worker: WorkerEntry, ceiling: str) -> bool:
    if ceiling == "unlimited":
        return True
    return _COST_RANK.get(worker.cost, 1) <= _COST_RANK.get(ceiling, 2)


def _passes_quality_floor(worker: WorkerEntry, floor: str) -> bool:
    return _QUALITY_RANK.get(worker.quality, 1) >= _QUALITY_RANK.get(floor, 0)


def _strength_overlap(worker: WorkerEntry, category: str) -> float:
    """Fraction of category-related strengths the worker advertises.

    The router treats the category itself, the per-category preference
    keywords, and ``worker.categories`` as the strength vocabulary. A
    worker that lists the category as one of its ``categories`` scores
    at least 0.5 even without a preference match.
    """
    matches = 0
    targets = 3  # category match, best_for match, preference match

    if category in worker.categories:
        matches += 1
    if any(category in bf or bf in category for bf in worker.best_for):
        matches += 1
    prefs = _CATEGORY_PREFERENCES.get(category, ())
    if worker.id in prefs:
        # Earlier preferences score higher (1.0 for #1, 0.66 for #2, …).
        rank = prefs.index(worker.id)
        matches += max(0.0, 1.0 - 0.34 * rank)
    return min(1.0, matches / targets)


def _score(worker: WorkerEntry, category: str, ctx: RouterContext) -> float:
    """Compute the worker's score for this task. Higher = better.

    Weights mirror ``model-routing-policy.md`` §4: strengths dominate,
    speed/cost are tie-breakers, validation locality nudges the result
    toward Hermes' own validation surface.
    """

    score = 0.0
    score += 0.40 * _strength_overlap(worker, category)
    score += 0.20 * _QUALITY_SCORE.get(worker.quality, 0.5)
    score += 0.15 * _SPEED_SCORE.get(worker.speed, 0.5)
    score += 0.15 * _COST_SCORE.get(worker.cost, 0.5)

    # Validation locality: ``hermes-local`` always validates, so workers
    # closer to it score a hair higher. This is what makes Hermes
    # itself appear as the validator in every plan.
    if worker.id == "hermes-local":
        score += 0.05

    # Local-first bias under prefer_local or offline mode.
    if ctx.prefer_local or ctx.offline:
        if worker.privacy == "local":
            score += 0.10
        elif worker.privacy == "cloud":
            score -= 0.20

    # User preferences re-rank within the candidate set.
    if worker.id in ctx.user_preferences:
        rank = ctx.user_preferences.index(worker.id)
        score += max(0.0, 0.10 - 0.02 * rank)

    return round(score, 4)


def _is_available(
    worker: WorkerEntry, ctx: RouterContext
) -> tuple[bool, str | None]:
    """Whether the router will consider this worker. Returns (ok, reason)."""

    # Internal workers are always available.
    if worker.id in {"hermes-local", "github-publisher", "human-approval"}:
        return True, None

    if ctx.available_workers is not None:
        if worker.id not in ctx.available_workers:
            return False, "not detected on this host"

    # Cloud workers are off the table when fully offline.
    if ctx.offline and worker.privacy == "cloud":
        return False, "offline mode: cloud worker excluded"

    # Claude Code Windows specifically requires a healthy secure tunnel.
    if worker.id == "claude-code-windows" and not ctx.tunnel_healthy:
        return False, "secure tunnel to Windows host is not healthy"

    return True, None


def _approvals_needed(
    category: str, ctx: RouterContext, selected_ids: Iterable[str]
) -> list[str]:
    """Compute the union of approval tags the plan needs."""

    needs: list[str] = []
    selected_set = set(selected_ids)

    if category in APPROVAL_GATED_CATEGORIES:
        if category == "secrets-management":
            needs.append("secrets")
        if category == "deployment":
            needs.append("deployment")
        if category == "github-pr":
            needs.append("publish")
        if category == "remote-execution":
            needs.append("remote-tunnel-setup")
        if category == "security":
            needs.append("security-review")

    if ctx.continuous_listening:
        needs.append("continuous-listening")

    # Worker-specific approval triggers (Supabase needs schema/deploy;
    # Vercel needs deploy; github-publisher needs publish; etc.)
    for wid in selected_set:
        if wid == "supabase-worker":
            needs.append("schema-approval")
        if wid == "vercel-worker":
            needs.append("deployment")
        if wid == "github-publisher":
            needs.append("publish")
        if wid == "claude-code-windows":
            needs.append("remote-tunnel-setup")

    # De-dup while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for n in needs:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _validation_plan(category: str, selected_ids: list[str]) -> list[str]:
    """Concrete validation steps. ``hermes-local`` always owns them."""

    plan: list[str] = ["hermes-local: confirm worker outputs match request"]
    if category in {"implementation", "refactor", "debug", "test_repair"}:
        plan.append("hermes-local: run project test suite")
        plan.append("hermes-local: run lint/type checks if configured")
        plan.append("hermes-local: review git diff before publish")
    if category == "deployment":
        plan.append("hermes-local: dry-run deployment plan; require human-approval")
        plan.append("hermes-local: verify rollback path documented")
    if category == "github-pr":
        plan.append("hermes-local: confirm branch + PR draft built; require publish approval")
    if category == "research":
        plan.append("hermes-local: spot-check at least one citation")
        plan.append("hermes-local: confirm no secrets in research output")
    if category == "secrets-management":
        plan.append("hermes-local: scrub secrets from logs and ledger entry")
        plan.append("human-approval: confirm any secret write")
    if category == "remote-execution":
        plan.append("hermes-local: confirm tunnel health before and after")
    if "supabase-worker" in selected_ids:
        plan.append("supabase-worker: dry-run migration; require schema approval")
    if "vercel-worker" in selected_ids:
        plan.append("vercel-worker: build a preview deployment first")
    if "android-builder" in selected_ids:
        plan.append("android-builder: assemble debug APK; run instrumentation smoke test")
    return plan


# ---------------------------------------------------------------------------
# Public routing entry point
# ---------------------------------------------------------------------------


def route(
    task: str,
    category: str,
    *,
    context: RouterContext | None = None,
    registry: Registry | None = None,
) -> RoutingDecision:
    """Plan a worker line-up for *task* in *category*.

    The router never executes the plan; it returns a structured
    :class:`RoutingDecision` for the caller to act on.

    Hard rules enforced here (per phase spec):
      * ``hermes-local`` is always in ``selected``.
      * ``human-approval`` is added when the category is approval-gated
        or continuous-listening mode is on.
      * ``browser-research`` is added when the task needs current docs.
      * ``supabase-worker`` is held back unless schema/deployment
        approval is granted.
      * ``vercel-worker`` is held back unless deployment approval is
        granted.
      * ``claude-code-windows`` is only selected when the secure tunnel
        is healthy.
    """

    if category not in TASK_CATEGORIES:
        raise ValueError(
            f"unknown task category {category!r}; "
            f"expected one of: {', '.join(TASK_CATEGORIES)}"
        )

    ctx = context or RouterContext()
    # HERMES_OFFLINE is an environment floor: when the host declares itself
    # offline, cloud workers are off the table regardless of caller context, so
    # force offline + local-first. Explicit ``offline=True`` callers are
    # unchanged; we only ever raise the floor, never lower it.
    if env_var_enabled("HERMES_OFFLINE") and not ctx.offline:
        ctx = replace(ctx, offline=True, prefer_local=True)
    reg = registry or load_registry()

    # ------------------------------------------------------------------
    # Build candidate set
    # ------------------------------------------------------------------

    candidates: list[tuple[WorkerEntry, float]] = []
    rejected: dict[str, str] = {}

    for worker in reg.workers:
        # chatgpt-handoff is never auto-routed; user opts in explicitly.
        if worker.id == "chatgpt-handoff" and worker.id not in ctx.user_preferences:
            rejected[worker.id] = "manual handoff: only selected on explicit user opt-in"
            continue

        ok, reason = _is_available(worker, ctx)
        if not ok:
            rejected[worker.id] = reason or "unavailable"
            continue

        if not _passes_cost_ceiling(worker, ctx.cost_ceiling):
            rejected[worker.id] = (
                f"cost tier {worker.cost!r} exceeds ceiling {ctx.cost_ceiling!r}"
            )
            continue

        if not _passes_quality_floor(worker, ctx.quality_floor):
            rejected[worker.id] = (
                f"quality tier {worker.quality!r} below floor {ctx.quality_floor!r}"
            )
            continue

        # ROUTE-2: eval gate. For an opted-in category, exclude workers that
        # have not passed project evals — so an unverified worker can't become
        # the default. Internal infra workers are exempt.
        if (
            category in ctx.require_eval_for
            and not worker.eval_passed
            and worker.id not in {"hermes-local", "github-publisher", "human-approval"}
        ):
            rejected[worker.id] = f"eval gate: not eval-passed for category {category!r}"
            continue

        # Approval-gated workers are held back unless their approval
        # tag has been granted. The router still records them as
        # *candidates*, but if approval isn't granted we surface that
        # in the rejection map and let the caller solicit approval.
        if worker.id == "supabase-worker" and "schema-approval" not in ctx.approvals_granted:
            rejected[worker.id] = "requires schema/deployment approval"
            continue
        if worker.id == "vercel-worker" and "deployment" not in ctx.approvals_granted:
            rejected[worker.id] = "requires deployment approval"
            continue

        score = _score(worker, category, ctx)
        candidates.append((worker, score))

    candidates.sort(key=lambda t: (-t[1], t[0].id))

    # ------------------------------------------------------------------
    # Choose primary + fallback ladder
    # ------------------------------------------------------------------

    selected: list[WorkerSelection] = []
    selected_ids: list[str] = []

    # hermes-local always rides along.
    hermes = reg.get("hermes-local")
    if hermes is not None:
        selected.append(
            WorkerSelection(
                worker_id="hermes-local",
                role="validator",
                score=_score(hermes, category, ctx),
                rationale="muse local is always included for validation + memory.",
            )
        )
        selected_ids.append("hermes-local")

    # Workers that fill special roles (publisher, approver, researcher)
    # are slotted in by role below — they shouldn't accidentally become
    # the primary just because their tiers scored well.
    _NEVER_PRIMARY = {"github-publisher", "human-approval", "browser-research"}

    primary_worker: WorkerEntry | None = None
    for worker, score in candidates:
        if worker.id == "hermes-local":
            continue
        if worker.id in _NEVER_PRIMARY:
            continue
        # Don't promote a worker whose category coverage is zero — that
        # means it scored on tier weights alone and isn't actually a
        # suitable primary for this task.
        if _strength_overlap(worker, category) <= 0.0:
            continue
        primary_worker = worker
        selected.append(
            WorkerSelection(
                worker_id=worker.id,
                role="primary",
                score=score,
                rationale=_primary_rationale(worker, category, ctx),
                approval_required=worker.approval_required,
            )
        )
        selected_ids.append(worker.id)
        break

    if primary_worker is None and hermes is not None:
        # Re-tag Hermes as primary if nothing else is available.
        selected[0] = WorkerSelection(
            worker_id="hermes-local",
            role="primary",
            score=selected[0].score,
            rationale="No external worker available; muse local is the primary.",
        )

    # Browser research as a sidecar when current external docs matter.
    if (
        category in BROWSER_REQUIRED_CATEGORIES or ctx.needs_external_docs
    ) and reg.get("browser-research") is not None:
        if "browser-research" not in selected_ids:
            br = reg.require("browser-research")
            selected.append(
                WorkerSelection(
                    worker_id="browser-research",
                    role="researcher",
                    score=_score(br, category, ctx),
                    rationale="Current external docs are required; browser-research is added.",
                )
            )
            selected_ids.append("browser-research")

    # Approval gate: bring in human-approval when the category demands it
    # or when continuous-listening / destructive flows are active.
    needs_approval = (
        category in APPROVAL_GATED_CATEGORIES
        or ctx.continuous_listening
        or any(reg.get(wid) and reg.require(wid).approval_required for wid in selected_ids)
    )
    if (
        needs_approval
        and reg.get("human-approval") is not None
        and "human-approval" not in selected_ids
    ):
        ha = reg.require("human-approval")
        selected.append(
            WorkerSelection(
                worker_id="human-approval",
                role="approver",
                score=_score(ha, category, ctx),
                rationale=(
                    "Human approval is required for this category "
                    "(secrets/destructive/publish/remote tunnel/continuous listening)."
                ),
                approval_required=True,
            )
        )
        selected_ids.append("human-approval")

    # Publisher: only assigned for github-pr / deployment categories.
    publisher: str | None = None
    if category in {"github-pr", "deployment"}:
        if reg.get("github-publisher") is not None and "github-publisher" not in selected_ids:
            gp = reg.require("github-publisher")
            selected.append(
                WorkerSelection(
                    worker_id="github-publisher",
                    role="publisher",
                    score=_score(gp, category, ctx),
                    rationale="Publish step requires github-publisher (gated writes).",
                    approval_required=True,
                )
            )
            selected_ids.append("github-publisher")
        publisher = "github-publisher" if reg.get("github-publisher") else None

    # Fallback ladder. Build from the primary's declared fallbacks (if
    # the primary is in the registry), then append the next-best
    # candidates by score, then ensure hermes-local terminates the
    # ladder so nothing dead-ends.
    fallback_plan: list[str] = []
    if primary_worker is not None:
        for fb in primary_worker.fallbacks:
            entry = reg.get(fb)
            if entry is None:
                continue
            ok, _ = _is_available(entry, ctx)
            if not ok:
                continue
            if fb not in fallback_plan and fb != primary_worker.id:
                fallback_plan.append(fb)
    for worker, _score_val in candidates:
        if primary_worker is not None and worker.id == primary_worker.id:
            continue
        if worker.id in fallback_plan:
            continue
        if worker.id == "hermes-local":
            continue
        # Skip special-purpose roles — they aren't drop-in replacements
        # for the primary worker. They have their own slots in the
        # selected list (publisher / approver / researcher).
        if worker.id in {"github-publisher", "human-approval", "browser-research"}:
            continue
        # Only include workers that share the task category. Otherwise
        # the ladder fills with workers that scored OK on tier weights
        # but aren't actually suitable substitutes.
        if category not in worker.categories and not any(
            category in bf or bf in category for bf in worker.best_for
        ):
            continue
        fallback_plan.append(worker.id)
    # hermes-local always terminates the ladder. If a primary worker's
    # declared fallbacks already mentioned it, move it to the end so
    # the terminal-fallback invariant holds regardless of how it got
    # in there.
    while "hermes-local" in fallback_plan:
        fallback_plan.remove("hermes-local")
    fallback_plan.append("hermes-local")

    # Account for any candidate that didn't land in selected or
    # fallback — the policy guarantees "no silent drops". A candidate
    # that wasn't promoted to any role is listed in rejected with a
    # tag so the audit trail is complete.
    accounted = set(selected_ids) | set(fallback_plan)
    for worker, _score_val in candidates:
        if worker.id in accounted:
            continue
        if worker.id in rejected:
            continue
        rejected[worker.id] = "available but not selected for this task category"

    # Validator is always hermes-local — non-negotiable.
    validator = "hermes-local"

    approval_requirements = _approvals_needed(category, ctx, selected_ids)
    validation_plan = _validation_plan(category, selected_ids)

    summary = (task or "").strip().splitlines()[0] if task else ""
    if len(summary) > 200:
        summary = summary[:197] + "..."

    explanation = _build_explanation(
        category=category,
        primary=primary_worker.id if primary_worker else "hermes-local",
        rejected=rejected,
        ctx=ctx,
        approval_requirements=approval_requirements,
    )

    task_id_value = _task_id(category, summary)
    created_at = time.time()

    ledger_entry = {
        "schema": "hermes.routing.decision.v1",
        "task_id": task_id_value,
        "task_category": category,
        "task_summary": summary,
        "selected": [s.worker_id for s in selected],
        "primary": primary_worker.id if primary_worker else "hermes-local",
        "fallback_plan": list(fallback_plan),
        "validator": validator,
        "publisher": publisher,
        "rejected": dict(rejected),
        "approval_requirements": list(approval_requirements),
        "registry_source": reg.source,
        "created_at": created_at,
    }

    # Flywheel: routing decisions are part of the daily digest. Soft —
    # the router's contract (pure planning, no side effects that can
    # fail the caller) is preserved.
    try:
        from hermes_cli.jarvis_prime import flywheel as _flywheel

        _flywheel.record(
            "model.routed",
            {
                "category": category,
                "primary": primary_worker.id if primary_worker else "hermes-local",
                "selected": [s.worker_id for s in selected],
                "summary": summary,
            },
            outcome="success",
        )
    except Exception:
        pass

    return RoutingDecision(
        task_id=task_id_value,
        task_category=category,
        task_summary=summary,
        selected=selected,
        rejected=rejected,
        primary=primary_worker.id if primary_worker else "hermes-local",
        fallback_plan=fallback_plan,
        validator=validator,
        publisher=publisher,
        explanation=explanation,
        approval_requirements=approval_requirements,
        validation_plan=validation_plan,
        ledger_entry=ledger_entry,
        registry_source=reg.source,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# Explanation builders
# ---------------------------------------------------------------------------


def _primary_rationale(
    worker: WorkerEntry, category: str, ctx: RouterContext
) -> str:
    parts: list[str] = []
    prefs = _CATEGORY_PREFERENCES.get(category, ())
    if worker.id in prefs:
        rank = prefs.index(worker.id) + 1
        parts.append(
            f"{worker.id} is the #{rank} preferred worker for category {category!r}."
        )
    else:
        parts.append(
            f"{worker.id} scored highest among available workers for category {category!r}."
        )
    if worker.id == "claude-code-windows" and ctx.tunnel_healthy:
        parts.append("Secure tunnel to the Windows host is healthy.")
    if ctx.prefer_local and worker.privacy == "local":
        parts.append("Local-first preference is active.")
    if ctx.offline:
        parts.append("Offline mode is active.")
    return " ".join(parts)


def _build_explanation(
    *,
    category: str,
    primary: str,
    rejected: dict[str, str],
    ctx: RouterContext,
    approval_requirements: list[str],
) -> str:
    bits = [
        f"Category {category!r} routed to primary={primary}.",
        f"hermes-local is included for validation.",
    ]
    if approval_requirements:
        bits.append(
            "Approval required: " + ", ".join(approval_requirements) + "."
        )
    if rejected:
        # Don't dump the full rejection map into the explanation — keep
        # it scannable. The ledger entry has the full list.
        bits.append(f"{len(rejected)} worker(s) rejected; see ledger for details.")
    if ctx.offline:
        bits.append("Offline mode excluded all cloud workers.")
    if ctx.prefer_local:
        bits.append("Local-first preference biased scoring.")
    return " ".join(bits)


# ---------------------------------------------------------------------------
# Convenience helpers for callers / templates
# ---------------------------------------------------------------------------


def render_report(decision: RoutingDecision) -> str:
    """Render the decision as the worker-selection report template.

    Mirrors ``templates/orchestration/worker-selection-report.md`` so
    callers can ``print(render_report(decision))`` and get a
    reviewable artifact without keeping markdown logic in two places.
    """
    lines: list[str] = []
    lines.append(f"# Worker selection — {decision.task_id}")
    lines.append("")
    lines.append(f"**Category:** `{decision.task_category}`  ")
    lines.append(f"**Summary:** {decision.task_summary or '(none)'}  ")
    lines.append(f"**Primary:** `{decision.primary}`  ")
    lines.append(f"**Validator:** `{decision.validator}`  ")
    lines.append(f"**Publisher:** `{decision.publisher or '—'}`  ")
    lines.append(f"**Registry:** `{decision.registry_source}`")
    lines.append("")
    lines.append("## Selected workers")
    lines.append("")
    lines.append("| worker | role | score | approval | rationale |")
    lines.append("| --- | --- | ---:| :---: | --- |")
    for s in decision.selected:
        approval = "yes" if s.approval_required else "—"
        lines.append(
            f"| `{s.worker_id}` | {s.role} | {s.score:.2f} | {approval} | {s.rationale} |"
        )
    lines.append("")
    lines.append("## Rejected workers")
    lines.append("")
    if not decision.rejected:
        lines.append("_None rejected._")
    else:
        for wid, reason in decision.rejected.items():
            lines.append(f"- `{wid}` — {reason}")
    lines.append("")
    lines.append("## Fallback plan")
    lines.append("")
    if decision.fallback_plan:
        for i, wid in enumerate(decision.fallback_plan, start=1):
            lines.append(f"{i}. `{wid}`")
    else:
        lines.append("_No fallbacks — terminal worker only._")
    lines.append("")
    lines.append("## Approval requirements")
    lines.append("")
    if decision.approval_requirements:
        for tag in decision.approval_requirements:
            lines.append(f"- `{tag}`")
    else:
        lines.append("_No approval required._")
    lines.append("")
    lines.append("## Validation plan")
    lines.append("")
    for step in decision.validation_plan:
        lines.append(f"- {step}")
    lines.append("")
    lines.append("## Explanation")
    lines.append("")
    lines.append(decision.explanation)
    lines.append("")
    lines.append("## Ledger entry")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(decision.ledger_entry, indent=2, sort_keys=True))
    lines.append("```")
    return "\n".join(lines)
