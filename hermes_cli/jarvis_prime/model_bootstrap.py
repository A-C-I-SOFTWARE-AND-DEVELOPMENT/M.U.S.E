"""Free-first model bootstrap for JARVIS Prime.

Implements ``hermes models bootstrap --free-first --jarvis``: a real
bootstrap, not just a recommendation. It

1. **Detects** what is actually runnable on this host —
   local runtimes (ollama, llama.cpp, vllm, lmstudio), hosted open-route
   providers (only when a key/config is *already* present), and the
   official worker CLIs (Claude Code, Codex) — all via ``shutil.which``
   and read-only env inspection. It never installs or authenticates a
   paid service and never asks for or stores API keys.
2. **Plans** a free-first route order:
   ``local_oss`` → ``hosted_free_or_user_configured_oss`` →
   ``claude_code_worker`` → ``codex_worker`` → ``paid_api_explicit_only``.
   Paid APIs are disabled unless the owner explicitly opted in.
3. **Writes** (unless ``--dry-run``) a JARVIS model routing config to
   ``${HERMES_HOME:-~/.hermes}/jarvis_prime/model_policy.json``.
4. Optionally **pulls** small, safe default local models via Ollama
   (skippable with ``--no-pull``). Model *choices* come from the OSS
   model brain catalog — the single source of truth.

Stdlib-only at import time. ``subprocess`` is only touched behind thin,
injectable wrappers so tests never shell out, pull a model, or hit the
network.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


CONFIG_VERSION = 1

# Free-first route order. Lower index = preferred. Paid is always last and
# disabled unless the owner explicitly opted in.
ROUTE_ORDER: tuple[str, ...] = (
    "local_oss",
    "hosted_free_or_user_configured_oss",
    "claude_code_worker",
    "codex_worker",
    "paid_api_explicit_only",
)

# Local runtimes we know how to detect. value = candidate CLI binaries.
_LOCAL_RUNTIME_BINARIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ollama", ("ollama",)),
    ("llama.cpp", ("llama-server", "llama-cli", "llama")),
    ("vllm", ("vllm",)),
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
    """Detect installed local model runtimes. ``which`` is injectable."""
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
# Local model defaults (from the OSS model brain catalog)
# ---------------------------------------------------------------------------


@dataclass
class LocalDefault:
    purpose: str  # "local_reasoning" | "local_coding" | "embeddings"
    model_id: str  # catalog family id, or a runtime-native tag for embeddings
    ollama_tag: Optional[str]  # concrete ollama model tag, if resolvable
    small: bool  # safe to pull by default on common hardware
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ollama_tag_for(model: Any) -> Optional[str]:
    """Return the ollama model tag for a catalog family, if it has one."""
    for ref in getattr(model, "providers", ()):
        if "ollama" in ref.provider.lower():
            return ref.model
    return None


# Models that fit comfortably on common hardware (≈8GB-16GB). Used to decide
# what is safe to pull by default. Tags are matched against the catalog's
# resolved ollama tags; anything not in this set is "suggested, not auto-pulled".
_SMALL_OLLAMA_TAGS: frozenset[str] = frozenset({"deepseek-r1:8b", "gpt-oss:20b"})
_EMBEDDING_TAG = (
    "nomic-embed-text"  # tiny, ubiquitous; not in the catalog (no embeddings tier)
)


def compute_local_defaults() -> list[LocalDefault]:
    """Pick sane local defaults for reasoning, coding, and embeddings.

    Reasoning/coding choices come from the catalog (source of truth);
    embeddings has no catalog tier so we use the standard small model.
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
                    small=bool(tag and tag in _SMALL_OLLAMA_TAGS),
                    why=model.why,
                )
            )

    defaults.append(
        LocalDefault(
            purpose="embeddings",
            model_id=_EMBEDDING_TAG,
            ollama_tag=_EMBEDDING_TAG,
            small=True,
            why="Standard small local embedding model for JARVIS memory.",
        )
    )
    return defaults


# ---------------------------------------------------------------------------
# Pull plan + execution (Ollama only, behind an injectable runner)
# ---------------------------------------------------------------------------


@dataclass
class PullTarget:
    model: str
    purpose: str
    will_pull: bool
    pulled: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_pulls(
    defaults: list[LocalDefault],
    *,
    no_pull: bool,
    force: bool,
    ollama_available: bool,
) -> list[PullTarget]:
    """Decide which default models to pull. Conservative by default."""
    targets: list[PullTarget] = []
    seen: set[str] = set()
    for d in defaults:
        if not d.ollama_tag or d.ollama_tag in seen:
            continue
        seen.add(d.ollama_tag)
        if not ollama_available:
            targets.append(
                PullTarget(
                    d.ollama_tag, d.purpose, False, reason="ollama not installed"
                )
            )
        elif no_pull:
            targets.append(
                PullTarget(d.ollama_tag, d.purpose, False, reason="--no-pull")
            )
        elif force or d.small:
            targets.append(
                PullTarget(
                    d.ollama_tag,
                    d.purpose,
                    True,
                    reason="safe default" if d.small else "--force",
                )
            )
        else:
            targets.append(
                PullTarget(
                    d.ollama_tag,
                    d.purpose,
                    False,
                    reason="large model — pull manually or use --force",
                )
            )
    return targets


