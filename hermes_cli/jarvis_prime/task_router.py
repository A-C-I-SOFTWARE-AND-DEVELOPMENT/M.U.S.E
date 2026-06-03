"""JARVIS Prime — evidence-backed task-class model router.

This is the **single** model-route decision layer for JARVIS Prime. It does
not detect providers, score outcomes, or store scorecards itself; it *composes*
the four layers that already exist:

* **policy** — :mod:`hermes_cli.jarvis_prime.model_bootstrap`
  (``load_policy``): free/local-first route order + paid explicit opt-in.
* **evidence** — :mod:`hermes_cli.jarvis_prime.model_scorecard`
  (``ScorecardBook.recommend`` + ``ModelScorecard.score_for``): measured
  per-(model, task) outcomes, re-weighted per task class.
* **catalog** — the route map's candidate models (local recommendations,
  hosted providers, worker lanes, paid providers).
* **owner override** — a small, owner-gated override store so the phone can
  pin a model or flip paid routing.

Given a :class:`TaskClass` it answers: *which model should run this, why, and
what is the fallback chain* — deterministically, stdlib-only, and fully
injectable so tests never touch the network, real hardware, or a real policy.

Ranking rule (deterministic):

* A candidate with recorded scorecard samples is ranked by its task-class
  score (``ModelScorecard.score_for``).
* A candidate with no samples gets a *tier prior* derived from the free/
  local-first route order, so a fresh install routes local-first and a
  measured-strong model can overtake that prior — but a measured-weak model
  never beats the local-first prior. Scorecards genuinely move the choice.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskClass(Enum):
    """The mobile-first task classes JARVIS routes models for."""

    MOBILE_CHAT = "mobile_chat"
    RESEARCH = "research"
    CITATION_VERIFICATION = "citation_verification"
    CODING_PLAN = "coding_plan"
    CODING_BUILD = "coding_build"
    CODING_REVIEW = "coding_review"
    TEST_DEBUG = "test_debug"
    SUMMARIZATION = "summarization"
    MEMORY_CURATOR = "memory_curator"
    VOICE_REPLY = "voice_reply"

    @classmethod
    def from_value(cls, value: str) -> "TaskClass":
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"unknown task class: {value!r}")


# The free/local-first route tiers, lowest index = most preferred. Mirrors
# ``model_bootstrap.ROUTE_ORDER`` exactly (kept as a literal so this module
# stays import-light and works even on a stripped install).
ROUTE_TIERS: tuple[str, ...] = (
    "local_oss",
    "hosted_free_or_user_configured_oss",
    "claude_code_worker",
    "codex_worker",
    "paid_api_explicit_only",
)


@dataclass(frozen=True)
class TaskProfile:
    risk_class: str
    catalog_task: str  # maps to oss_model_brain known tasks (advisory)
    local_first: bool
    paid_allowed: bool
    # Optional per-class re-ordering of the route tiers. When empty the
    # free/local-first ROUTE_TIERS order is used.
    preferred_tiers: tuple[str, ...] = ()


# Per-class routing profile. ``coding_*`` / ``test_debug`` prefer the strong
# worker lanes (Claude Code / Codex) when enabled; chat/voice/summarize stay
# local-first for latency + privacy. Paid is only ever *allowed* for the
# heaviest classes, and even then only when the owner has opted in.
TASK_PROFILES: dict[TaskClass, TaskProfile] = {
    TaskClass.MOBILE_CHAT: TaskProfile("RC1", "reasoning", True, False),
    TaskClass.VOICE_REPLY: TaskProfile("RC1", "reasoning", True, False),
    TaskClass.SUMMARIZATION: TaskProfile("RC1", "reasoning", True, False),
    TaskClass.MEMORY_CURATOR: TaskProfile("RC1", "reasoning", True, False),
    TaskClass.RESEARCH: TaskProfile("RC2", "reasoning", True, True),
    TaskClass.CITATION_VERIFICATION: TaskProfile("RC2", "reasoning", True, True),
    TaskClass.CODING_PLAN: TaskProfile(
        "RC2", "reasoning", False, True,
        preferred_tiers=("claude_code_worker", "local_oss",
                         "hosted_free_or_user_configured_oss", "codex_worker",
                         "paid_api_explicit_only"),
    ),
    TaskClass.CODING_BUILD: TaskProfile(
        "RC3", "agentic_coding", False, True,
        preferred_tiers=("claude_code_worker", "codex_worker", "local_oss",
                         "hosted_free_or_user_configured_oss",
                         "paid_api_explicit_only"),
    ),
    TaskClass.CODING_REVIEW: TaskProfile(
        "RC2", "coding", False, True,
        preferred_tiers=("codex_worker", "claude_code_worker", "local_oss",
                         "hosted_free_or_user_configured_oss",
                         "paid_api_explicit_only"),
    ),
    TaskClass.TEST_DEBUG: TaskProfile(
        "RC2", "bug_fix", False, True,
        preferred_tiers=("local_oss", "claude_code_worker", "codex_worker",
                         "hosted_free_or_user_configured_oss",
                         "paid_api_explicit_only"),
    ),
}


# ---------------------------------------------------------------------------
# Owner override store (owner-gated; pins a model or flips paid routing)
# ---------------------------------------------------------------------------


def overrides_path() -> Path:
    """``${HERMES_HOME:-~/.hermes}/jarvis_prime/model_route_overrides.json``."""
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "jarvis_prime" / "model_route_overrides.json"


def load_overrides(path: Optional[Path] = None) -> dict[str, Any]:
    target = Path(path) if path else overrides_path()
    if not target.is_file():
        return {"version": 1, "paid_enabled": None, "task_overrides": {}}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "paid_enabled": None, "task_overrides": {}}
    data.setdefault("version", 1)
    data.setdefault("paid_enabled", None)
    data.setdefault("task_overrides", {})
    return data


def _save_overrides(data: dict[str, Any], path: Optional[Path] = None) -> Path:
    target = Path(path) if path else overrides_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now_iso()
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".routes-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target


def set_task_override(
    task_class: str, model: Optional[str], *, path: Optional[Path] = None
) -> dict[str, Any]:
    """Pin (``model``) or clear (``model is None``) a task's model. Reversible."""
    TaskClass.from_value(task_class)  # validate
    data = load_overrides(path)
    if model:
        data["task_overrides"][task_class] = model
    else:
        data["task_overrides"].pop(task_class, None)
    _save_overrides(data, path)
    return data


