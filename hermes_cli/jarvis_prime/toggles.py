"""M.U.S.E feature-toggle registry — the runtime catalog of opt-in / owner-gated
environment toggles.

Loads ``docs/architecture/muse-toggle-registry.yaml`` (the canonical,
machine-readable inventory behind ``docs/security/opt-in-owner-gated-inventory.md``)
so docs, the CLI, and tests share one description of every toggle MUSE honours.

This module is a thin registry + validator + *resolver*. It does **not** import
or execute any subsystem a toggle controls — it only reads the YAML, validates
each entry, and (optionally) resolves a toggle's effective on/off state against
an environment mapping using the project's shared truthy parser
(:func:`utils.is_truthy_value`), so resolution matches every hand-rolled
``os.getenv(...) in {"1","true",...}`` read scattered across the codebase.

Group legend (see the YAML header):

* ``B1`` — opt-in **and** owner-gated.
* ``B2`` — spawn / self-improvement gates.
* ``B3`` — cognition / retrieval opt-ins.
* ``B4`` — approval / safety toggles.
* ``B5`` — runtime / deployment toggles.

Clean-room, stdlib + pyyaml. No network calls. Mirrors the shape of
``hermes_cli/jarvis_prime/component_registry.py``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional

import yaml

from utils import is_truthy_value

# Repo-root-relative default. parents[2] climbs
# hermes_cli/jarvis_prime/ -> hermes_cli/ -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = (
    _REPO_ROOT / "docs" / "architecture" / "muse-toggle-registry.yaml"
)
# A copy bundled alongside the module is preferred when present (e.g. an
# installed wheel that ships docs/ in package data); the repo checkout uses the
# docs/ companion above. Either resolves transparently.
_PACKAGED_REGISTRY_PATH = (
    Path(__file__).resolve().parent / "muse-toggle-registry.yaml"
)
# Escape hatch for non-standard installs.
REGISTRY_PATH_ENV = "MUSE_TOGGLE_REGISTRY"

SCHEMA = "muse.toggle_registry.v1"

VALID_GROUPS = ("B1", "B2", "B3", "B4", "B5")

# Toggle env vars are namespaced to the project's three prefixes.
_ENV_RE = re.compile(r"^(MUSE|HERMES|JARVIS)_[A-Z0-9_]+$")

_REQUIRED_FIELDS = ("env", "group", "summary")


@dataclass
class Toggle:
    """One opt-in / owner-gated environment toggle MUSE honours."""

    env: str
    group: str
    summary: str
    owner_gated: bool = False
    default: bool = False
    read_sites: tuple[str, ...] = ()
    docs: tuple[str, ...] = ()

    # -- predicates ---------------------------------------------------------

    def is_enabled(self, env: Optional[Mapping[str, str]] = None) -> bool:
        """Resolve the toggle's effective state against *env* (default os.environ).

        Uses the project's shared truthy parser so this matches the ad-hoc reads
        in the wired modules. An unset variable resolves to :attr:`default`.
        """

        source = os.environ if env is None else env
        raw = source.get(self.env)
        if raw is None:
            return self.default
        return is_truthy_value(raw, default=self.default)

    def read_site_paths(self, repo_root: Optional[Path] = None) -> list[Path]:
        """Resolve every ``read_sites`` entry against the repo root."""

        root = repo_root or _REPO_ROOT
        return [root / s for s in self.read_sites]

    def doc_paths(self, repo_root: Optional[Path] = None) -> list[Path]:
        """Resolve every ``docs`` entry against the repo root."""

        root = repo_root or _REPO_ROOT
        return [root / d for d in self.docs]

    # -- serialization ------------------------------------------------------

    @classmethod
    def from_dict(cls, d: dict) -> "Toggle":
        missing = [f for f in _REQUIRED_FIELDS if d.get(f) in (None, "")]
        if missing:
            raise ValueError(
                f"toggle {d.get('env', '?')!r} missing required "
                f"field(s): {', '.join(missing)}"
            )

        env = str(d["env"]).strip()
        if not _ENV_RE.match(env):
            raise ValueError(
                f"toggle {env!r} is not a valid env name; expected "
                r"^(MUSE|HERMES|JARVIS)_[A-Z0-9_]+$"
            )

        group = str(d["group"]).strip()
        if group not in VALID_GROUPS:
            raise ValueError(
                f"toggle {env!r} has invalid group {group!r}; "
                f"expected one of {VALID_GROUPS}"
            )

        owner_gated = bool(d.get("owner_gated", False))
        if group == "B1" and not owner_gated:
            raise ValueError(
                f"toggle {env!r} is in group B1 but not owner_gated; "
                "B1 is the opt-in AND owner-gated band."
            )

        return cls(
            env=env,
            group=group,
            summary=str(d["summary"]).strip(),
            owner_gated=owner_gated,
            default=bool(d.get("default", False)),
            read_sites=tuple(str(s).strip() for s in (d.get("read_sites") or [])),
            docs=tuple(str(s).strip() for s in (d.get("docs") or [])),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "env": self.env,
            "group": self.group,
            "summary": self.summary,
            "owner_gated": self.owner_gated,
            "default": self.default,
            "read_sites": list(self.read_sites),
            "docs": list(self.docs),
        }


# --- registry loading -------------------------------------------------------


def resolve_registry_path(path: Optional[Path] = None) -> Path:
    """Resolve the registry YAML, tolerating both checkouts and installs.

    Order: explicit ``path`` arg, the ``MUSE_TOGGLE_REGISTRY`` env var, a copy
    bundled next to this module, then the ``docs/`` companion in a source
    checkout. Raises an actionable ``FileNotFoundError`` if none exist.
    """

    if path is not None:
        return Path(path)
    env = os.environ.get(REGISTRY_PATH_ENV)
    if env:
        return Path(env)
    for candidate in (_PACKAGED_REGISTRY_PATH, DEFAULT_REGISTRY_PATH):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "muse toggle registry not found. It ships with the hermes-agent source "
        f"tree at {DEFAULT_REGISTRY_PATH}. Run from a checkout, or set "
        f"{REGISTRY_PATH_ENV}=/path/to/muse-toggle-registry.yaml."
    )


def load_toggles(path: Optional[Path] = None) -> list[Toggle]:
    """Parse the YAML registry and return toggles sorted by (group, env).

    Raises ``ValueError`` on a wrong schema header, a duplicate env var, or any
    entry that fails validation so a malformed registry fails loudly rather than
    silently dropping rows.
    """

    target = resolve_registry_path(path)
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}

    schema = str(raw.get("schema", "")).strip()
    if schema and schema != SCHEMA:
        raise ValueError(
            f"toggle registry has schema {schema!r}; expected {SCHEMA!r}"
        )

    rows = raw.get("toggles", []) or []
    toggles = [Toggle.from_dict(row) for row in rows]

    envs = [t.env for t in toggles]
    if len(set(envs)) != len(envs):
        dupes = sorted({e for e in envs if envs.count(e) > 1})
        raise ValueError(f"toggle registry has duplicate env(s): {dupes}")

    return sorted(toggles, key=lambda t: (t.group, t.env))


# --- partitions / lookups ---------------------------------------------------


def get(
    env_name: str, *, toggles: Optional[Iterable[Toggle]] = None
) -> Optional[Toggle]:
    """Look up one toggle by env var name."""

    pool = list(toggles) if toggles is not None else load_toggles()
    for t in pool:
        if t.env == env_name:
            return t
    return None


def by_group(
    group: str, *, toggles: Optional[Iterable[Toggle]] = None
) -> list[Toggle]:
    pool = list(toggles) if toggles is not None else load_toggles()
    return [t for t in pool if t.group == group]


def owner_gated_toggles(
    toggles: Optional[Iterable[Toggle]] = None,
) -> list[Toggle]:
    pool = list(toggles) if toggles is not None else load_toggles()
    return [t for t in pool if t.owner_gated]


def is_enabled(
    env_name: str,
    *,
    env: Optional[Mapping[str, str]] = None,
    toggles: Optional[Iterable[Toggle]] = None,
) -> bool:
    """Resolve a toggle by name. Unknown toggles resolve to ``False``.

    A convenience wrapper so callers can ask the registry directly rather than
    re-deriving a truthy parse. Unknown names are treated as off (not an error)
    so a typo never silently enables behaviour.
    """

    t = get(env_name, toggles=toggles)
    if t is None:
        return False
    return t.is_enabled(env)


def evaluate_all(
    env: Optional[Mapping[str, str]] = None,
    *,
    toggles: Optional[Iterable[Toggle]] = None,
) -> list[tuple[Toggle, bool]]:
    """Return every toggle paired with its resolved on/off state."""

    pool = list(toggles) if toggles is not None else load_toggles()
    return [(t, t.is_enabled(env)) for t in pool]


__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "REGISTRY_PATH_ENV",
    "SCHEMA",
    "VALID_GROUPS",
    "Toggle",
    "by_group",
    "evaluate_all",
    "get",
    "is_enabled",
    "load_toggles",
    "owner_gated_toggles",
    "resolve_registry_path",
]
