"""Config loader + safety gates for the vercel plugin.

The plugin reads a single top-level ``vercel:`` block from
``~/.hermes/config.yaml``::

    vercel:
      enabled: true
      allow_writes: false
      allowed_projects:
        - "my-app"
        - "prj_AbC123"

Defaults err on the safer side:

  * ``enabled``          — False. Operator opts in.
  * ``allow_writes``     — False. ``vercel_set_env``, ``vercel_deploy`` and
    ``vercel_cancel_deployment`` refuse to run.
  * ``allowed_projects`` — empty tuple. **Empty means "no allowlist
    enforced"** for read tools; any project the token can reach is
    reachable. A *write* against a project still requires ``allow_writes``
    AND an owner-approved decision verdict regardless of this list. Set a
    non-empty list to switch into deny-by-default mode (read + write).

Mirrors ``plugins/github_assistant/config.py`` — pure-Python, no I/O at
import, re-read on every tool call so an operator can flip a flag without
restarting the agent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


# Vercel project identifiers are either a name (``my-app``) or an id
# (``prj_...``); both match this conservative character class.
_PROJECT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class VercelConfig:
    """Resolved vercel-plugin configuration."""

    enabled: bool = False
    allow_writes: bool = False
    allowed_projects: tuple[str, ...] = ()

    def is_project_allowed(self, project: str) -> bool:
        """Allowlist check. Empty list = no allowlist enforced."""
        if not self.allowed_projects:
            return True
        return project in self.allowed_projects


class ConfigError(ValueError):
    """Raised when the vercel: block in config.yaml has the wrong shape."""


def _coerce_bool(value: Any, *, key: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "yes", "1", "on"}:
            return True
        if v in {"false", "no", "0", "off"}:
            return False
    raise ConfigError(f"vercel.{key} must be a boolean, got {value!r}")


def _coerce_project_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ConfigError("vercel.allowed_projects must be a list of strings")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ConfigError(
                f"vercel.allowed_projects entry must be a string, got {item!r}"
            )
        item = item.strip()
        if not _PROJECT_RE.match(item):
            raise ConfigError(
                f"vercel.allowed_projects entry {item!r} contains invalid characters"
            )
        out.append(item)
    return tuple(out)


def from_mapping(raw: Mapping[str, Any] | None) -> VercelConfig:
    """Parse a vercel: block (already loaded from YAML) into VercelConfig."""
    if not raw:
        return VercelConfig()
    if not isinstance(raw, Mapping):
        raise ConfigError(f"vercel: must be a mapping, got {type(raw).__name__}")
    return VercelConfig(
        enabled=_coerce_bool(raw.get("enabled"), key="enabled", default=False),
        allow_writes=_coerce_bool(
            raw.get("allow_writes"), key="allow_writes", default=False
        ),
        allowed_projects=_coerce_project_list(raw.get("allowed_projects")),
    )


def load_config() -> VercelConfig:
    """Read ``vercel:`` from the active Hermes config. Returns defaults on miss.

    Called lazily so importing this plugin doesn't pull the whole config
    stack in for every tool call. Any failure degrades to safe defaults
    (disabled, writes blocked).
    """
    try:
        from hermes_cli.config import load_config as _hermes_load_config  # heavy
    except Exception:  # pragma: no cover — config import path varies in tests
        return VercelConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return VercelConfig()
    return from_mapping(cfg.get("vercel") if isinstance(cfg, Mapping) else None)


def validate_project(project: str) -> None:
    """Reject obvious path-traversal / injection attempts before they hit the API."""
    if not isinstance(project, str) or not project:
        raise ConfigError("project must be a non-empty string")
    if ".." in project or "/" in project or "\x00" in project:
        raise ConfigError(f"project {project!r} contains forbidden characters")
    if not _PROJECT_RE.match(project):
        raise ConfigError(f"project {project!r} must match [A-Za-z0-9._-]+")
