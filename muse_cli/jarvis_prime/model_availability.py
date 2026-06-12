"""Model availability — what can JARVIS/Hermes actually use *right now*.

A practical, offline-safe report over the wired provider layer:

- **per provider**: is its credential present (cloud) or is a local runtime +
  models installed (local) — i.e. is it usable now;
- **recommended-but-missing**: local models the bootstrap policy recommends but
  that are not actually pulled into Ollama;
- **fallback walking**: :func:`walk_fallback_chain` tries a router fallback chain
  in order until a live model answers.

stdlib-only and fully injectable (provider specs / env / `ollama list` are
passed in for tests); the default loaders lazily read the real provider registry
and the on-disk model policy.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

# (name, env_vars, base_url) for one provider.
ProviderSpec = tuple[str, tuple[str, ...], str]


def _is_local(base_url: str) -> bool:
    return any(h in (base_url or "") for h in ("localhost", "127.0.0.1", "0.0.0.0", "::1"))


def _is_credential_var(name: str) -> bool:
    """A real credential env var, not a base-URL / endpoint override."""

    upper = name.upper()
    return not (upper.endswith("URL") or upper.endswith("ENDPOINT"))


def credential_env_vars(env_vars: Iterable[str]) -> tuple[str, ...]:
    """Keep only API-key-style vars (drop ``*_BASE_URL`` / ``*_URL`` / ``*_ENDPOINT``).

    Provider profiles list both the key var and a base-URL override in
    ``env_vars``; only the former proves a provider is usable.
    """

    return tuple(v for v in env_vars if _is_credential_var(v))


def load_hermes_dotenv(home: Optional[Path] = None) -> dict:
    """Parse ``$HERMES_HOME/.env`` (or ``~/.hermes/.env``) — where Hermes stores
    API keys — into a dict. Returns ``{}`` when absent/unreadable. stdlib
    ``KEY=VALUE`` parse (``#`` comments and surrounding quotes handled)."""

    if home:
        base = Path(home)
    else:
        from muse_constants import get_hermes_home

        base = get_hermes_home()
    env_file = base / ".env"
    if not env_file.exists():
        return {}
    try:
        text = env_file.read_text(encoding="utf-8")
    except OSError:
        return {}
    out: dict = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            out[key] = value.strip().strip('"').strip("'")
    return out


def _default_env() -> dict:
    """Process environment merged over the Hermes ``.env`` (process env wins)."""

    return {**load_hermes_dotenv(), **os.environ}


def _default_ollama_list() -> str:
    proc = subprocess.run(
        ["ollama", "list"], capture_output=True, text=True, check=False, timeout=10
    )
    return proc.stdout if proc.returncode == 0 else ""


def installed_ollama_models(list_runner: Optional[Callable[[], str]] = None) -> list[str]:
    """Return every locally installed Ollama model tag (``[]`` if none/Ollama absent)."""

    runner = list_runner or _default_ollama_list
    try:
        output = runner()
    except Exception:
        return []
    models: list[str] = []
    for line in output.splitlines():
        parts = line.split()
        if not parts or parts[0].lower() == "name":
            continue
        models.append(parts[0])
    return models


def load_provider_specs() -> list[ProviderSpec]:
    """Lazily read the real provider registry into (name, env_vars, base_url)."""

    from providers import list_providers

    specs: list[ProviderSpec] = []
    for profile in list_providers():
        specs.append(
            (
                profile.name,
                tuple(getattr(profile, "env_vars", ()) or ()),
                getattr(profile, "base_url", "") or "",
            )
        )
    return specs


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    kind: str  # "cloud" | "local"
    env_vars: tuple[str, ...]
    available_now: bool
    detail: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "env_vars": list(self.env_vars),
            "available_now": self.available_now,
            "detail": self.detail,
        }


def provider_statuses(
    specs: Iterable[ProviderSpec],
    *,
    env: Optional[dict] = None,
    installed_local_models: Optional[list[str]] = None,
) -> list[ProviderStatus]:
    """Resolve each provider to an availability status (sorted: available first)."""

    env = env if env is not None else _default_env()
    installed = installed_local_models or []
    statuses: list[ProviderStatus] = []
    for name, env_vars, base_url in specs:
        if _is_local(base_url):
            avail = len(installed) > 0
            detail = (
                f"{len(installed)} local model(s) installed"
                if avail
                else "no local models installed (e.g. `ollama pull gemma4:e4b`)"
            )
            statuses.append(ProviderStatus(name, "local", tuple(env_vars), avail, detail))
        else:
            cred_vars = credential_env_vars(env_vars)
            present = any(bool((env.get(var) or "").strip()) for var in cred_vars)
            if present:
                detail = "credential present"
            elif cred_vars:
                detail = "set " + " / ".join(cred_vars)
            else:
                detail = "no credential env var defined"
            statuses.append(ProviderStatus(name, "cloud", cred_vars, present, detail))
    return sorted(statuses, key=lambda s: (not s.available_now, s.kind, s.name))


