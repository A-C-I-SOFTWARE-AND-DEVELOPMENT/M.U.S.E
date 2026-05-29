"""JARVIS Prime — Open-Source Model Brain.

Loads ``docs/ai-intelligence/oss-model-catalog.yaml`` (the canonical,
cross-referenced catalog of open-weight models JARVIS Prime can learn
from) into typed objects and answers the question:

    "What is the best open model for task X, given the providers I have
     installed and my privacy constraints?"

This is the *model* layer. It is deliberately separate from:

* ``model_registry.py`` — the *worker* layer (which agent executes a task).
* ``providers/`` + ``plugins/model-providers/`` — the *transport* layer
  (how to physically reach a provider's API).

The brain maps a task category to an ordered preference of model
*families*, resolves each family to a concrete ``(provider, model)`` pair
using the providers actually installed on the host, and returns the
result with the benchmark evidence and source URLs attached.

Design goals (same spirit as ``model_registry.py``):

1. **Single source of truth.** The YAML is canonical so docs, skills, and
   the Android app can read it too. This module never invents a model
   that isn't in the catalog.
2. **Cheap + stdlib-friendly.** PyYAML is imported lazily; if it is
   missing or the file is unreadable we fall back to a built-in catalog
   that covers the routing the CLI relies on, so tests stay hermetic.
3. **Refreshable, not frozen.** Each family carries ``current_variant`` +
   ``updated_at`` + ``sources`` so the fast-moving frontier can be
   re-validated without changing the routing logic.

Provenance: original work, MIT-licensed with hermes-agent. The
local-first emphasis is inspired by OpenHuman
(github.com/tinyhumansai/openhuman, GPL-3.0) — concept only, no code
copied.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

# ---------------------------------------------------------------------------
# Locations / constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG_PATH = (
    _REPO_ROOT / "docs" / "ai-intelligence" / "oss-model-catalog.yaml"
)

TIERS = ("frontier", "strong", "local")
# Higher rank = preferred when sorting fallback candidates of equal task fit.
_TIER_RANK = {"frontier": 3, "strong": 2, "local": 1}


# ---------------------------------------------------------------------------
# Typed model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderRef:
    """A way to reach a model: a provider plugin id + that provider's model id."""

    provider: str
    model: str

    def to_dict(self) -> dict[str, str]:
        return {"provider": self.provider, "model": self.model}


@dataclass(frozen=True)
class OssModel:
    """One open-weight model family from the catalog.

    ``frozen=True`` makes it hashable so callers can dedupe with sets.
    Collection fields are tuples for the same reason.
    """

    id: str
    vendor: str = ""
    license: str = ""
    license_spdx: str = ""
    open_weights: bool = True
    tier: str = "strong"
    current_variant: str = ""
    context_window: int = 0
    params: str = ""
    local: bool = False
    local_runner: str = ""
    best_for: tuple[str, ...] = ()
    benchmarks: tuple[tuple[str, float], ...] = ()
    providers: tuple[ProviderRef, ...] = ()
    why: str = ""
    sources: tuple[str, ...] = ()

    @property
    def benchmarks_dict(self) -> dict[str, float]:
        return dict(self.benchmarks)

    @property
    def top_benchmark(self) -> float:
        """Best (highest) benchmark value, or 0.0 — a coarse quality proxy."""
        return max((v for _, v in self.benchmarks), default=0.0)

    def resolve_provider(
        self, available: Optional[Iterable[str]] = None
    ) -> Optional[ProviderRef]:
        """Return the first provider reachable on this host.

        ``available`` is the set of installed provider names. When it is
        ``None`` we don't know what's installed, so we return the first
        listed provider (the catalog lists them in preference order).
        Returns ``None`` only when ``available`` is given and none match.
        """
        if not self.providers:
            return None
        if available is None:
            return self.providers[0]
        allowed = {a.lower() for a in available}
        for ref in self.providers:
            if ref.provider.lower() in allowed:
                return ref
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "vendor": self.vendor,
            "license": self.license,
            "license_spdx": self.license_spdx,
            "open_weights": self.open_weights,
            "tier": self.tier,
            "current_variant": self.current_variant,
            "context_window": self.context_window,
            "params": self.params,
            "local": self.local,
            "local_runner": self.local_runner,
            "best_for": list(self.best_for),
            "benchmarks": self.benchmarks_dict,
            "providers": [p.to_dict() for p in self.providers],
            "why": self.why,
            "sources": list(self.sources),
        }


