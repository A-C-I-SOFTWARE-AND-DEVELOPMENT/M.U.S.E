"""Free-first model bootstrap for JARVIS Prime — one unified system.

Implements ``hermes models bootstrap --free-first --jarvis``. It ties two
layers into a single model policy so local model download/detection and
free-first provider routing feel like one system, not two adjacent pieces:

* **Provider routing (this module).** A free-first route order:
  ``local_oss`` → ``hosted_free_or_user_configured_oss`` →
  ``claude_code_worker`` → ``codex_worker`` → ``paid_api_explicit_only``.
  Paid APIs are disabled unless the owner explicitly opts in. Hosted
  providers are detected read-only (env presence only — never stored).
* **Local model layer (``hermes_cli.local_models``).** Hardware probe,
  open-weight candidate catalog, server adapters (Ollama / llama.cpp /
  vLLM / SGLang / OpenAI-compat), and a hardware-aware, **consent-gated**
  download plan. The router drives it and folds its plan into the policy,
  so ``local_oss`` lists the concrete local models that fit this box.

The result is written (unless ``--dry-run``) to
``${HERMES_HOME:-~/.hermes}/jarvis_prime/model_policy.json``.

Stdlib-only at import time. The local layer + ``subprocess`` are reached
only behind thin, injectable wrappers so tests never shell out, download
a model, probe real hardware, or hit the network.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence


CONFIG_VERSION = 2

# Free-first route order. Lower index = preferred. Paid is always last and
# disabled unless the owner explicitly opted in.
ROUTE_ORDER: tuple[str, ...] = (
    "local_oss",
    "hosted_free_or_user_configured_oss",
    "claude_code_worker",
    "codex_worker",
    "paid_api_explicit_only",
)

# Local runtimes we detect via ``which``. Mirrors the runtimes the local
# model layer (``local_models.server_adapters``) knows how to launch, plus
# LM Studio. ``openai-compat`` is a base-URL, not a CLI, so it isn't probed
# here. ``which`` is injectable so this stays hermetic in tests.
_LOCAL_RUNTIME_BINARIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ollama", ("ollama",)),
    ("llama.cpp", ("llama-server", "llama-cli", "llama")),
    ("vllm", ("vllm",)),
    ("sglang", ("sglang", "sglang.launch_server")),
    ("lmstudio", ("lms", "lmstudio")),
)

# Hosted OPEN-route providers and the env var(s) that indicate the owner
# already configured them. Detection is read-only — we never write these.
_HOSTED_OSS_ENV: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("openrouter", ("OPENROUTER_API_KEY",)),
    ("huggingface", ("HF_TOKEN", "HUGGINGFACE_API_KEY", "HUGGINGFACEHUB_API_TOKEN")),
    ("nous", ("NOUS_API_KEY", "NOUS_PORTAL_API_KEY")),
    ("novita", ("NOVITA_API_KEY",)),
    ("nim", ("NIM_API_KEY", "NVIDIA_API_KEY")),
    ("together", ("TOGETHER_API_KEY",)),
    ("fireworks", ("FIREWORKS_API_KEY",)),
)

# Paid, closed providers. Detected for transparency only; NEVER auto-enabled.
_PAID_ENV: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("anthropic", ("ANTHROPIC_API_KEY",)),
    ("openai", ("OPENAI_API_KEY",)),
    ("google", ("GEMINI_API_KEY", "GOOGLE_API_KEY")),
    ("xai", ("XAI_API_KEY",)),
)

# Env var the owner sets to *explicitly* opt into paid API routes. Presence
# of a paid key alone does NOT enable paid routing — this flag must be set.
PAID_OPT_IN_ENV = "HERMES_JARVIS_ENABLE_PAID"


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def detect_local_runtimes(
    which: Callable[[str], Optional[str]] = shutil.which,
) -> dict[str, dict[str, Any]]:
    """Detect installed local model runtimes. ``which`` is injectable.

    The runtime set is unified with ``local_models.server_adapters`` so a
    runtime detected here can also be launched by the local model layer.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, binaries in _LOCAL_RUNTIME_BINARIES:
        path = None
        matched = None
        for binary in binaries:
            path = which(binary)
            if path:
                matched = binary
                break
        out[name] = {
            "available": path is not None,
            "binary": matched,
            "path": path,
        }
    return out