def set_paid_enabled(
    enabled: bool, *, authorized: bool, path: Optional[Path] = None
) -> dict[str, Any]:
    """Flip the owner-gated paid-routing override.

    ``authorized`` MUST be True — flipping a money-spend gate is owner-gated.
    The env opt-in (``HERMES_JARVIS_ENABLE_PAID``) remains a floor; this only
    layers an explicit, audited owner decision on top.
    """
    if not authorized:
        raise PermissionError("enabling paid routing requires owner authorization")
    data = load_overrides(path)
    data["paid_enabled"] = bool(enabled)
    data["authorized_by"] = "owner"
    _save_overrides(data, path)
    return data


# ---------------------------------------------------------------------------
# Policy resolution
# ---------------------------------------------------------------------------


def _default_policy() -> dict[str, Any]:
    """A minimal, honest policy used only when none has been written yet.

    Local-first with a generic local candidate; everything else disabled.
    The live cockpit normally has a real ``model_policy.json``.
    """
    return {
        "route_order": list(ROUTE_TIERS),
        "routes": {
            "local_oss": {"enabled": True, "recommended_local_models": [], "runtimes": []},
            "hosted_free_or_user_configured_oss": {"enabled": False, "providers": []},
            "claude_code_worker": {"enabled": False},
            "codex_worker": {"enabled": False},
            "paid_api_explicit_only": {"enabled": False, "providers_detected": []},
        },
        "paid": {"enabled": False},
        "local_defaults": [],
        "_default": True,
    }


