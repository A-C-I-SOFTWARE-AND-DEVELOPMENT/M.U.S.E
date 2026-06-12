"""Hermes model/worker registry.

This module is the Python-level loader for
``docs/ai-intelligence/model-registry.yaml``. The YAML file is the
source of truth (so non-Python consumers — docs, skills, the Android
companion app — can read it too); this module exposes the same data as
typed objects to the rest of Hermes.

Design goals
------------

1. **Single source of truth.** The YAML is canonical. This module never
   silently invents workers that aren't in the YAML.
2. **Cheap to import.** The registry is small (a couple dozen workers),
   so we eagerly parse on first call and cache for the rest of the
   process. No I/O on every routing decision.
3. **Robust to missing YAML.** If the YAML is unreadable (e.g., the
   user is running a stripped-down install), we fall back to a minimal
   built-in registry that covers the workers ``model_router.py``
   references by name. This keeps the router operational and tests
   hermetic.
4. **No code in the YAML.** Detection / run-mode / approval policy
   are declarative dicts. The router interprets them; the registry
   just hands them over.

The registry is consumed by:

- ``muse_cli/model_router.py`` (the routing engine).
- ``skills/model-router/SKILL.md`` (the runtime entry point — reads
  the YAML directly so the skill remains self-contained).
- ``docs/ai-intelligence/tool-capability-matrix.md`` (a static table
  kept in sync by review).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

# The YAML lives next to the docs that explain the routing policy. We
# resolve it relative to the repo root so the loader works whether
# Hermes is run from a checkout, an installed wheel, or a packaged app.
_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_PATH = (
    _REPO_ROOT / "docs" / "ai-intelligence" / "model-registry.yaml"
)


# ---------------------------------------------------------------------------
# Worker entry
# ---------------------------------------------------------------------------

QUALITY_TIERS = ("draft", "standard", "high", "critical")
SPEED_TIERS = ("slow", "medium", "fast", "instant")
COST_TIERS = ("free", "low", "medium", "high")
PRIVACY_TIERS = ("local", "standard", "cloud")
RISK_TIERS = ("low", "medium", "high")


@dataclass(frozen=True)
class WorkerEntry:
    """One row of the worker registry.

    All optional fields default to empty containers so callers can
    iterate them without ``None`` checks. The frozen=True makes
    WorkerEntry hashable; the router uses sets of workers internally.
    """

    id: str
    provider: str = ""
    surface: str = ""
    strengths: tuple[str, ...] = ()
    best_for: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    detection: tuple[tuple[str, Any], ...] = ()
    run_mode: tuple[tuple[str, Any], ...] = ()
    quality: str = "standard"
    speed: str = "medium"
    cost: str = "medium"
    privacy: str = "standard"
    risk: str = "low"
    validation: tuple[tuple[str, Any], ...] = ()
    fallbacks: tuple[str, ...] = ()
    approval_required: bool = False
    approval_triggers: tuple[str, ...] = ()
    notes: str = ""
    # Eval gating (ROUTE-2). Backward compatible: default unverified. A worker is
    # only eligible to be the default for an eval-gated task category when
    # ``eval_passed`` is True. ``eval_results`` is a tuple-of-pairs (suite -> score
    # / metadata) to stay frozen/hashable, mirroring ``validation``.
    eval_passed: bool = False
    eval_results: tuple[tuple[str, Any], ...] = ()

    @property
    def detection_dict(self) -> dict[str, Any]:
        return dict(self.detection)

    @property
    def run_mode_dict(self) -> dict[str, Any]:
        return dict(self.run_mode)

    @property
    def validation_dict(self) -> dict[str, Any]:
        return dict(self.validation)

    @property
    def eval_results_dict(self) -> dict[str, Any]:
        return dict(self.eval_results)


# ---------------------------------------------------------------------------
# Registry container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Registry:
    workers: tuple[WorkerEntry, ...]
    source: str  # "yaml" or "builtin" — exposed for diagnostics
    path: str | None = None

    def __post_init__(self) -> None:
        # Reject duplicate IDs at construction time; ambiguous routing
        # is worse than a hard error during startup.
        seen: set[str] = set()
        for w in self.workers:
            if w.id in seen:
                raise ValueError(f"duplicate worker id in registry: {w.id!r}")
            seen.add(w.id)

    def ids(self) -> list[str]:
        return [w.id for w in self.workers]

    def get(self, worker_id: str) -> WorkerEntry | None:
        for w in self.workers:
            if w.id == worker_id:
                return w
        return None

    def require(self, worker_id: str) -> WorkerEntry:
        w = self.get(worker_id)
        if w is None:
            raise KeyError(f"unknown worker id: {worker_id!r}")
        return w

    def by_category(self, category: str) -> list[WorkerEntry]:
        return [w for w in self.workers if category in w.categories]


# ---------------------------------------------------------------------------
# YAML loader (best-effort; falls back to the built-in registry)
# ---------------------------------------------------------------------------


def _coerce_tuple(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,)


def _coerce_pairs(value: Any) -> tuple[tuple[str, Any], ...]:
    """Convert a nested mapping into a tuple-of-pairs (hashable form)."""
    if not isinstance(value, dict):
        return ()
    return tuple((str(k), v) for k, v in value.items())


def _worker_from_yaml(raw: dict[str, Any]) -> WorkerEntry:
    return WorkerEntry(
        id=str(raw.get("id") or "").strip(),
        provider=str(raw.get("provider") or ""),
        surface=str(raw.get("surface") or ""),
        strengths=tuple(str(s) for s in (raw.get("strengths") or [])),
        best_for=tuple(str(s) for s in (raw.get("best_for") or [])),
        categories=tuple(str(s) for s in (raw.get("categories") or [])),
        detection=_coerce_pairs(raw.get("detection")),
        run_mode=_coerce_pairs(raw.get("run_mode")),
        quality=str(raw.get("quality") or "standard"),
        speed=str(raw.get("speed") or "medium"),
        cost=str(raw.get("cost") or "medium"),
        privacy=str(raw.get("privacy") or "standard"),
        risk=str(raw.get("risk") or "low"),
        validation=_coerce_pairs(raw.get("validation")),
        fallbacks=tuple(str(s) for s in (raw.get("fallbacks") or [])),
        approval_required=bool(raw.get("approval_required") or False),
        approval_triggers=tuple(
            str(s) for s in (raw.get("approval_triggers") or [])
        ),
        notes=str(raw.get("notes") or ""),
        eval_passed=bool(raw.get("eval_passed") or False),
        eval_results=_coerce_pairs(raw.get("eval_results")),
    )


def _load_yaml_registry(path: Path) -> Registry | None:
    """Parse the YAML at *path*. Returns ``None`` if YAML is unavailable
    or the file is missing / malformed."""
    try:
        import yaml
    except ImportError:
        return None
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = yaml.safe_load(raw_text) or {}
    except Exception:
        return None
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        return None
    workers = []
    for entry in models:
        if not isinstance(entry, dict):
            continue
        worker = _worker_from_yaml(entry)
        if not worker.id:
            continue
        workers.append(worker)
    if not workers:
        return None
    return Registry(workers=tuple(workers), source="yaml", path=str(path))


# ---------------------------------------------------------------------------
# Built-in fallback registry
# ---------------------------------------------------------------------------

# The built-in registry is intentionally narrow — it has the workers the
# router refers to by ID plus the approval / category metadata the
# routing rules in ``model_router.py`` rely on. It is not a substitute
# for the YAML; it is a safety net so the router still produces a
# sensible plan when the YAML is missing (e.g., in a hermetic test
# environment that hasn't copied the docs directory).

_BUILTIN: tuple[WorkerEntry, ...] = (
    WorkerEntry(
        id="hermes-local",
        provider="hermes",
        surface="internal",
        strengths=("repo evidence", "validation", "planning", "memory"),
        best_for=("validation", "planning", "plumbing"),
        categories=(
            "planning",
            "validation",
            "backend-orchestration",
            "user-profile-learning",
        ),
        quality="high",
        speed="fast",
        cost="free",
        privacy="local",
        risk="low",
        fallbacks=(),
    ),
    WorkerEntry(
        id="claude-code-windows",
        provider="anthropic",
        surface="cli-tunnel",
        strengths=(
            "long-context review",
            "multi-file reasoning",
            "repo-wide refactor",
            "architecture",
        ),
        best_for=("refactor", "implementation", "architecture"),
        categories=(
            "refactor",
            "implementation",
            "backend-orchestration",
            "remote-execution",
        ),
        detection=(
            ("command", "claude"),
            ("tunnel", "claude-code-windows"),
        ),
        quality="critical",
        speed="medium",
        cost="high",
        privacy="cloud",
        risk="medium",
        approval_required=True,
        approval_triggers=("remote-tunnel-setup",),
        fallbacks=("claude-code-local", "codex", "hermes-local"),
    ),
    WorkerEntry(
        id="claude-code-local",
        provider="anthropic",
        surface="cli",
        strengths=(
            "long-context review",
            "multi-file reasoning",
            "careful diffs",
        ),
        best_for=("refactor", "implementation", "code_review"),
        categories=("refactor", "implementation", "debug"),
        detection=(("command", "claude"),),
        quality="critical",
        speed="medium",
        cost="high",
        privacy="cloud",
        risk="low",
        fallbacks=("codex", "aider", "hermes-local"),
    ),
    WorkerEntry(
        id="codex",
        provider="openai",
        surface="cli",
        strengths=(
            "implementation",
            "tests",
            "patch-oriented edits",
        ),
        best_for=("implementation", "test_repair", "bug_fix"),
        categories=("implementation", "debug", "validation"),
        detection=(("command", "codex"),),
        quality="high",
        speed="fast",
        cost="medium",
        privacy="cloud",
        risk="low",
        fallbacks=("aider", "claude-code-local", "hermes-local"),
    ),
    WorkerEntry(
        id="aider",
        provider="paul-gauthier",
        surface="cli",
        strengths=(
            "git-aware paired edits",
            "surgical multi-file patches",
            "explicit diff output",
        ),
        best_for=("refactor_small", "bug_fix", "implementation"),
        categories=("implementation", "refactor", "debug"),
        detection=(("command", "aider"),),
        quality="high",
        speed="medium",
        cost="low",
        privacy="cloud",
        risk="low",
        fallbacks=("codex", "claude-code-local", "hermes-local"),
    ),
    WorkerEntry(
        id="goose",
        provider="block",
        surface="cli",
        strengths=(
            "local shell + file agent",
            "extensions",
            "recipes",
        ),
        best_for=("plumbing", "implementation"),
        categories=("implementation", "backend-orchestration"),
        detection=(("command", "goose"),),
        quality="standard",
        speed="medium",
        cost="low",
        privacy="cloud",
        risk="low",
        fallbacks=("aider", "codex", "hermes-local"),
    ),
    WorkerEntry(
        id="chatgpt-handoff",
        provider="openai",
        surface="user-driven",
        strengths=(
            "user-driven reasoning",
            "uses existing ChatGPT subscription",
        ),
        best_for=("manual_handoff", "research"),
        categories=("research", "planning"),
        detection=(("manual_only", True),),
        quality="high",
        speed="slow",
        cost="free",
        privacy="cloud",
        risk="medium",
        fallbacks=("hermes-local",),
    ),
    WorkerEntry(
        id="browser-research",
        provider="hermes",
        surface="tool",
        strengths=(
            "current external docs",
            "URL fetch",
            "search summarization",
        ),
        best_for=("research",),
        categories=("research",),
        detection=(("tool", "browser"),),
        quality="high",
        speed="fast",
        cost="low",
        privacy="cloud",
        risk="low",
        fallbacks=("hermes-local",),
    ),
    WorkerEntry(
        id="github-publisher",
        provider="hermes",
        surface="internal",
        strengths=(
            "branch / push / PR / comment",
            "gated writes",
            "allowlisted repos",
        ),
        best_for=("github_publish",),
        categories=("github-pr", "deployment"),
        detection=(("internal", True),),
        quality="high",
        speed="fast",
        cost="free",
        privacy="cloud",
        risk="high",
        approval_required=True,
        approval_triggers=("publish",),
        fallbacks=("hermes-local",),
    ),
    WorkerEntry(
        id="supabase-worker",
        provider="supabase",
        surface="mcp",
        strengths=(
            "Supabase schema/migration",
            "row-level security",
            "edge functions",
        ),
        best_for=("deployment", "backend-orchestration"),
        categories=("deployment", "backend-orchestration", "remote-execution"),
        detection=(("mcp", "supabase"),),
        quality="high",
        speed="medium",
        cost="medium",
        privacy="cloud",
        risk="high",
        approval_required=True,
        approval_triggers=("schema", "deployment"),
        fallbacks=("hermes-local",),
    ),
    WorkerEntry(
        id="vercel-worker",
        provider="vercel",
        surface="mcp",
        strengths=(
            "Vercel deployment",
            "preview environments",
            "edge config",
        ),
        best_for=("deployment",),
        categories=("deployment", "remote-execution"),
        detection=(("mcp", "vercel"),),
        quality="high",
        speed="fast",
        cost="medium",
        privacy="cloud",
        risk="high",
        approval_required=True,
        approval_triggers=("deployment",),
        fallbacks=("hermes-local",),
    ),
    WorkerEntry(
        id="android-builder",
        provider="hermes",
        surface="local",
        strengths=(
            "Android Gradle build",
            "Termux runtime",
            "Jetpack/Compose",
        ),
        best_for=("mobile-android",),
        categories=("mobile-android", "deployment"),
        detection=(("command", "gradle"),),
        quality="high",
        speed="medium",
        cost="free",
        privacy="local",
        risk="medium",
        fallbacks=("hermes-local",),
    ),
    WorkerEntry(
        id="human-approval",
        provider="user",
        surface="user-driven",
        strengths=(
            "approval for destructive actions",
            "consent for remote execution",
            "policy gate",
        ),
        best_for=("secrets-management", "deployment", "remote-execution"),
        categories=(
            "secrets-management",
            "deployment",
            "remote-execution",
            "github-pr",
            "security",
        ),
        detection=(("internal", True),),
        quality="critical",
        speed="slow",
        cost="free",
        privacy="local",
        risk="low",
        approval_required=True,
        approval_triggers=(
            "secrets",
            "destructive",
            "publish",
            "remote-tunnel-setup",
            "continuous-listening",
        ),
        fallbacks=(),
    ),
)


_BUILTIN_REGISTRY = Registry(workers=_BUILTIN, source="builtin", path=None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_cache: dict[str, Registry] = {}


def load_registry(path: str | os.PathLike[str] | None = None) -> Registry:
    """Load the registry from *path* (defaults to ``DEFAULT_REGISTRY_PATH``).

    The result is cached per resolved path for the life of the process.
    If the YAML is missing or unreadable, the built-in fallback registry
    is returned and its ``.source`` is set to ``"builtin"``.
    """

    resolved = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    key = str(resolved.resolve()) if resolved.exists() else f"missing:{resolved}"
    if key in _cache:
        return _cache[key]
    reg = _load_yaml_registry(resolved) if resolved.exists() else None
    if reg is None:
        reg = _BUILTIN_REGISTRY
    _cache[key] = reg
    return reg


def builtin_registry() -> Registry:
    """Return the built-in registry directly (for tests / diagnostics)."""

    return _BUILTIN_REGISTRY


def reset_cache() -> None:
    """Clear the in-process registry cache."""

    _cache.clear()


def merge_registries(*regs: Registry) -> Registry:
    """Merge several registries; later workers with the same id override
    earlier ones. Used when a host-local YAML extends the shipped one."""

    merged: dict[str, WorkerEntry] = {}
    for r in regs:
        for w in r.workers:
            merged[w.id] = w
    return Registry(
        workers=tuple(merged.values()),
        source="merged",
        path=None,
    )


def required_worker_ids() -> tuple[str, ...]:
    """The worker IDs the router relies on by name.

    Used by ``tests/test_model_router.py`` to assert that the YAML on
    disk has not silently dropped a required entry.
    """

    return (
        "hermes-local",
        "claude-code-windows",
        "claude-code-local",
        "codex",
        "aider",
        "goose",
        "chatgpt-handoff",
        "browser-research",
        "github-publisher",
        "supabase-worker",
        "vercel-worker",
        "android-builder",
        "human-approval",
    )


def iter_categories(reg: Registry) -> Iterable[str]:
    """Yield each category mentioned by any worker (unique, sorted)."""

    seen: set[str] = set()
    for w in reg.workers:
        for c in w.categories:
            if c not in seen:
                seen.add(c)
                yield c
