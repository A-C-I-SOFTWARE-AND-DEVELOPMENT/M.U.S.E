"""Config loader + safety gates for the github-assistant plugin.

The plugin reads a single top-level ``github:`` block from
``~/.hermes/config.yaml``::

    github:
      enabled: true
      allow_writes: false
      allowed_repositories:
        - "echerd27-design/hermes-agent"

Defaults err on the safer side:

  * ``enabled``     — False. Operator opts in.
  * ``allow_writes`` — False. `github_create_issue` and
    `github_comment_on_issue_or_pr` refuse to run.
  * ``allowed_repositories`` — empty list. **Empty means "no allowlist
    enforced"**; any repo the token can reach is reachable. Set a
    non-empty list to switch into deny-by-default mode.

This module is pure-Python — no I/O during import — so the plugin's
``register(ctx)`` can call ``load_config()`` cheaply when the plugin
loader fires. We also re-read on every tool call so an operator can
flip ``allow_writes`` without restarting the agent (changes land on
disk; the next tool call honours them).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping


_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class GithubConfig:
    """Resolved github-assistant configuration."""

    enabled: bool = False
    allow_writes: bool = False
    allowed_repositories: tuple[str, ...] = ()

    def is_repo_allowed(self, owner: str, name: str) -> bool:
        """Allowlist check. Empty list = no allowlist enforced."""
        if not self.allowed_repositories:
            return True
        return f"{owner}/{name}" in self.allowed_repositories


class ConfigError(ValueError):
    """Raised when the github: block in config.yaml has the wrong shape."""


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
    raise ConfigError(f"github.{key} must be a boolean, got {value!r}")


def _coerce_repo_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ConfigError(
            "github.allowed_repositories must be a list of 'owner/name' strings"
        )
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ConfigError(
                f"github.allowed_repositories entry must be a string, got {item!r}"
            )
        item = item.strip()
        if "/" not in item:
            raise ConfigError(
                f"github.allowed_repositories entry must be 'owner/name', got {item!r}"
            )
        owner, _, name = item.partition("/")
        if not _REPO_RE.match(owner) or not _REPO_RE.match(name):
            raise ConfigError(
                f"github.allowed_repositories entry {item!r} contains invalid characters"
            )
        out.append(f"{owner}/{name}")
    return tuple(out)


def from_mapping(raw: Mapping[str, Any] | None) -> GithubConfig:
    """Parse a github: block (already loaded from YAML) into GithubConfig."""
    if not raw:
        return GithubConfig()
    if not isinstance(raw, Mapping):
        raise ConfigError(f"github: must be a mapping, got {type(raw).__name__}")
    return GithubConfig(
        enabled=_coerce_bool(raw.get("enabled"), key="enabled", default=False),
        allow_writes=_coerce_bool(
            raw.get("allow_writes"), key="allow_writes", default=False
        ),
        allowed_repositories=_coerce_repo_list(raw.get("allowed_repositories")),
    )


def load_config() -> GithubConfig:
    """Read ``github:`` from the active Hermes config. Returns defaults on miss.

    Hermes' own config loader (``hermes_cli.config.load_config``) handles
    file lookup, env-var interpolation (``${VAR}``), and deep-merging
    user/project configs. We call it lazily so importing this plugin
    doesn't pull the whole config stack in for every tool call.
    """
    try:
        from hermes_cli.config import load_config as _hermes_load_config  # heavy
    except Exception:  # pragma: no cover — config import path varies in tests
        return GithubConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return GithubConfig()
    return from_mapping(cfg.get("github") if isinstance(cfg, Mapping) else None)


def validate_owner_name(owner: str, name: str) -> None:
    """Reject obvious path-traversal / injection attempts before they hit the API."""
    for label, value in (("owner", owner), ("name", name)):
        if not isinstance(value, str) or not value:
            raise ConfigError(f"{label} must be a non-empty string")
        if ".." in value or "/" in value or "\x00" in value:
            raise ConfigError(f"{label} {value!r} contains forbidden characters")
        if not _REPO_RE.match(value):
            raise ConfigError(f"{label} {value!r} must match [A-Za-z0-9._-]+")