# ---------------------------------------------------------------------------
# Catalog container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OssCatalog:
    families: tuple[OssModel, ...]
    routing: tuple[tuple[str, tuple[str, ...]], ...] = ()
    source: str = "builtin"  # "yaml" | "builtin"
    version: int = 1
    updated_at: str = ""
    sources: tuple[str, ...] = ()
    path: Optional[str] = None

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for f in self.families:
            if f.id in seen:
                raise ValueError(f"duplicate model id in catalog: {f.id!r}")
            seen.add(f.id)

    # -- lookups ----------------------------------------------------------
    @property
    def routing_dict(self) -> dict[str, tuple[str, ...]]:
        return dict(self.routing)

    def ids(self) -> list[str]:
        return [f.id for f in self.families]

    def tasks(self) -> list[str]:
        return sorted(self.routing_dict.keys())

    def by_id(self, model_id: str) -> Optional[OssModel]:
        for f in self.families:
            if f.id == model_id:
                return f
        return None

    # -- recommendation ---------------------------------------------------
    def recommend(
        self,
        task: str,
        *,
        local_only: bool = False,
        license_allow: Optional[Iterable[str]] = None,
        available_providers: Optional[Iterable[str]] = None,
    ) -> list[OssModel]:
        """Return models for ``task``, best first.

        Resolution:
          1. If ``routing`` names the task, follow that ordered list.
          2. Otherwise fall back to families whose ``best_for`` contains
             the task (or its non-``local_`` base), sorted by tier then
             top benchmark.

        Filters (all optional, applied after ordering):
          * ``local_only``        — keep only families with a local variant.
          * ``license_allow``     — keep only families whose normalized
                                    license is in the set (e.g. {"MIT"}).
          * ``available_providers`` — keep only families reachable via an
                                    installed provider.
        """
        task = (task or "").strip().lower()
        ordered = self._ordered_for_task(task)

        allow_tokens = (
            {t.strip().lower() for t in license_allow}
            if license_allow is not None
            else None
        )
        avail = (
            {a.lower() for a in available_providers}
            if available_providers is not None
            else None
        )

        out: list[OssModel] = []
        seen: set[str] = set()
        for model in ordered:
            if model.id in seen:
                continue
            if local_only and not model.local:
                continue
            if (
                allow_tokens is not None
                and model.license_spdx.lower() not in allow_tokens
            ):
                continue
            if avail is not None and model.resolve_provider(avail) is None:
                continue
            out.append(model)
            seen.add(model.id)
        return out

    def best(self, task: str, **kwargs: Any) -> Optional[OssModel]:
        hits = self.recommend(task, **kwargs)
        return hits[0] if hits else None

    def _ordered_for_task(self, task: str) -> list[OssModel]:
        routing = self.routing_dict
        if task in routing:
            resolved = [self.by_id(i) for i in routing[task]]
            return [m for m in resolved if m is not None]

        # Fallback: match best_for, including the base of a local_* task.
        base = task[len("local_") :] if task.startswith("local_") else task
        want_local = task.startswith("local_")
        cands = [f for f in self.families if task in f.best_for or base in f.best_for]
        if want_local:
            local_cands = [f for f in cands if f.local]
            if local_cands:
                cands = local_cands
        cands.sort(
            key=lambda f: (_TIER_RANK.get(f.tier, 0), f.top_benchmark),
            reverse=True,
        )
        return cands

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "source": self.source,
            "sources": list(self.sources),
            "families": [f.to_dict() for f in self.families],
            "routing": {k: list(v) for k, v in self.routing},
        }


# ---------------------------------------------------------------------------
# YAML loader (best-effort; falls back to built-in)
# ---------------------------------------------------------------------------


def _provider_refs(raw: Any) -> tuple[ProviderRef, ...]:
    refs: list[ProviderRef] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            provider = str(item.get("provider") or "").strip()
            model = str(item.get("model") or "").strip()
            if provider and model:
                refs.append(ProviderRef(provider=provider, model=model))
    return tuple(refs)


def _benchmarks(raw: Any) -> tuple[tuple[str, float], ...]:
    out: list[tuple[str, float]] = []
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                out.append((str(k), float(v)))
            except (TypeError, ValueError):
                continue
    return tuple(out)


