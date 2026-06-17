"""Config loader for the recipe plugin.

Reads a single top-level ``recipe:`` block from ``~/.hermes/config.yaml``::

    recipe:
      enabled: true

``recipe_card`` is a pure, offline tool (no network, no key); the only gate is
the master ``enabled`` switch (default False, operator opts in). Mirrors
``plugins/places/config.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RecipeConfig:
    enabled: bool = False


def _coerce_bool(value: Any, *, default: bool) -> bool:
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
    return default


def from_mapping(raw: Mapping[str, Any] | None) -> RecipeConfig:
    if not raw or not isinstance(raw, Mapping):
        return RecipeConfig()
    return RecipeConfig(enabled=_coerce_bool(raw.get("enabled"), default=False))


def load_config() -> RecipeConfig:
    """Read ``recipe:`` from the active Hermes config; defaults on miss."""
    try:
        from hermes_cli.config import load_config as _hermes_load_config
    except Exception:  # pragma: no cover — config import path varies in tests
        return RecipeConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return RecipeConfig()
    return from_mapping(cfg.get("recipe") if isinstance(cfg, Mapping) else None)
