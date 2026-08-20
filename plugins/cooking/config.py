"""Config loader for the cooking plugin.

Reads a top-level ``cooking:`` block from ``~/.hermes/config.yaml``::

    cooking:
      enabled: true

All sources (TheMealDB, TheCocktailDB, Open Food Facts) are free and
key-less, so the only gate is the master ``enabled`` switch (default False).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CookingConfig:
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


def from_mapping(raw: Mapping[str, Any] | None) -> CookingConfig:
    if not raw or not isinstance(raw, Mapping):
        return CookingConfig()
    return CookingConfig(enabled=_coerce_bool(raw.get("enabled"), default=False))


def load_config() -> CookingConfig:
    try:
        from hermes_cli.config import load_config as _hermes_load_config
    except Exception:  # pragma: no cover
        return CookingConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return CookingConfig()
    return from_mapping(cfg.get("cooking") if isinstance(cfg, Mapping) else None)