def detect_hosted_oss(
    env: Optional[dict[str, str]] = None,
) -> dict[str, dict[str, Any]]:
    """Detect hosted OPEN-route providers the owner already configured.

    Read-only: presence of an env var is the only signal. We never read
    the value, never echo it, and never write it anywhere.
    """
    env = env if env is not None else dict(os.environ)
    out: dict[str, dict[str, Any]] = {}
    for name, keys in _HOSTED_OSS_ENV:
        present = any(bool(env.get(k, "").strip()) for k in keys)
        out[name] = {"configured": present}
    return out


def detect_paid_providers(
    env: Optional[dict[str, str]] = None,
) -> dict[str, dict[str, Any]]:
    """Detect paid providers (transparency only — never auto-enabled)."""
    env = env if env is not None else dict(os.environ)
    out: dict[str, dict[str, Any]] = {}
    for name, keys in _PAID_ENV:
        present = any(bool(env.get(k, "").strip()) for k in keys)
        out[name] = {"configured": present}
    return out


def paid_opt_in(env: Optional[dict[str, str]] = None) -> bool:
    """True only if the owner explicitly opted into paid API routes."""
    env = env if env is not None else dict(os.environ)
    val = env.get(PAID_OPT_IN_ENV, "").strip().lower()
    return val in ("1", "true", "yes", "on")


def detect_workers() -> dict[str, dict[str, Any]]:
    """Detect official worker-lane CLIs (Claude Code, Codex). No credentials."""
    from hermes_cli.jarvis_prime import worker_registry as wr

    statuses = wr.detect_lanes()
    out: dict[str, dict[str, Any]] = {}
    for status in statuses:
        out[status.lane.id] = {
            "tool": status.lane.tool,
            "available": status.available,
            "version": status.version,
            "role": status.lane.role,
        }
    return out


# ---------------------------------------------------------------------------
# Local model route preferences (from the OSS model brain catalog)
# ---------------------------------------------------------------------------


@dataclass
class LocalDefault:
    purpose: str  # "local_reasoning" | "local_coding" | "embeddings"
    model_id: str  # catalog family id, or a runtime-native tag for embeddings
    ollama_tag: Optional[str]  # concrete ollama model tag, if resolvable
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ollama_tag_for(model: Any) -> Optional[str]:
    """Return the ollama model tag for a catalog family, if it has one."""
    for ref in getattr(model, "providers", ()):
        if "ollama" in ref.provider.lower():
            return ref.model
    return None


_EMBEDDING_TAG = "nomic-embed-text"  # tiny, ubiquitous; no catalog tier for embeddings


def compute_local_defaults() -> list[LocalDefault]:
    """Preferred local model *families* for reasoning/coding/embeddings.

    These are the route-layer preferences (from the OSS model brain — the
    cross-referenced catalog). The concrete, hardware-fit *download* plan
    comes from the local model layer (see :func:`build_local_plan`); the
    two are folded together in the written policy.
    """
    from hermes_cli import oss_model_brain as ob

    catalog = ob.load_oss_catalog()
    defaults: list[LocalDefault] = []

    for purpose in ("local_reasoning", "local_coding"):
        best = None
        for model in catalog.recommend(purpose, local_only=True):
            tag = _ollama_tag_for(model)
            if tag:
                best = (model, tag)
                break
            if best is None:
                best = (model, None)
        if best is not None:
            model, tag = best
            defaults.append(
                LocalDefault(
                    purpose=purpose,
                    model_id=model.id,
                    ollama_tag=tag,
                    why=model.why,
                )
            )

    defaults.append(
        LocalDefault(
            purpose="embeddings",
            model_id=_EMBEDDING_TAG,
            ollama_tag=_EMBEDDING_TAG,
            why="Standard small local embedding model for JARVIS memory.",
        )
    )
    return defaults


