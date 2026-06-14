"""M.U.S.E component registry — machine-readable architecture inventory.

Loads ``docs/architecture/muse-component-registry.yaml`` (the canonical,
machine-readable inventory behind ``docs/architecture/MUSE_COMPONENT_REGISTRY.md``)
so docs, tooling, and tests share one description of the running system.

This module is a thin registry + validator. It does **not** import, execute, or
mutate any component it describes — it only reads the YAML and checks each entry
against the two governance sources of truth so the documented architecture can
never silently drift from the code:

* ``risk_class`` must be one of
  :data:`hermes_cli.jarvis_prime.work_packet.VALID_RISK_CLASSES`.
* every ``owner_gated_actions`` entry must be a member of
  :data:`hermes_cli.jarvis_prime.owner_auth.OWNER_GATED_ACTIONS` — the registry
  *references* the canonical frozenset rather than copying it (Constitution C9).

Clean-room, stdlib + pyyaml. No network calls. Mirrors the shape of
``hermes_cli/jarvis_prime/open_data_sources.py``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import yaml

from hermes_cli.jarvis_prime.owner_auth import OWNER_GATED_ACTIONS
from hermes_cli.jarvis_prime.work_packet import VALID_RISK_CLASSES

# Repo-root-relative default. parents[2] climbs
# hermes_cli/jarvis_prime/ -> hermes_cli/ -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = (
    _REPO_ROOT / "docs" / "architecture" / "muse-component-registry.yaml"
)
# A copy bundled alongside the module is preferred when present (e.g. an
# installed wheel that ships docs/ in package data); the repo checkout uses the
# docs/ companion above. Either resolves transparently.
_PACKAGED_REGISTRY_PATH = (
    Path(__file__).resolve().parent / "muse-component-registry.yaml"
)
# Escape hatch for non-standard installs.
REGISTRY_PATH_ENV = "MUSE_COMPONENT_REGISTRY"

SCHEMA = "muse.component_registry.v1"

VALID_KINDS = (
    "surface",
    "runtime",
    "orchestration",
    "cognition",
    "governance",
    "integration",
    "worker",
    "provider",
)

_REQUIRED_FIELDS = (
    "id",
    "name",
    "kind",
    "owner_module",
    "risk_class",
)


@dataclass
class Component:
    """One architectural component in the M.U.S.E system."""

    id: str
    name: str
    kind: str
    owner_module: str
    risk_class: str
    entrypoints: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    owner_gated_actions: tuple[str, ...] = ()
    tests: str = ""
    rollback: str = ""
    observability: str = ""
    docs: tuple[str, ...] = ()

    # -- predicates ---------------------------------------------------------

    @property
    def is_owner_gated(self) -> bool:
        """True when this component can reach any owner-gated action."""

        return bool(self.owner_gated_actions)

    def owner_module_path(self, repo_root: Optional[Path] = None) -> Path:
        """Resolve ``owner_module`` against the repo root."""

        return (repo_root or _REPO_ROOT) / self.owner_module

    def doc_paths(self, repo_root: Optional[Path] = None) -> list[Path]:
        """Resolve every ``docs`` entry against the repo root."""

        root = repo_root or _REPO_ROOT
        return [root / d for d in self.docs]

    # -- serialization ------------------------------------------------------

    @classmethod
    def from_dict(cls, d: dict) -> "Component":
        missing = [f for f in _REQUIRED_FIELDS if d.get(f) in (None, "")]
        if missing:
            raise ValueError(
                f"component {d.get('id', '?')!r} missing required "
                f"field(s): {', '.join(missing)}"
            )

        kind = str(d["kind"]).strip()
        if kind not in VALID_KINDS:
            raise ValueError(
                f"component {d['id']!r} has invalid kind {kind!r}; "
                f"expected one of {VALID_KINDS}"
            )

        risk_class = str(d["risk_class"]).strip()
        if risk_class not in VALID_RISK_CLASSES:
            raise ValueError(
                f"component {d['id']!r} has invalid risk_class {risk_class!r}; "
                f"expected one of {VALID_RISK_CLASSES}"
            )

        gated = tuple(str(a).strip() for a in (d.get("owner_gated_actions") or []))
        unknown = [a for a in gated if a not in OWNER_GATED_ACTIONS]
        if unknown:
            raise ValueError(
                f"component {d['id']!r} lists owner_gated_actions not in the "
                f"canonical owner_auth.OWNER_GATED_ACTIONS: {sorted(unknown)}. "
                "Extend the spec frozenset first — do not add a second copy."
            )

        return cls(
            id=str(d["id"]).strip(),
            name=str(d["name"]).strip(),
            kind=kind,
            owner_module=str(d["owner_module"]).strip(),
            risk_class=risk_class,
            entrypoints=tuple(d.get("entrypoints", []) or []),
            capabilities=tuple(d.get("capabilities", []) or []),
            owner_gated_actions=gated,
            tests=str(d.get("tests", "")).strip(),
            rollback=str(d.get("rollback", "")).strip(),
            observability=str(d.get("observability", "")).strip(),
            docs=tuple(d.get("docs", []) or []),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "owner_module": self.owner_module,
            "risk_class": self.risk_class,
            "entrypoints": list(self.entrypoints),
            "capabilities": list(self.capabilities),
            "owner_gated_actions": list(self.owner_gated_actions),
            "tests": self.tests,
            "rollback": self.rollback,
            "observability": self.observability,
            "docs": list(self.docs),
            "is_owner_gated": self.is_owner_gated,
        }


# --- registry loading -------------------------------------------------------


def resolve_registry_path(path: Optional[Path] = None) -> Path:
    """Resolve the registry YAML, tolerating both checkouts and installs.

    Order: explicit ``path`` arg, the ``MUSE_COMPONENT_REGISTRY`` env var, a
    copy bundled next to this module, then the ``docs/`` companion in a source
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
        "muse component registry not found. It ships with the hermes-agent "
        f"source tree at {DEFAULT_REGISTRY_PATH}. Run from a checkout, or set "
        f"{REGISTRY_PATH_ENV}=/path/to/muse-component-registry.yaml."
    )