def _default_pull_runner(model: str) -> tuple[bool, str]:
    """Run ``ollama pull <model>``. Returns (ok, detail). Never raises."""
    try:
        proc = subprocess.run(
            ["ollama", "pull", model],
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
        if proc.returncode == 0:
            return True, "pulled"
        return False, (proc.stderr or proc.stdout or "non-zero exit").strip()[:200]
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - defensive
        return False, f"pull failed: {exc}"


def execute_pulls(
    targets: list[PullTarget],
    *,
    dry_run: bool,
    runner: Optional[Callable[[str], tuple[bool, str]]] = None,
) -> list[PullTarget]:
    """Execute the planned pulls. In dry-run mode nothing is pulled."""
    runner = runner or _default_pull_runner
    for t in targets:
        if not t.will_pull or dry_run:
            continue
        ok, detail = runner(t.model)
        t.pulled = ok
        t.reason = detail if not ok else "pulled"
    return targets


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
) -> dict[str, dict[str, Any]]:
    """Build the free-first route map. Free routes precede paid ones."""
    any_local = any(v.get("available") for v in local_runtimes.values())
    any_hosted = any(v.get("configured") for v in hosted_oss.values())
    claude_ok = workers.get("claude_code_builder", {}).get("available", False)
    codex_ok = workers.get("codex_reviewer", {}).get("available", False)

    return {
        "local_oss": {
            "rank": 1,
            "enabled": any_local,
            "runtimes": [k for k, v in local_runtimes.items() if v.get("available")],
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
    pulls: list[PullTarget] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["pulls"] = [
            p.to_dict() if isinstance(p, PullTarget) else p for p in self.pulls
        ]
        return d

    def render(self) -> str:
        lines = ["JARVIS Prime — free-first model bootstrap"]
        cfg = self.config
        lines.append(
            f"  mode: {'dry-run' if self.dry_run else 'apply'}"
            f"{' · local-only' if self.local_only else ''}"
        )
        routes = cfg.get("routes", {})
        lines.append("  route order (free-first):")
        for name in ROUTE_ORDER:
            r = routes.get(name, {})
            mark = "✓" if r.get("enabled") else "·"
            extra = ""
            if name == "local_oss" and r.get("runtimes"):
                extra = f"  [{', '.join(r['runtimes'])}]"
            elif name == "hosted_free_or_user_configured_oss" and r.get("providers"):
                extra = f"  [{', '.join(r['providers'])}]"
            elif name == "paid_api_explicit_only":
                extra = "  (explicit opt-in only)"
            lines.append(f"    {mark} {name}{extra}")
        if cfg.get("local_defaults"):
            lines.append("  local defaults:")
            for d in cfg["local_defaults"]:
                tag = d.get("ollama_tag") or d.get("model_id")
                lines.append(f"    - {d['purpose']}: {d['model_id']} ({tag})")
        if self.pulls:
            lines.append("  model pulls:")
            for p in self.pulls:
                state = (
                    "pulled"
                    if p.pulled
                    else ("would pull" if p.will_pull and self.dry_run else "skipped")
                )
                lines.append(f"    - {p.model} [{p.purpose}]: {state} — {p.reason}")
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
    pull_runner: Optional[Callable[[str], tuple[bool, str]]] = None,
    record_memory: bool = True,
) -> BootstrapResult:
    """Run the bootstrap. Pure detection + a single config write (unless dry-run).

    Returns a :class:`BootstrapResult`. Missing optional providers are
    warnings, not errors — ``ok`` is False only on a real failure
    (e.g. the config could not be written when it was supposed to be).
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

    routes = build_route_plan(
        local_runtimes=local_runtimes,
        hosted_oss=hosted_oss,
        workers=workers,
        paid_providers=paid_providers,
        paid_enabled=paid_enabled,
        local_only=local_only,
    )

    ollama_available = local_runtimes.get("ollama", {}).get("available", False)
    pulls = plan_pulls(
        defaults, no_pull=no_pull, force=force, ollama_available=ollama_available
    )
    pulls = execute_pulls(pulls, dry_run=dry_run, runner=pull_runner)

    warnings: list[str] = []
    if not any(v.get("available") for v in local_runtimes.values()):
        warnings.append(
            "No local model runtime detected (ollama/llama.cpp/vllm/lmstudio). "
            "JARVIS will fall back to configured hosted/worker routes. Install "
            "Ollama (https://ollama.com) for a fully local, free-first setup."
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
        "local_runtimes": local_runtimes,
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
        pulls=pulls,
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
            "free-first local OSS routing enabled; Claude Code/Codex are "
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
    "PullTarget",
    "bootstrap",
    "build_route_plan",
    "compute_local_defaults",
    "config_path",
    "detect_hosted_oss",
    "detect_local_runtimes",
    "detect_paid_providers",
    "detect_workers",
    "execute_pulls",
    "load_policy",
    "paid_opt_in",
    "plan_pulls",
]
