"""Config loader for the recommend plugin.

Reads a single top-level ``recommend:`` block from ``~/.hermes/config.yaml``::

    recommend:
      enabled: true

``recommend_surfaces`` is a pure, offline tool; the only gate is the master
``enabled`` switch (default False, operator opts in). Mirrors
``plugins/places/config.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RecommendConfig:
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


def from_mapping(raw: Mapping[str, Any] | None) -> RecommendConfig:
    if not raw or not isinstance(raw, Mapping):
        return RecommendConfig()
    return RecommendConfig(enabled=_coerce_bool(raw.get("enabled"), default=False))


def load_config() -> RecommendConfig:
    """Read ``recommend:`` from the active Hermes config; defaults on miss."""
    try:
        from hermes_cli.config import load_config as _hermes_load_config
    except Exception:  # pragma: no cover — config import path varies in tests
        return RecommendConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return RecommendConfig()
    return from_mapping(cfg.get("recommend") if isinstance(cfg, Mapping) else None)