def load_registry(path: Optional[Path] = None) -> list[Component]:
    """Parse the YAML registry and return components sorted by id.

    Raises ``ValueError`` on a wrong schema header, duplicate ids, or any entry
    that fails validation so a malformed registry fails loudly rather than
    silently dropping rows.
    """

    target = resolve_registry_path(path)
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}

    schema = str(raw.get("schema", "")).strip()
    if schema and schema != SCHEMA:
        raise ValueError(
            f"component registry has schema {schema!r}; expected {SCHEMA!r}"
        )

    rows = raw.get("components", []) or []
    components = [Component.from_dict(row) for row in rows]

    ids = [c.id for c in components]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"component registry has duplicate id(s): {dupes}")

    return sorted(components, key=lambda c: c.id)


# --- partitions -------------------------------------------------------------


def get(
    component_id: str, *, components: Optional[Iterable[Component]] = None
) -> Optional[Component]:
    pool = list(components) if components is not None else load_registry()
    for c in pool:
        if c.id == component_id:
            return c
    return None


def by_kind(
    kind: str, *, components: Optional[Iterable[Component]] = None
) -> list[Component]:
    pool = list(components) if components is not None else load_registry()
    return [c for c in pool if c.kind == kind]


def by_risk(
    risk_class: str, *, components: Optional[Iterable[Component]] = None
) -> list[Component]:
    pool = list(components) if components is not None else load_registry()
    return [c for c in pool if c.risk_class == risk_class]


def owner_gated_components(
    components: Optional[Iterable[Component]] = None,
) -> list[Component]:
    pool = list(components) if components is not None else load_registry()
    return [c for c in pool if c.is_owner_gated]


__all__ = [
    "Component",
    "DEFAULT_REGISTRY_PATH",
    "REGISTRY_PATH_ENV",
    "SCHEMA",
    "VALID_KINDS",
    "by_kind",
    "by_risk",
    "get",
    "load_registry",
    "owner_gated_components",
    "resolve_registry_path",
]