def resolve_policy(policy: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    if policy is not None:
        return policy
    try:
        from hermes_cli.jarvis_prime import model_bootstrap as mb

        loaded = mb.load_policy()
    except Exception:  # pragma: no cover - defensive (stripped install)
        loaded = None
    return loaded if loaded is not None else _default_policy()


def _local_candidates(policy: dict[str, Any], profile: TaskProfile) -> list[str]:
    route = policy.get("routes", {}).get("local_oss", {})
    names: list[str] = list(route.get("recommended_local_models") or [])
    if not names:
        purpose = "local_coding" if "coding" in profile.catalog_task or profile.catalog_task in (
            "agentic_coding", "bug_fix",
        ) else "local_reasoning"
        for d in policy.get("local_defaults", []):
            if d.get("purpose") == purpose:
                tag = d.get("ollama_tag") or d.get("model_id")
                if tag:
                    names.append(tag)
        # also accept the generic reasoning default if nothing matched
        if not names:
            for d in policy.get("local_defaults", []):
                tag = d.get("ollama_tag") or d.get("model_id")
                if tag:
                    names.append(tag)
                    break
    if not names and route.get("enabled"):
        names.append("local-model")
    # de-dup, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _tier_candidates(policy: dict[str, Any], tier: str, profile: TaskProfile) -> list[str]:
    routes = policy.get("routes", {})
    route = routes.get(tier, {})
    if not route.get("enabled"):
        return []
    if tier == "local_oss":
        return _local_candidates(policy, profile)
    if tier == "hosted_free_or_user_configured_oss":
        return list(route.get("providers") or [])
    if tier == "claude_code_worker":
        return ["claude"]
    if tier == "codex_worker":
        return ["codex"]
    if tier == "paid_api_explicit_only":
        return list(route.get("providers_detected") or [])
    return []


def _tier_prior(rank: int) -> float:
    """Neutral prior for an unmeasured candidate, by route-tier preference."""
    return max(0.30, 0.55 - 0.05 * rank)


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    model: str
    tier: str
    tier_rank: int
    score: Optional[float]  # task-class scorecard score, if measured
    samples: int = 0

    @property
    def effective(self) -> float:
        return self.score if self.score is not None else _tier_prior(self.tier_rank)


@dataclass
class ModelRouteDecision:
    task_class: str
    chosen: Optional[str]
    route_tier: Optional[str]
    risk_class: str
    fallback_chain: list[str]
    why: str
    evidence: list[dict[str, Any]]
    local_first: bool
    paid_allowed: bool
    paid_enabled: bool
    owner_override: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_class": self.task_class,
            "chosen": self.chosen,
            "route_tier": self.route_tier,
            "risk_class": self.risk_class,
            "fallback_chain": list(self.fallback_chain),
            "why": self.why,
            "evidence": list(self.evidence),
            "local_first": self.local_first,
            "paid_allowed": self.paid_allowed,
            "paid_enabled": self.paid_enabled,
            "owner_override": self.owner_override,
        }