def _policy_path() -> Path:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "jarvis_prime" / "model_policy.json"


def load_policy_recommended(path: Optional[Path] = None) -> list[str]:
    """Local models the bootstrap policy recommends (``model_policy.json``)."""

    target = Path(path) if path else _policy_path()
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [str(m) for m in (data.get("recommended_local_models") or [])]


def _norm(text: str) -> str:
    return text.lower().replace("-", "").replace(":", "").replace("/", "").replace("_", "")


def recommended_but_missing(recommended: Iterable[str], installed: Iterable[str]) -> list[str]:
    """Recommended local models that are not actually installed (tag-normalized)."""

    inst = [_norm(m) for m in installed]
    return [
        rec
        for rec in recommended
        if not any(_norm(rec) in m or m in _norm(rec) for m in inst if m)
    ]


def walk_fallback_chain(models: Iterable[str], invoke: Callable[[str], Any]) -> tuple[str, Any]:
    """Try each model via ``invoke(model)`` until one succeeds; return (model, result).

    Auto-fallback primitive: a caller hands the router's chosen+fallback_chain and
    a live invoke; the first model that doesn't raise wins. Raises ``RuntimeError``
    if every model fails (carrying the last error).
    """

    tried: list[str] = []
    last_exc: Optional[BaseException] = None
    for model in models:
        tried.append(model)
        try:
            return model, invoke(model)
        except Exception as exc:
            last_exc = exc
    raise RuntimeError(
        f"all {len(tried)} fallback model(s) failed ({tried}); last error: {last_exc}"
    )


@dataclass
class AvailabilityReport:
    providers: list[ProviderStatus]
    installed_local_models: list[str]
    recommended_local_models: list[str]
    recommended_missing: list[str]

    def available(self) -> list[ProviderStatus]:
        return [p for p in self.providers if p.available_now]

    def to_dict(self) -> dict:
        return {
            "available_count": len(self.available()),
            "provider_count": len(self.providers),
            "providers": [p.to_dict() for p in self.providers],
            "installed_local_models": list(self.installed_local_models),
            "recommended_local_models": list(self.recommended_local_models),
            "recommended_missing": list(self.recommended_missing),
        }

    def render(self) -> str:
        lines = [
            f"Model availability: {len(self.available())}/{len(self.providers)} "
            "provider(s) usable now",
        ]
        for status in self.providers:
            mark = "✅" if status.available_now else "  "
            lines.append(f"  {mark} {status.name:<22} [{status.kind}] {status.detail}")
        if self.installed_local_models:
            lines.append(f"Local models installed: {', '.join(self.installed_local_models)}")
        if self.recommended_missing:
            lines.append(
                "⚠ recommended but NOT installed: "
                + ", ".join(self.recommended_missing)
                + "  (pull them, or they won't be used)"
            )
        return "\n".join(lines)


def build_report(
    *,
    specs: Optional[Iterable[ProviderSpec]] = None,
    env: Optional[dict] = None,
    ollama_list: Optional[Callable[[], str]] = None,
    policy_path: Optional[Path] = None,
) -> AvailabilityReport:
    """Assemble the availability report from observable sources."""

    installed = installed_ollama_models(ollama_list)
    resolved_specs = list(specs) if specs is not None else load_provider_specs()
    statuses = provider_statuses(resolved_specs, env=env, installed_local_models=installed)
    recommended = load_policy_recommended(policy_path)
    missing = recommended_but_missing(recommended, installed)
    return AvailabilityReport(statuses, installed, recommended, missing)


__all__ = [
    "ProviderSpec",
    "ProviderStatus",
    "AvailabilityReport",
    "installed_ollama_models",
    "load_provider_specs",
    "provider_statuses",
    "load_policy_recommended",
    "recommended_but_missing",
    "walk_fallback_chain",
    "build_report",
]
