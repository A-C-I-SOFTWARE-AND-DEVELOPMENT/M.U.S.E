"""muse — evidence-backed task-class model router.

This is the **single** model-route decision layer for muse It does
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
from typing import Any, Callable, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_gemma(model: Optional[str]) -> bool:
    """True if ``model`` names a Gemma 4 variant (tag or candidate name).

    Recognizes ``gemma4:e4b``, ``gemma4-e4b``, ``gemma4-26b-a4b``,
    ``ollama-local/gemma4-e2b`` and friends. Used only by surfaces/tests and
    scorecard family attribution — routing itself stays data-driven (a Gemma
    candidate is just whatever the policy's local route lists).
    """
    if not model:
        return False
    tail = model.rsplit("/", 1)[-1].lower()
    return tail.startswith("gemma4") or tail.startswith("gemma-4") or tail.startswith("gemma:")


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
    # Which local Gemma variant a lane should prefer, by job weight:
    #   "local_fast"      → E2B  (fast daily: chat/voice/summarize/memory)
    #   "local_reasoning" → E4B  (deeper reasoning)
    #   "local_coding"    → E4B  (coding / planning / test-debug)
    # Empty falls back to a catalog_task-derived purpose (back-compat).
    local_purpose: str = ""


# Cloud/server-first tier order for heavy *research* lanes: large autonomous
# research is too big for the small local Gemma variants (and 26B/31B don't fit
# an 8 GB box), so research routes to a hosted/worker/paid endpoint and only
# reaches local_oss as a last-ditch fallback.
_RESEARCH_TIERS: tuple[str, ...] = (
    "hosted_free_or_user_configured_oss",
    "claude_code_worker",
    "codex_worker",
    "paid_api_explicit_only",
    "local_oss",
)


# Per-class routing profile. ``coding_*`` / ``test_debug`` prefer the strong
# worker lanes (Claude Code / Codex) when enabled; chat/voice/summarize stay
# local-first for latency + privacy; *research* is explicitly off-local (cloud/
# server). Paid is only ever *allowed* for the heaviest classes, and even then
# only when the owner has opted in. ``local_purpose`` picks the Gemma variant by
# job weight (fast→E2B, reasoning/coding→E4B).
TASK_PROFILES: dict[TaskClass, TaskProfile] = {
    TaskClass.MOBILE_CHAT: TaskProfile("RC1", "mobile_chat", True, False, local_purpose="local_fast"),
    TaskClass.VOICE_REPLY: TaskProfile("RC1", "voice_reply", True, False, local_purpose="local_fast"),
    TaskClass.SUMMARIZATION: TaskProfile("RC1", "summarization", True, False, local_purpose="local_fast"),
    TaskClass.MEMORY_CURATOR: TaskProfile("RC1", "memory_curator", True, False, local_purpose="local_fast"),
    TaskClass.RESEARCH: TaskProfile(
        "RC2", "deep_research", False, True,
        preferred_tiers=_RESEARCH_TIERS, local_purpose="local_reasoning",
    ),
    TaskClass.CITATION_VERIFICATION: TaskProfile(
        "RC2", "citation_verification", False, True,
        preferred_tiers=_RESEARCH_TIERS, local_purpose="local_reasoning",
    ),
    TaskClass.CODING_PLAN: TaskProfile(
        "RC2", "reasoning", False, True,
        preferred_tiers=("claude_code_worker", "local_oss",
                         "hosted_free_or_user_configured_oss", "codex_worker",
                         "paid_api_explicit_only"),
        local_purpose="local_coding",
    ),
    TaskClass.CODING_BUILD: TaskProfile(
        "RC3", "agentic_coding", False, True,
        preferred_tiers=("claude_code_worker", "codex_worker", "local_oss",
                         "hosted_free_or_user_configured_oss",
                         "paid_api_explicit_only"),
        local_purpose="local_coding",
    ),
    TaskClass.CODING_REVIEW: TaskProfile(
        "RC2", "coding_review", False, True,
        preferred_tiers=("codex_worker", "claude_code_worker", "local_oss",
                         "hosted_free_or_user_configured_oss",
                         "paid_api_explicit_only"),
        local_purpose="local_coding",
    ),
    TaskClass.TEST_DEBUG: TaskProfile(
        "RC2", "bug_fix", False, True,
        preferred_tiers=("local_oss", "claude_code_worker", "codex_worker",
                         "hosted_free_or_user_configured_oss",
                         "paid_api_explicit_only"),
        local_purpose="local_coding",
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

    Paid routing is a *double gate*: at decision time (``route_for_task``) it is
    on when **either** this explicit, audited owner override says so **or**,
    when no override is set, the env-written policy flag
    (``HERMES_JARVIS_ENABLE_PAID`` → ``policy["paid"]["enabled"]``) is on. The
    override, once written, takes precedence over the policy flag in either
    direction (it can enable paid the policy left off, or disable paid the
    policy turned on); it is not merely a floor on top of the env. Clearing the
    override (``paid_enabled = None`` in the store) hands the decision back to
    the policy flag, so this never permanently locks paid routing on or off.
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


def _purpose_for(profile: TaskProfile) -> str:
    """The local-model purpose for a lane: fast / reasoning / coding."""
    if profile.local_purpose:
        return profile.local_purpose
    if "coding" in profile.catalog_task or profile.catalog_task in (
        "agentic_coding", "bug_fix",
    ):
        return "local_coding"
    return "local_reasoning"


def _gemma_variant_key(name: str) -> Optional[str]:
    """The variant token (``e2b``/``e4b``/``26b``/``31b``/``12b``) of a Gemma
    model name/tag, or ``None`` when it isn't a Gemma model."""
    if not is_gemma(name):
        return None
    low = name.lower()
    for key in ("e2b", "e4b", "26b", "31b", "12b"):
        if key in low:
            return key
    return None


def _gated_preferred_key(purpose: str) -> str:
    """Preferred Gemma variant token for ``purpose``, applying the load-gate.

    Fast lanes always prefer E2B. Reasoning/coding prefer E4B, **unless** a
    recorded smoke check shows E4B fails to load cleanly on this host — then we
    demote to E2B (``gemma_load_status.variant_failed`` is True only for a
    *demonstrated* failure, so a fresh/unprobed install still prefers E4B).
    """
    if purpose == "local_fast":
        return "e2b"
    key = "e4b"
    try:
        from hermes_cli.jarvis_prime import gemma_load_status as gls

        if gls.variant_failed("gemma4-e4b"):
            key = "e2b"
    except Exception:  # pragma: no cover - defensive (stripped install)
        pass
    return key


def _apply_gemma_policy(names: list[str], purpose: str) -> list[str]:
    """Reorder local candidates per the Gemma routing policy.

    Among the *available* Gemma variants, lead with the job-weight-preferred
    one (load-gated); keep the other small variant as immediate fallback; and
    sink 26B/31B to the tail so they are **never** an auto local default (they
    only fit workstation/server hardware and are a scorecard-gated fallback).
    Non-Gemma local models keep their order as a secondary fallback. When no
    Gemma model is present the list is returned unchanged.
    """
    preferred = _gated_preferred_key(purpose)
    order = [preferred] + [k for k in ("e2b", "e4b", "12b") if k != preferred]
    small: dict[str, list[str]] = {k: [] for k in order}
    big_gemma: list[str] = []   # 26B/31B — tail-only, never auto-default
    other_gemma: list[str] = []
    non_gemma: list[str] = []
    for n in names:
        key = _gemma_variant_key(n)
        if key in ("26b", "31b"):
            big_gemma.append(n)
        elif key in small:
            small[key].append(n)
        elif key is not None:
            other_gemma.append(n)
        else:
            non_gemma.append(n)
    ordered_small = [n for k in order for n in small[k]]
    return ordered_small + other_gemma + non_gemma + big_gemma


def _names_from_local_defaults(policy: dict[str, Any], purpose: str) -> list[str]:
    """Local candidate tags from the policy's per-purpose ``local_defaults``.

    Includes the purpose match first, then any sibling Gemma defaults (so the
    load-gate can substitute E2B↔E4B), then a generic fallback.
    """
    defaults = policy.get("local_defaults", [])
    names: list[str] = []
    for d in defaults:
        if d.get("purpose") == purpose:
            tag = d.get("ollama_tag") or d.get("model_id")
            if tag:
                names.append(tag)
    for d in defaults:
        if str(d.get("model_id", "")).startswith("gemma4"):
            tag = d.get("ollama_tag") or d.get("model_id")
            if tag and tag not in names:
                names.append(tag)
    if not names:
        for d in defaults:
            tag = d.get("ollama_tag") or d.get("model_id")
            if tag:
                names.append(tag)
                break
    return names


# ---------------------------------------------------------------------------
# Installed-model specialist routing (#9) — additive, opt-out via env.
# ---------------------------------------------------------------------------
#
# Seeded from the VERIFIED installed-model capability matrix (``ollama show``).
# Each entry maps a substring *name-pattern* (matched case-insensitively against
# a local candidate tag, after stripping any ``provider/`` prefix) to the
# specialist's verified capabilities and the task-router *lanes* it is the
# preferred local pick for. Lanes are the ``local_purpose`` weights used across
# this module (``local_coding`` / ``local_reasoning`` / ``local_fast``) plus a
# couple of explicit purpose tags for non-chat roles:
#
#   * ``local_vision``    — multimodal lanes (vision-capable models only).
#   * ``local_creative``  — companion / long-context creative lane.
#   * ``embedding``       — embedding/RAG only (never a chat candidate).
#
# ``tools``/``vision``/``thinking`` are recorded straight from the matrix and
# are advisory metadata only — routing keys off ``lanes``. This table is a
# *preference hint*: when a candidate matching the detected lane is present in
# the installed set it is led; otherwise the list is returned unchanged, so a
# host without these exact models keeps today's behavior byte-for-byte.


@dataclass(frozen=True)
class ModelSpecialist:
    """A verified installed model's capabilities + the lanes it specializes in."""

    pattern: str  # case-insensitive substring matched against a local tag tail
    lanes: tuple[str, ...]  # local_purpose weights this model is preferred for
    tools: bool = False
    vision: bool = False
    thinking: bool = False
    embedding: bool = False


# Ordered most-specific first so a coding/reasoning specialist is preferred over
# a generalist when a lane lists more than one. (qwen3-coder before qwen3.5 so a
# bare "qwen3" tail still resolves to the generalist via its own entry.)
MODEL_SPECIALISTS: tuple[ModelSpecialist, ...] = (
    # coding workhorse — agentic edits / refactor / build / test-debug
    ModelSpecialist(
        "qwen3-coder",
        lanes=("local_coding",),
        tools=True,
    ),
    # reasoning / planning / critic (no vision)
    ModelSpecialist(
        "gpt-oss",
        lanes=("local_reasoning",),
        tools=True,
        thinking=True,
    ),
    # alt reasoning lane
    ModelSpecialist(
        "ornith",
        lanes=("local_reasoning",),
        tools=True,
        thinking=True,
    ),
    # creative / companion + long-context ("the muse")
    ModelSpecialist(
        "qwythos",
        lanes=("local_creative",),
        tools=True,
        vision=True,
        thinking=True,
    ),
    # vision + balanced general
    ModelSpecialist(
        "gemma4:12b",
        lanes=("local_vision", "local_reasoning"),
        tools=True,
        vision=True,
        thinking=True,
    ),
    # fast all-rounder / default daily
    ModelSpecialist(
        "qwen3.5:9b",
        lanes=("local_fast", "local_vision"),
        tools=True,
        vision=True,
        thinking=True,
    ),
    # embeddings / RAG / memory — never a chat candidate
    ModelSpecialist(
        "bge-m3",
        lanes=("embedding",),
        embedding=True,
    ),
)


# Routing switch (default ON; owner-reversible at runtime). Set to a falsey
# value (0/false/no/off) to restore the legacy pre-specialist local ordering.
_SPECIALIST_ENV = "HERMES_JARVIS_SPECIALIST_ROUTING"


def _specialist_routing_enabled(env: Optional[dict[str, str]] = None) -> bool:
    """True unless the owner explicitly disabled installed-specialist routing."""
    source = env if env is not None else dict(os.environ)
    val = source.get(_SPECIALIST_ENV)
    if val is None:
        return True
    return val.strip().lower() not in ("0", "false", "no", "off")


def _specialist_for(name: str) -> Optional[ModelSpecialist]:
    """The first specialist whose pattern matches ``name`` (tail, lower), if any."""
    if not name:
        return None
    tail = name.rsplit("/", 1)[-1].lower()
    for spec in MODEL_SPECIALISTS:
        if spec.pattern in tail:
            return spec
    return None


def _prefer_specialist(names: list[str], purpose: str) -> list[str]:
    """Lead with installed specialists matching ``purpose``; keep the rest in order.

    Stable partition: candidates whose model matches a specialist for this lane
    are moved to the front (ordered by ``MODEL_SPECIALISTS`` priority, then by
    their original position), and every other candidate keeps its place behind
    them. ``embedding`` specialists are never chat candidates, so they are
    excluded from the preferred group regardless of lane. When no installed
    candidate matches the lane the list is returned unchanged — so the legacy
    (post-Gemma-policy) order is preserved exactly on a host without these
    models, or when disabled.
    """
    if not purpose or not _specialist_routing_enabled():
        return names

    def _rank(name: str) -> Optional[int]:
        spec = _specialist_for(name)
        if spec is None or spec.embedding:
            return None
        if purpose not in spec.lanes:
            return None
        return MODEL_SPECIALISTS.index(spec)

    preferred: list[tuple[int, int, str]] = []
    rest: list[str] = []
    for seq, name in enumerate(names):
        rank = _rank(name)
        if rank is None:
            rest.append(name)
        else:
            preferred.append((rank, seq, name))
    if not preferred:
        return names
    preferred.sort()
    return [name for _r, _s, name in preferred] + rest


def _local_candidates(policy: dict[str, Any], profile: TaskProfile) -> list[str]:
    route = policy.get("routes", {}).get("local_oss", {})
    purpose = _purpose_for(profile)
    names: list[str] = list(route.get("recommended_local_models") or [])
    if not names:
        names = _names_from_local_defaults(policy, purpose)
    if not names and route.get("enabled"):
        names.append("local-model")
    # Prefer an installed specialist for the detected lane BEFORE the Gemma
    # policy decides the lead. We apply the legacy Gemma ordering first to get
    # today's exact list, then float a matching installed specialist to the
    # front — so a specialist wins over the Gemma default, and when none matches
    # (or routing is disabled) the result is byte-for-byte the legacy order.
    names = _apply_gemma_policy(names, purpose)
    names = _prefer_specialist(names, purpose)
    # de-dup, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


# Hosted-tier task-class routing switch (default ON; owner-reversible at
# runtime). When ON, the configured hosted providers are expanded into ordered
# ``provider/model`` candidates drawn from the OSS catalog's per-task routing —
# so a coding build leads with coding families and research with reasoning
# families — without hardcoding model ids here. Set the env var to a falsey
# value (0/false/no/off) to restore the legacy bare-provider-id behavior.
_HOSTED_TASKCLASS_ENV = "HERMES_JARVIS_HOSTED_TASKCLASS"


def _hosted_taskclass_enabled(env: Optional[dict[str, str]] = None) -> bool:
    """True unless the owner explicitly disabled hosted task-class routing.

    Default ON. Recognized *disable* values: ``0/false/no/off`` (case-
    insensitive). This is a no-code rollback switch; the full revert is the
    patch itself.
    """
    source = env if env is not None else dict(os.environ)
    val = source.get(_HOSTED_TASKCLASS_ENV)
    if val is None:
        return True
    return val.strip().lower() not in ("0", "false", "no", "off")


def _hosted_candidates(route: dict[str, Any], profile: TaskProfile) -> list[str]:
    """Hosted-tier candidates, task-class-ordered from the OSS catalog.

    Default: expand each configured hosted provider into ordered
    ``provider/model`` candidates for this lane's ``catalog_task`` (filtered to
    the providers the owner actually configured). The order only feeds the
    router's intra-tier ``seq`` tiebreaker — scorecards and owner overrides
    still win, and no gate changes.

    Honesty ordering ("no fake certainty"): within the catalog's per-task
    order, families flagged ``candidate`` (just-released variant whose slugs +
    benchmarks aren't yet verified against the provider's live model list) are
    *sunk below* the verified families. This is a stable partition — relative
    order inside each group is preserved — so a lane whose hits are all-verified
    or all-candidate is byte-for-byte unchanged; only a mixed lane re-orders, and
    no candidate is ever DROPPED (it just sorts after the verified ones).

    Safe by construction:
      * Disabled (env switch) → the legacy bare provider-id list, unchanged.
      * No catalog match / PyYAML missing / any error → the bare provider list
        (``load_oss_catalog`` never raises; the ``except`` is a second belt).
      * Never *shrinks* the set: a configured provider the catalog didn't map
        for this lane is still appended as a tail fallback.
    """
    providers = list(route.get("providers") or [])
    if not providers or not _hosted_taskclass_enabled():
        return providers
    try:
        from hermes_cli.oss_model_brain import load_oss_catalog

        catalog = load_oss_catalog()
        hits = catalog.recommend(profile.catalog_task, available_providers=providers)
    except Exception:  # pragma: no cover - defensive (no catalog / no PyYAML)
        return providers

    # Stable verified-first partition: keep the catalog's order within each
    # group, but place verified families ahead of candidate-tagged ones.
    verified: list[str] = []
    candidate: list[str] = []
    for model in hits:
        ref = model.resolve_provider(providers)
        if ref is None:
            continue
        cand = f"{ref.provider}/{ref.model}"
        bucket = candidate if getattr(model, "candidate", False) else verified
        if cand not in verified and cand not in candidate:
            bucket.append(cand)
    ordered: list[str] = verified + candidate
    # Never drop a configured provider the catalog didn't map for this lane.
    # Compare provider prefixes case-insensitively: ``resolve_provider`` matches
    # case-insensitively and returns the catalog's casing, so a policy provider
    # like ``"OpenRouter"`` must not be re-appended as a duplicate of the
    # expanded ``openrouter/...`` candidates.
    ordered_prefixes = {c.split("/", 1)[0].casefold() for c in ordered}
    for p in providers:
        if p.casefold() not in ordered_prefixes:
            ordered.append(p)
            ordered_prefixes.add(p.casefold())
    return ordered or providers


def _tier_candidates(policy: dict[str, Any], tier: str, profile: TaskProfile) -> list[str]:
    routes = policy.get("routes", {})
    route = routes.get(tier, {})
    if not route.get("enabled"):
        return []
    if tier == "local_oss":
        return _local_candidates(policy, profile)
    if tier == "hosted_free_or_user_configured_oss":
        return _hosted_candidates(route, profile)
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
    seq: int = 0  # stable position in the candidate build order (intra-tier rank)

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

    # Family-level evidence index. An *expanded* hosted candidate
    # ("openrouter/z-ai/glm-5") carries no exact scorecard key, but a scorecard
    # recorded under the family/variant id ("glm-5") should still inform it.
    # Exact match always wins; this is a fallback ONLY for provider/model hosted
    # strings (those containing "/"), so local/worker variants keep exact-match
    # semantics (no e2b/e4b conflation). Coarse-by-family on purpose, consistent
    # with how promotion baselines compare families.
    _family_fn: Optional[Callable[[str], str]] = None
    measured_by_family: dict[str, tuple[float, int]] = {}
    if measured:
        try:
            from hermes_cli.jarvis_prime.model_scorecard import model_family

            _family_fn = model_family
        except Exception:  # pragma: no cover - defensive (stripped install)
            _family_fn = None
        if _family_fn is not None:
            for _m, _sn in measured.items():
                _f = _family_fn(_m)
                if _f and (_f not in measured_by_family or _sn[0] > measured_by_family[_f][0]):
                    measured_by_family[_f] = _sn

    # Build candidates, honoring paid gating.
    candidates: list[Candidate] = []
    for rank, tier in enumerate(tier_order):
        if tier == "paid_api_explicit_only" and not (paid_enabled and profile.paid_allowed):
            continue
        for model in _tier_candidates(policy, tier, profile):
            score_n = measured.get(model)
            if score_n is None and _family_fn is not None and "/" in model:
                score_n = measured_by_family.get(_family_fn(model))
            candidates.append(
                Candidate(
                    model=model,
                    tier=tier,
                    tier_rank=rank,
                    score=score_n[0] if score_n else None,
                    samples=score_n[1] if score_n else 0,
                    seq=len(candidates),
                )
            )

    # Deterministic ranking: effective score desc, then tier preference, then
    # the candidate's build position (so the local-policy ordering from
    # ``_tier_candidates`` is authoritative for equal-score same-tier ties —
    # e.g. Gemma E4B leading E2B for coding), and finally name as a last resort.
    candidates.sort(key=lambda c: (-c.effective, c.tier_rank, c.seq, c.model))

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
    "is_gemma",
    "TaskClass",
    "TaskProfile",
    "TASK_PROFILES",
    "ModelSpecialist",
    "MODEL_SPECIALISTS",
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
