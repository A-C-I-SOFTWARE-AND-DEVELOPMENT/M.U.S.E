"""Config loader + safety gates for the apify plugin.

The plugin reads a single top-level ``apify:`` block from
``~/.hermes/config.yaml``::

    apify:
      enabled: true
      allow_runs: false
      allowed_actors:
        - "apify/website-content-crawler"

Defaults err on the safer side, mirroring github_assistant:

  * ``enabled``        — False. Operator opts in.
  * ``allow_runs``     — False. ``apify_run_actor`` refuses to run (and is
    hidden from the model), because starting an Actor run consumes paid
    Apify compute units. The three read tools work without it.
  * ``allowed_actors`` — empty list. **Empty means "no allowlist
    enforced"**; any Actor the token can reach may be run. Set a
    non-empty list to switch into deny-by-default mode for runs.

Actor identifiers are accepted in either ``username/name`` or
``username~name`` form (the Apify REST path uses the tilde) or as a bare
Actor ID; the allowlist normalises both ``/`` and ``~`` to a single
canonical form so an entry matches regardless of which separator the
caller typed.

This module is pure-Python — no I/O during import — so the plugin's
``register(ctx)`` can call ``load_config()`` cheaply when the plugin
loader fires. We re-read on every tool call so an operator can flip
``allow_runs`` without restarting the agent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

# Default run timeout (seconds) for run-sync calls, and the hard ceiling we
# refuse to exceed regardless of the caller's request. Apify caps run-sync
# at 300s server-side; we stay at or under that.
DEFAULT_RUN_TIMEOUT_SECS = 60
MAX_RUN_TIMEOUT_SECS = 300

# Canonical actor-id charset after normalising '/' -> '~'. Apify Actor IDs
# are short alphanumerics; slugs are ``username~actorName`` with the same
# safe punctuation set. We reject anything that could enable path traversal.
_ACTOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~-]*$")


def normalise_actor_id(actor_id: str) -> str:
    """Return the canonical path form of an Actor id (``/`` -> ``~``)."""
    return actor_id.strip().replace("/", "~")


@dataclass(frozen=True)
class ApifyConfig:
    """Resolved apify configuration."""

    enabled: bool = False
    allow_runs: bool = False
    allowed_actors: tuple[str, ...] = ()

    def is_actor_allowed(self, actor_id: str) -> bool:
        """Allowlist check for runs. Empty list = no allowlist enforced."""
        if not self.allowed_actors:
            return True
        return normalise_actor_id(actor_id) in self.allowed_actors


class ConfigError(ValueError):
    """Raised when the apify: block in config.yaml has the wrong shape."""


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
    raise ConfigError(f"apify.{key} must be a boolean, got {value!r}")


def _coerce_actor_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ConfigError(
            "apify.allowed_actors must be a list of Actor id/slug strings"
        )
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ConfigError(
                f"apify.allowed_actors entry must be a string, got {item!r}"
            )
        canonical = normalise_actor_id(item)
        if not canonical or not _ACTOR_RE.match(canonical):
            raise ConfigError(
                f"apify.allowed_actors entry {item!r} is not a valid Actor id/slug"
            )
        out.append(canonical)
    return tuple(out)


def from_mapping(raw: Mapping[str, Any] | None) -> ApifyConfig:
    """Parse an apify: block (already loaded from YAML) into ApifyConfig."""
    if not raw:
        return ApifyConfig()
    if not isinstance(raw, Mapping):
        raise ConfigError(f"apify: must be a mapping, got {type(raw).__name__}")
    return ApifyConfig(
        enabled=_coerce_bool(raw.get("enabled"), key="enabled", default=False),
        allow_runs=_coerce_bool(
            raw.get("allow_runs"), key="allow_runs", default=False
        ),
        allowed_actors=_coerce_actor_list(raw.get("allowed_actors")),
    )


def load_config() -> ApifyConfig:
    """Read ``apify:`` from the active Hermes config. Returns defaults on miss.

    Lazily imports Hermes' config loader so importing this plugin doesn't
    pull the whole config stack in for every tool call.
    """
    try:
        from hermes_cli.config import load_config as _hermes_load_config  # heavy
    except Exception:  # pragma: no cover — config import path varies in tests
        return ApifyConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return ApifyConfig()
    return from_mapping(cfg.get("apify") if isinstance(cfg, Mapping) else None)


def validate_actor_id(actor_id: Any) -> str:
    """Normalise + validate a caller-supplied Actor id/slug.

    Returns the canonical path form (``username~actorName`` or a bare id).
    Raises :class:`ConfigError` on anything that looks like path traversal
    or injection so it never reaches the API URL.
    """
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ConfigError("actor_id must be a non-empty string")
    canonical = normalise_actor_id(actor_id)
    if ".." in canonical or "\x00" in canonical or "/" in canonical:
        raise ConfigError(f"actor_id {actor_id!r} contains forbidden characters")
    if not _ACTOR_RE.match(canonical):
        raise ConfigError(
            f"actor_id {actor_id!r} must be an Actor id or 'username/name' slug"
        )
    return canonical


def validate_store_id(value: Any, *, label: str) -> str:
    """Validate a dataset-id / run-id style store identifier."""
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label} must be a non-empty string")
    v = value.strip()
    if ".." in v or "/" in v or "~" in v or "\x00" in v:
        raise ConfigError(f"{label} {value!r} contains forbidden characters")
    if not _ACTOR_RE.match(v):
        raise ConfigError(f"{label} {value!r} must match [A-Za-z0-9._-]+")
    return v