def _model_from_yaml(raw: dict[str, Any]) -> OssModel:
    return OssModel(
        id=str(raw.get("id") or "").strip(),
        vendor=str(raw.get("vendor") or ""),
        license=str(raw.get("license") or ""),
        license_spdx=str(raw.get("license_spdx") or raw.get("license") or ""),
        open_weights=bool(raw.get("open_weights", True)),
        tier=str(raw.get("tier") or "strong"),
        current_variant=str(raw.get("current_variant") or ""),
        context_window=int(raw.get("context_window") or 0),
        params=str(raw.get("params") or ""),
        local=bool(raw.get("local", False)),
        local_runner=str(raw.get("local_runner") or ""),
        best_for=tuple(str(s) for s in (raw.get("best_for") or [])),
        benchmarks=_benchmarks(raw.get("benchmarks")),
        providers=_provider_refs(raw.get("providers")),
        why=str(raw.get("why") or ""),
        sources=tuple(str(s) for s in (raw.get("sources") or [])),
    )


def _routing_from_yaml(raw: Any) -> tuple[tuple[str, tuple[str, ...]], ...]:
    out: list[tuple[str, tuple[str, ...]]] = []
    if isinstance(raw, dict):
        for task, ids in raw.items():
            if isinstance(ids, (list, tuple)):
                out.append((str(task), tuple(str(i) for i in ids)))
    return tuple(out)


def _load_yaml_catalog(path: Path) -> Optional[OssCatalog]:
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
    if not isinstance(data, dict):
        return None
    families_raw = data.get("families")
    if not isinstance(families_raw, list):
        return None
    families: list[OssModel] = []
    seen: set[str] = set()
    for entry in families_raw:
        if not isinstance(entry, dict):
            continue
        model = _model_from_yaml(entry)
        if not model.id or model.id in seen:
            continue
        families.append(model)
        seen.add(model.id)
    if not families:
        return None
    return OssCatalog(
        families=tuple(families),
        routing=_routing_from_yaml(data.get("routing")),
        source="yaml",
        version=int(data.get("version") or 1),
        updated_at=str(data.get("updated_at") or ""),
        sources=tuple(str(s) for s in (data.get("sources") or [])),
        path=str(path),
    )


# ---------------------------------------------------------------------------
# Built-in fallback catalog (narrow — keeps the brain + tests working
# without the YAML or PyYAML installed). Mirrors the YAML's routing.
# ---------------------------------------------------------------------------