def route_for_task(
    task_class: "TaskClass | str",
    *,
    policy: Optional[dict[str, Any]] = None,
    book: Optional[Any] = None,
    overrides: Optional[dict[str, Any]] = None,
    overrides_path_: Optional[Path] = None,
) -> ModelRouteDecision:
    """Decide which model should run ``task_class`` and explain why."""

    tc = task_class if isinstance(task_class, TaskClass) else TaskClass.from_value(task_class)
    profile = TASK_PROFILES[tc]
    policy = resolve_policy(policy)
    overrides = overrides if overrides is not None else load_overrides(overrides_path_)

    # Paid is enabled when the owner override says so, else the policy flag.
    ov_paid = overrides.get("paid_enabled")
    paid_enabled = bool(ov_paid) if ov_paid is not None else bool(
        policy.get("paid", {}).get("enabled", False)
    )

    # Tier ordering: per-class preference if set, else free/local-first order.
    tier_order = profile.preferred_tiers or ROUTE_TIERS

    # Evidence: scorecards filtered to this task class.
    if book is None:
        try:
            from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook

            book = ScorecardBook.load()
        except Exception:  # pragma: no cover - defensive
            book = None
    # Evidence is scoped by task class (which already implies the relevant
    # risk grouping); we deliberately do NOT filter by risk_class here so a
    # scorecard recorded for the task class always informs the route.
    measured: dict[str, tuple[float, int]] = {}
    if book is not None:
        for model, score, n in book.recommend(tc.value, task_class=tc.value):
            measured[model] = (score, n)

    # Build candidates, honoring paid gating.
    candidates: list[Candidate] = []
    for rank, tier in enumerate(tier_order):
        if tier == "paid_api_explicit_only" and not (paid_enabled and profile.paid_allowed):
            continue
        for model in _tier_candidates(policy, tier, profile):
            score_n = measured.get(model)
            candidates.append(
                Candidate(
                    model=model,
                    tier=tier,
                    tier_rank=rank,
                    score=score_n[0] if score_n else None,
                    samples=score_n[1] if score_n else 0,
                )
            )

    # Deterministic ranking: effective score desc, then tier preference, then name.
    candidates.sort(key=lambda c: (-c.effective, c.tier_rank, c.model))

    evidence = [
        {"model": m, "score": round(s, 4), "samples": n}
        for m, (s, n) in sorted(measured.items(), key=lambda kv: -kv[1][0])
    ]

    owner_override = overrides.get("task_overrides", {}).get(tc.value)
    if owner_override:
        chain = [owner_override] + [c.model for c in candidates if c.model != owner_override]
        why = (
            f"Owner override: {tc.value} is pinned to '{owner_override}'. "
            f"Auto-route fallbacks: {', '.join(chain[1:]) or 'none'}."
        )
        return ModelRouteDecision(
            task_class=tc.value,
            chosen=owner_override,
            route_tier="owner_override",
            risk_class=profile.risk_class,
            fallback_chain=chain,
            why=why,
            evidence=evidence,
            local_first=profile.local_first,
            paid_allowed=profile.paid_allowed,
            paid_enabled=paid_enabled,
            owner_override=owner_override,
        )

    if not candidates:
        why = (
            f"No enabled route offers a model for {tc.value}. Bootstrap a local "
            f"runtime (e.g. Ollama) or configure a provider; paid routing is "
            f"{'on' if paid_enabled else 'off'}."
        )
        return ModelRouteDecision(
            task_class=tc.value,
            chosen=None,
            route_tier=None,
            risk_class=profile.risk_class,
            fallback_chain=[],
            why=why,
            evidence=evidence,
            local_first=profile.local_first,
            paid_allowed=profile.paid_allowed,
            paid_enabled=paid_enabled,
            owner_override=None,
        )

    top = candidates[0]
    chain = [c.model for c in candidates]
    if top.score is not None:
        basis = (
            f"chosen by measured evidence (score {top.score:.2f} over "
            f"{top.samples} sample{'s' if top.samples != 1 else ''})"
        )
    else:
        basis = (
            f"chosen by {'local-first ' if top.tier == 'local_oss' else ''}"
            f"policy preference ({top.tier}); no scorecards yet for {tc.value}"
        )
    why = (
        f"{tc.value}: route → {top.model} [{top.tier}] — {basis}. "
        f"Fallbacks: {', '.join(chain[1:]) or 'none'}. "
        f"Paid routing {'enabled' if paid_enabled else 'disabled'}; "
        f"risk {profile.risk_class}."
    )
    return ModelRouteDecision(
        task_class=tc.value,
        chosen=top.model,
        route_tier=top.tier,
        risk_class=profile.risk_class,
        fallback_chain=chain,
        why=why,
        evidence=evidence,
        local_first=profile.local_first,
        paid_allowed=profile.paid_allowed,
        paid_enabled=paid_enabled,
        owner_override=None,
    )


def all_routes(
    *,
    policy: Optional[dict[str, Any]] = None,
    book: Optional[Any] = None,
    overrides: Optional[dict[str, Any]] = None,
    overrides_path_: Optional[Path] = None,
) -> list[ModelRouteDecision]:
    """Route decisions for every task class (one shared policy/evidence load)."""
    policy = resolve_policy(policy)
    if overrides is None:
        overrides = load_overrides(overrides_path_)
    if book is None:
        try:
            from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook

            book = ScorecardBook.load()
        except Exception:  # pragma: no cover - defensive
            book = None
    return [
        route_for_task(tc, policy=policy, book=book, overrides=overrides)
        for tc in TaskClass
    ]


def explain(decision: ModelRouteDecision) -> str:
    """Human-readable rationale for a routing decision."""
    head = (
        f"JARVIS model route — {decision.task_class}\n"
        f"  chosen : {decision.chosen or '(none available)'}"
        f"{' [' + decision.route_tier + ']' if decision.route_tier else ''}\n"
        f"  why    : {decision.why}"
    )
    if decision.fallback_chain[1:]:
        head += "\n  chain  : " + " → ".join(decision.fallback_chain)
    if decision.evidence:
        head += "\n  evidence:"
        for e in decision.evidence:
            head += f"\n    - {e['model']}: score={e['score']:.2f} (n={e['samples']})"
    return head


__all__ = [
    "TaskClass",
    "TaskProfile",
    "TASK_PROFILES",
    "ROUTE_TIERS",
    "ModelRouteDecision",
    "route_for_task",
    "all_routes",
    "explain",
    "overrides_path",
    "load_overrides",
    "set_task_override",
    "set_paid_enabled",
    "resolve_policy",
]