# Per-tier preferred Gemma 4 variants for the doctor / status surfaces. This is
# advisory only — it recommends, it never downloads. The hardware-aware,
# consent-gated plan (``build_local_plan``) remains the authority on what
# actually fits this box.
_GEMMA_TIER_PREFERENCE: dict[str, tuple[str, ...]] = {
    "laptop": ("gemma4-e2b", "gemma4-e4b"),
    "desktop": ("gemma4-e4b", "gemma4-e2b"),
    "workstation": ("gemma4-26b-a4b", "gemma4-e4b"),
    "server": ("gemma4-31b", "gemma4-26b-a4b"),
}


def gemma_recommendations(tier: str, *, catalog: Any = None) -> list[dict[str, Any]]:
    """Recommended Gemma 4 variants for a hardware ``tier`` (advisory).

    Returns ``[{name, source, ollama_tag, kind, routing_lanes, tiers}, …]`` for
    the Gemma open-weight candidates that both fit ``tier`` and are listed in
    the per-tier preference. Pure and defensive: any failure (missing catalog /
    PyYAML on a stripped install) degrades to ``[]``. Recommends only — never
    downloads, never probes hardware, never hits the network.
    """
    try:
        if catalog is None:
            from hermes_cli.local_models.catalog import load_open_weight_catalog

            catalog = load_open_weight_catalog()
        for_tier = {m.name for m in catalog.for_tier(tier)}
    except Exception:  # pragma: no cover - defensive (stripped install)
        return []

    preferred = _GEMMA_TIER_PREFERENCE.get(tier, ())
    out: list[dict[str, Any]] = []
    for name in preferred:
        model = catalog.get(name)
        if model is None or name not in for_tier:
            continue
        tag = None
        if model.source.startswith("ollama:"):
            tag = model.source.split("ollama:", 1)[1]
        out.append(
            {
                "name": model.name,
                "source": model.source,
                "ollama_tag": tag,
                "kind": model.kind,
                "routing_lanes": list(model.routing_lanes),
                "tiers": list(model.tiers),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Local model layer integration (hardware-aware, consent-gated downloads)
# ---------------------------------------------------------------------------


def probe_hardware(hardware: Any = None) -> Any:
    """Probe this host's hardware via the local model layer (injectable).

    Returns a ``local_models.HardwareProfile``. ``hardware`` may be passed
    pre-built (tests). Never raises — degrades to ``None`` if the local
    layer is unavailable (stripped-down install).
    """
    if hardware is not None:
        return hardware
    try:
        from hermes_cli.local_models import probe

        return probe()
    except Exception:  # pragma: no cover - defensive (Termux/slim installs)
        return None


def build_local_plan(
    *,
    hardware: Any,
    accept_downloads: bool,
) -> tuple[Optional[dict[str, Any]], list[str], list[str]]:
    """Build the hardware-aware local model plan via the local model layer.

    Returns ``(plan_dict, recommended_model_names, warnings)``. Defensive:
    any failure (missing catalog/PyYAML, probe error) degrades to
    ``(None, [], [warning])`` so the route policy is still written.
    """
    warnings: list[str] = []
    if hardware is None:
        warnings.append(
            "Local model layer unavailable — hardware plan skipped "
            "(routing policy still written)."
        )
        return None, [], warnings
    try:
        from hermes_cli.local_models import plan_bootstrap

        plan = plan_bootstrap(
            hardware.tier, hardware=hardware, accept_downloads=accept_downloads
        )
        plan_dict = plan.to_dict()
        recommended: list[str] = [item.model.name for item in plan.recommended]
        return plan_dict, recommended, warnings
    except Exception as exc:  # pragma: no cover - defensive
        warnings.append(f"Local model plan unavailable ({exc}); routing policy only.")
        return None, [], warnings


def execute_local_downloads(
    plan_obj: Any,
    *,
    accept_downloads: bool,
    runner: Optional[Callable[[Sequence[str]], tuple[bool, str]]] = None,
) -> list[dict[str, Any]]:
    """Run the consent-gated downloads from a local plan. Never raises."""
    if plan_obj is None:
        return []
    try:
        from hermes_cli.local_models import execute_bootstrap

        outcomes = execute_bootstrap(
            plan_obj, accept_downloads=accept_downloads, runner=runner
        )
        result: list[dict[str, Any]] = []
        for o in outcomes:
            to_dict = getattr(o, "to_dict", None)
            result.append(to_dict() if callable(to_dict) else {"detail": str(o)})
        return result
    except Exception as exc:  # pragma: no cover - defensive
        return [
            {"attempted": False, "ok": False, "detail": f"download step failed: {exc}"}
        ]


# ---------------------------------------------------------------------------
# Route plan + config
# ---------------------------------------------------------------------------


def build_route_plan(
    *,
    local_runtimes: dict[str, dict[str, Any]],
    hosted_oss: dict[str, dict[str, Any]],
    workers: dict[str, dict[str, Any]],
    paid_providers: dict[str, dict[str, Any]],
    paid_enabled: bool,
    local_only: bool,
    recommended_local_models: Optional[list[str]] = None,
) -> dict[str, dict[str, Any]]:
    """Build the free-first route map. Free routes precede paid ones.

    ``recommended_local_models`` (from the local model layer) is folded into
    the ``local_oss`` route so provider routing and the hardware-aware local
    plan read as one system.
    """
    any_local = any(v.get("available") for v in local_runtimes.values())
    any_hosted = any(v.get("configured") for v in hosted_oss.values())
    claude_ok = workers.get("claude_code_builder", {}).get("available", False)
    codex_ok = workers.get("codex_reviewer", {}).get("available", False)

    return {
        "local_oss": {
            "rank": 1,
            "enabled": any_local,
            "runtimes": [k for k, v in local_runtimes.items() if v.get("available")],
            "recommended_local_models": list(recommended_local_models or []),
        },
        "hosted_free_or_user_configured_oss": {
            "rank": 2,
            "enabled": (not local_only) and any_hosted,
            "providers": [k for k, v in hosted_oss.items() if v.get("configured")],
        },
        "claude_code_worker": {
            "rank": 3,
            "enabled": (not local_only) and claude_ok,
            "lane": "claude_code_builder",
            "tool": "claude",
        },
        "codex_worker": {
            "rank": 4,
            "enabled": (not local_only) and codex_ok,
            "lanes": ["codex_reviewer", "codex_bounded_fix"],
            "tool": "codex",
        },
        "paid_api_explicit_only": {
            "rank": 5,
            "enabled": (not local_only) and paid_enabled,
            "explicit_opt_in_required": True,
            "providers_detected": [
                k for k, v in paid_providers.items() if v.get("configured")
            ],
            "note": (
                "Paid APIs stay disabled unless the owner explicitly opts in "
                f"via {PAID_OPT_IN_ENV}=1. Detecting a key does NOT enable it."
            ),
        },
    }


def config_path() -> Path:
    """``${HERMES_HOME:-~/.hermes}/jarvis_prime/model_policy.json``."""
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "jarvis_prime" / "model_policy.json"


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class BootstrapResult:
    ok: bool
    free_first: bool
    jarvis: bool
    dry_run: bool
    local_only: bool
    config_path: str
    config_written: bool
    config: dict[str, Any] = field(default_factory=dict)
    download_outcomes: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def render(self) -> str:
        lines = ["JARVIS Prime — free-first model bootstrap"]
        cfg = self.config
        lines.append(
            f"  mode: {'dry-run' if self.dry_run else 'apply'}"
            f"{' · local-only' if self.local_only else ''}"
        )
        local = cfg.get("local", {})
        hw = local.get("hardware") or {}
        if hw:
            lines.append(
                f"  hardware: tier={hw.get('tier', '?')} "
                f"ram={hw.get('ram_gb', '?')}GB accel={hw.get('accelerator_gb', '?')}GB"
                f"{' gpu=' + str(hw.get('gpu_name')) if hw.get('gpu_name') else ''}"
            )
        routes = cfg.get("routes", {})
        lines.append("  route order (free-first):")
        for name in ROUTE_ORDER:
            r = routes.get(name, {})
            mark = "✓" if r.get("enabled") else "·"
            extra = ""
            if name == "local_oss":
                if r.get("runtimes"):
                    extra = f"  [{', '.join(r['runtimes'])}]"
                if r.get("recommended_local_models"):
                    extra += "  → " + ", ".join(r["recommended_local_models"][:3])
            elif name == "hosted_free_or_user_configured_oss" and r.get("providers"):
                extra = f"  [{', '.join(r['providers'])}]"
            elif name == "paid_api_explicit_only":
                extra = "  (explicit opt-in only)"
            lines.append(f"    {mark} {name}{extra}")
        if cfg.get("local_defaults"):
            lines.append("  local model preferences:")
            for d in cfg["local_defaults"]:
                tag = d.get("ollama_tag") or d.get("model_id")
                lines.append(f"    - {d['purpose']}: {d['model_id']} ({tag})")
        if self.download_outcomes:
            lines.append("  local downloads:")
            for o in self.download_outcomes:
                state = (
                    "downloaded" if o.get("ok") and o.get("attempted") else "skipped"
                )
                lines.append(
                    f"    - {o.get('model', '?')}: {state} — {o.get('detail', '')}"
                )
        for w in self.warnings:
            lines.append(f"  ⚠ {w}")
        for e in self.errors:
            lines.append(f"  ✗ {e}")
        if self.config_written:
            lines.append(f"  config written: {self.config_path}")
        elif self.dry_run:
            lines.append(f"  config NOT written (dry-run): {self.config_path}")
        return "\n".join(lines)


def bootstrap(
    *,
    free_first: bool = True,
    jarvis: bool = True,
    dry_run: bool = False,
    no_pull: bool = False,
    force: bool = False,
    local_only: bool = False,
    which: Callable[[str], Optional[str]] = shutil.which,
    env: Optional[dict[str, str]] = None,
    hardware: Any = None,
    pull_runner: Optional[Callable[[Sequence[str]], tuple[bool, str]]] = None,
    record_memory: bool = True,
) -> BootstrapResult:
    """Run the unified bootstrap: provider routing + local model layer.

    Detection is pure; a single config write happens unless ``--dry-run``.
    Local model downloads are **consent-gated**: they run only with
    ``force`` and not ``no_pull`` and not ``dry_run`` (so an unattended
    ``curl | bash`` never pulls multi-GB weights). Missing optional
    providers/runtimes are warnings — ``ok`` is False only on a real
    failure (e.g. the config could not be written when it should be).
    """
    env = env if env is not None else dict(os.environ)

    local_runtimes = detect_local_runtimes(which)
    hosted_oss = detect_hosted_oss(env)
    paid_providers = detect_paid_providers(env)
    paid_enabled = paid_opt_in(env)
    workers = detect_workers()
    defaults = compute_local_defaults()

    from hermes_cli import oss_model_brain as ob

    catalog = ob.load_oss_catalog()

    # Local model layer: hardware-aware plan + consent-gated downloads.
    accept_downloads = force and (not no_pull) and (not dry_run)
    hw = probe_hardware(hardware)
    plan_dict, recommended_local, local_warnings = build_local_plan(
        hardware=hw, accept_downloads=accept_downloads
    )
    # Re-derive the plan object once for execution (build_local_plan returns
    # a dict for the policy; execution needs the live object).
    download_outcomes: list[dict[str, Any]] = []
    if plan_dict is not None and hw is not None:
        try:
            from hermes_cli.local_models import plan_bootstrap

            plan_obj = plan_bootstrap(
                hw.tier, hardware=hw, accept_downloads=accept_downloads
            )
            download_outcomes = execute_local_downloads(
                plan_obj, accept_downloads=accept_downloads, runner=pull_runner
            )
        except Exception as exc:  # pragma: no cover - defensive
            local_warnings.append(f"Local download step skipped ({exc}).")

    routes = build_route_plan(
        local_runtimes=local_runtimes,
        hosted_oss=hosted_oss,
        workers=workers,
        paid_providers=paid_providers,
        paid_enabled=paid_enabled,
        local_only=local_only,
        recommended_local_models=recommended_local,
    )

    warnings: list[str] = list(local_warnings)
    if not any(v.get("available") for v in local_runtimes.values()):
        warnings.append(
            "No local model runtime detected (ollama/llama.cpp/vllm/sglang/"
            "lmstudio). JARVIS will fall back to configured hosted/worker "
            "routes. Install Ollama (https://ollama.com) for a fully local, "
            "free-first setup."
        )
    if not workers.get("claude_code_builder", {}).get("available"):
        warnings.append("Claude Code CLI not detected — builder worker lane disabled.")
    if not workers.get("codex_reviewer", {}).get("available"):
        warnings.append("Codex CLI not detected — reviewer worker lane disabled.")

    config: dict[str, Any] = {
        "version": CONFIG_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "free_first": free_first,
        "jarvis": jarvis,
        "local_only": local_only,
        "route_order": list(ROUTE_ORDER),
        "routes": routes,
        "local": {
            "runtimes": local_runtimes,
            "hardware": (hw.to_dict() if hw is not None else None),
            "plan": plan_dict,
            "downloads_accepted": accept_downloads,
            "download_outcomes": download_outcomes,
        },
        "hosted_oss": hosted_oss,
        "workers": workers,
        "paid": {
            "enabled": (not local_only) and paid_enabled,
            "opt_in_env": PAID_OPT_IN_ENV,
            "providers_detected": [
                k for k, v in paid_providers.items() if v.get("configured")
            ],
        },
        "local_defaults": [d.to_dict() for d in defaults],
        "catalog": {"source": catalog.source, "updated_at": catalog.updated_at},
    }

    path = config_path()
    errors: list[str] = []
    config_written = False
    if not dry_run:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            config_written = True
        except OSError as exc:
            errors.append(f"could not write model policy config to {path}: {exc}")

    if config_written and record_memory:
        try:
            _record_launch_policy_memory()
        except Exception:  # pragma: no cover - memory is best-effort
            pass

    return BootstrapResult(
        ok=not errors,
        free_first=free_first,
        jarvis=jarvis,
        dry_run=dry_run,
        local_only=local_only,
        config_path=str(path),
        config_written=config_written,
        config=config,
        download_outcomes=download_outcomes,
        warnings=warnings,
        errors=errors,
    )


def _record_launch_policy_memory() -> None:
    """Persist the durable launch-policy memory record (idempotent-ish)."""
    from hermes_cli.jarvis_prime.memory import MemoryStore

    store = MemoryStore()
    # Avoid duplicating the record on every bootstrap run.
    existing = store.recollect("jarvis_launch_model_policy", limit=3)
    if any(r.key == "jarvis_launch_model_policy" for r in existing):
        return
    store.remember(
        key="jarvis_launch_model_policy",
        value=(
            "free-first local OSS routing enabled; local model layer "
            "(hardware-aware, consent-gated) wired in; Claude Code/Codex are "
            "worker lanes; paid APIs explicit opt-in only"
        ),
        durability="durable",
        source="system",
        tags=("bootstrap", "model_policy", "launch"),
    )


def load_policy() -> Optional[dict[str, Any]]:
    """Load the written model policy config, or None if absent/unreadable."""
    path = config_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


__all__ = [
    "PAID_OPT_IN_ENV",
    "ROUTE_ORDER",
    "BootstrapResult",
    "LocalDefault",
    "bootstrap",
    "build_local_plan",
    "build_route_plan",
    "compute_local_defaults",
    "config_path",
    "detect_hosted_oss",
    "detect_local_runtimes",
    "detect_paid_providers",
    "detect_workers",
    "execute_local_downloads",
    "gemma_recommendations",
    "load_policy",
    "paid_opt_in",
    "probe_hardware",
]