_BUILTIN_FAMILIES: tuple[OssModel, ...] = (
    OssModel(
        id="deepseek-v4",
        vendor="DeepSeek",
        license="MIT",
        license_spdx="MIT",
        tier="frontier",
        current_variant="deepseek-v4",
        context_window=1000000,
        params="~1.6T total / ~49B active (MoE)",
        local=False,
        best_for=("coding", "agentic_coding", "bug_fix", "reasoning"),
        benchmarks=(("swe_bench_verified", 80.6), ("livecodebench", 93.5)),
        providers=(
            ProviderRef("deepseek", "deepseek-chat"),
            ProviderRef("openrouter", "deepseek/deepseek-v4"),
            ProviderRef("novita", "deepseek/deepseek-v4"),
        ),
        why="Top open-weight SWE-bench Verified; frontier agentic coding.",
    ),
    OssModel(
        id="glm-5",
        vendor="Z.ai (Zhipu)",
        license="MIT",
        license_spdx="MIT",
        tier="frontier",
        current_variant="glm-5",
        context_window=200000,
        params="~744B total / ~40B active (MoE)",
        local=False,
        best_for=("agentic_coding", "bug_fix", "coding", "reasoning"),
        benchmarks=(("swe_bench_verified", 77.8), ("livecodebench", 84.9)),
        providers=(
            ProviderRef("zai", "glm-5"),
            ProviderRef("openrouter", "z-ai/glm-5"),
        ),
        why="Best open model for fixing real bugs + agentic/terminal work.",
    ),
    OssModel(
        id="kimi-k2",
        vendor="Moonshot AI",
        license="Modified MIT",
        license_spdx="MIT",
        tier="frontier",
        current_variant="kimi-k2",
        context_window=256000,
        params="~1T total / ~32B active (MoE)",
        local=False,
        best_for=("coding", "agentic_coding", "code_edit", "reasoning"),
        benchmarks=(
            ("humaneval", 99.0),
            ("livecodebench", 89.6),
            ("swe_bench_verified", 76.8),
        ),
        providers=(
            ProviderRef("kimi-coding", "kimi-k2"),
            ProviderRef("openrouter", "moonshotai/kimi-k2"),
        ),
        why="Elite raw code generation; strong thinking variant.",
    ),
    OssModel(
        id="minimax-m2",
        vendor="MiniMax",
        license="Apache-2.0",
        license_spdx="Apache-2.0",
        tier="strong",
        current_variant="minimax-m2",
        context_window=1000000,
        params="~230B total / ~10B active (MoE)",
        local=False,
        best_for=("agentic_coding", "coding"),
        benchmarks=(("swe_bench_verified", 80.2),),
        providers=(
            ProviderRef("minimax", "minimax-m2"),
            ProviderRef("openrouter", "minimax/minimax-m2"),
        ),
        why="Frontier-matching SWE-bench at small active params.",
    ),
    OssModel(
        id="qwen3-coder",
        vendor="Alibaba",
        license="Apache-2.0",
        license_spdx="Apache-2.0",
        tier="strong",
        current_variant="qwen3-coder",
        context_window=256000,
        params="MoE ~80B / ~3B active",
        local=True,
        local_runner="vllm",
        best_for=("coding", "code_edit", "agentic_coding", "local_coding"),
        benchmarks=(("swe_bench_verified", 71.3),),
        providers=(
            ProviderRef("qwen-oauth", "qwen3-coder"),
            ProviderRef("openrouter", "qwen/qwen3-coder"),
            ProviderRef("ollama-cloud", "qwen3-coder"),
        ),
        why="Best permissive (Apache-2.0) coder; runs on a workstation.",
    ),
    OssModel(
        id="qwen3-27b",
        vendor="Alibaba",
        license="Apache-2.0",
        license_spdx="Apache-2.0",
        tier="local",
        current_variant="qwen3.6-27b",
        context_window=262000,
        params="27B dense",
        local=True,
        local_runner="ollama",
        best_for=("local_coding", "coding", "code_edit", "local_reasoning"),
        benchmarks=(("swe_bench_verified", 77.2),),
        providers=(
            ProviderRef("ollama-cloud", "qwen3:27b"),
            ProviderRef("openrouter", "qwen/qwen3-27b"),
        ),
        why="Dense 27B you can run locally that still posts 77% SWE-bench.",
    ),
    OssModel(
        id="devstral-small",
        vendor="Mistral",
        license="Apache-2.0",
        license_spdx="Apache-2.0",
        tier="local",
        current_variant="devstral-small-2",
        context_window=128000,
        params="24B dense",
        local=True,
        local_runner="ollama",
        best_for=("local_coding", "code_edit", "bug_fix"),
        benchmarks=(("swe_bench_verified", 68.0),),
        providers=(
            ProviderRef("ollama-cloud", "devstral-small"),
            ProviderRef("huggingface", "mistralai/Devstral-Small-2"),
        ),
        why="Purpose-built local coding agent; fits a single 24GB GPU.",
    ),
    OssModel(
        id="deepseek-r1",
        vendor="DeepSeek",
        license="MIT",
        license_spdx="MIT",
        tier="frontier",
        current_variant="deepseek-r1",
        context_window=128000,
        params="~671B total / ~37B active (MoE)",
        local=False,
        best_for=("reasoning", "math"),
        benchmarks=(("math_500", 97.3),),
        providers=(
            ProviderRef("deepseek", "deepseek-reasoner"),
            ProviderRef("openrouter", "deepseek/deepseek-r1"),
        ),
        why="Near-perfect MATH-500; the reference open reasoning model.",
    ),
    OssModel(
        id="deepseek-r1-distill-8b",
        vendor="DeepSeek",
        license="MIT",
        license_spdx="MIT",
        tier="local",
        current_variant="deepseek-r1-distill-qwen3-8b",
        context_window=128000,
        params="8B dense (distilled)",
        local=True,
        local_runner="ollama",
        best_for=("local_reasoning", "reasoning", "math"),
        benchmarks=(("aime_2025", 87.5),),
        providers=(
            ProviderRef("ollama-cloud", "deepseek-r1:8b"),
            ProviderRef("huggingface", "deepseek-ai/DeepSeek-R1-Distill-Qwen3-8B"),
        ),
        why="8B that matches far larger models on AIME — best local reasoner.",
    ),
    OssModel(
        id="qwen3-235b",
        vendor="Alibaba",
        license="Apache-2.0",
        license_spdx="Apache-2.0",
        tier="frontier",
        current_variant="qwen3-235b-a22b",
        context_window=262000,
        params="235B total / ~22B active (MoE)",
        local=False,
        best_for=("reasoning", "math", "coding"),
        benchmarks=(("aime_2025", 89.2), ("humaneval", 91.5)),
        providers=(
            ProviderRef("qwen-oauth", "qwen3-235b-a22b"),
            ProviderRef("openrouter", "qwen/qwen3-235b-a22b"),
        ),
        why="Top open reasoning+math under permissive Apache-2.0.",
    ),
    OssModel(
        id="gpt-oss-120b",
        vendor="OpenAI (open weights)",
        license="Apache-2.0",
        license_spdx="Apache-2.0",
        tier="strong",
        current_variant="gpt-oss-120b",
        context_window=131000,
        params="117B total / 5.1B active (MoE)",
        local=False,
        best_for=("reasoning", "agentic_coding"),
        providers=(
            ProviderRef("openrouter", "openai/gpt-oss-120b"),
            ProviderRef("ollama-cloud", "gpt-oss:120b"),
        ),
        why="Near o4-mini reasoning, Apache-2.0; pairs with the 20B local sibling.",
    ),
    OssModel(
        id="gpt-oss-20b",
        vendor="OpenAI (open weights)",
        license="Apache-2.0",
        license_spdx="Apache-2.0",
        tier="local",
        current_variant="gpt-oss-20b",
        context_window=131000,
        params="21B total / 3.6B active (MoE) — 16GB RAM",
        local=True,
        local_runner="ollama",
        best_for=("local_reasoning", "local_coding", "reasoning"),
        providers=(
            ProviderRef("ollama-cloud", "gpt-oss:20b"),
            ProviderRef("huggingface", "openai/gpt-oss-20b"),
        ),
        why="Capable reasoning on a 16GB laptop — the everyday local default.",
    ),
)

