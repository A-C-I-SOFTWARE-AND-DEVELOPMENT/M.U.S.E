"""Config loader for the places plugin.

Reads a single top-level ``places:`` block from ``~/.hermes/config.yaml``::

    places:
      enabled: true

There is no API key — OpenStreetMap Nominatim is free and unauthenticated — so
the only gate is the master ``enabled`` switch (default False, operator opts in).
Mirrors ``plugins/weather/config.py`` so the plugins read configuration the same
way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PlacesConfig:
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


def from_mapping(raw: Mapping[str, Any] | None) -> PlacesConfig:
    if not raw or not isinstance(raw, Mapping):
        return PlacesConfig()
    return PlacesConfig(enabled=_coerce_bool(raw.get("enabled"), default=False))


def load_config() -> PlacesConfig:
    """Read ``places:`` from the active Hermes config; defaults on miss."""
    try:
        from hermes_cli.config import load_config as _hermes_load_config
    except Exception:  # pragma: no cover — config import path varies in tests
        return PlacesConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return PlacesConfig()
    return from_mapping(cfg.get("places") if isinstance(cfg, Mapping) else None)