_BUILTIN_ROUTING: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("coding", ("deepseek-v4", "glm-5", "kimi-k2", "minimax-m2", "qwen3-coder")),
    (
        "agentic_coding",
        ("glm-5", "deepseek-v4", "kimi-k2", "minimax-m2", "qwen3-coder"),
    ),
    ("bug_fix", ("glm-5", "deepseek-v4", "kimi-k2", "qwen3-coder", "devstral-small")),
    ("code_edit", ("qwen3-coder", "kimi-k2", "glm-5", "devstral-small", "deepseek-v4")),
    (
        "reasoning",
        ("deepseek-r1", "qwen3-235b", "glm-5", "gpt-oss-120b", "deepseek-v4"),
    ),
    ("math", ("deepseek-r1", "qwen3-235b", "deepseek-r1-distill-8b")),
    ("local_coding", ("qwen3-coder", "qwen3-27b", "devstral-small", "gpt-oss-20b")),
    ("local_reasoning", ("deepseek-r1-distill-8b", "gpt-oss-20b", "qwen3-27b")),
)

_BUILTIN_CATALOG = OssCatalog(
    families=_BUILTIN_FAMILIES,
    routing=_BUILTIN_ROUTING,
    source="builtin",
    version=1,
    updated_at="2026-05-28",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_cache: dict[str, OssCatalog] = {}


def load_oss_catalog(path: str | Path | None = None) -> OssCatalog:
    """Load the OSS model catalog, cached per resolved path for the process.

    Falls back to the built-in catalog if the YAML is missing/unreadable
    or PyYAML is unavailable. Never raises — the brain must stay usable.
    """
    resolved = Path(path) if path is not None else DEFAULT_CATALOG_PATH
    key = str(resolved.resolve()) if resolved.exists() else f"missing:{resolved}"
    if key in _cache:
        return _cache[key]
    cat = _load_yaml_catalog(resolved) if resolved.exists() else None
    if cat is None:
        cat = _BUILTIN_CATALOG
    _cache[key] = cat
    return cat


def builtin_catalog() -> OssCatalog:
    """Return the built-in catalog directly (tests / diagnostics)."""
    return _BUILTIN_CATALOG


def reset_cache() -> None:
    """Clear the in-process catalog cache."""
    _cache.clear()


def installed_provider_names() -> Optional[set[str]]:
    """Return the set of provider plugin names installed on this host.

    Used to filter recommendations to models that are actually reachable.
    Returns ``None`` (meaning "unknown — don't filter") if the provider
    registry can't be imported (e.g. a stripped-down install).
    """
    try:
        from providers import list_providers  # lazy: avoids import cost + cycles
    except Exception:
        return None
    try:
        names: set[str] = set()
        for profile in list_providers():
            names.add(profile.name)
            for alias in getattr(profile, "aliases", ()) or ():
                names.add(alias)
        return names or None
    except Exception:
        return None
