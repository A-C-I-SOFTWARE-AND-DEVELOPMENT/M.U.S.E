"""Config loader for the weather plugin.

Reads a single top-level ``weather:`` block from ``~/.hermes/config.yaml``::

    weather:
      enabled: true

There is no API key — Open-Meteo is free and unauthenticated — so the
only gate is the master ``enabled`` switch (default False, operator
opts in). The pattern mirrors ``plugins/github_assistant/config.py`` so
the two plugins read configuration the same way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class WeatherConfig:
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


def from_mapping(raw: Mapping[str, Any] | None) -> WeatherConfig:
    if not raw or not isinstance(raw, Mapping):
        return WeatherConfig()
    return WeatherConfig(enabled=_coerce_bool(raw.get("enabled"), default=False))


def load_config() -> WeatherConfig:
    """Read ``weather:`` from the active Hermes config; defaults on miss."""
    try:
        from hermes_cli.config import load_config as _hermes_load_config
    except Exception:  # pragma: no cover — config import path varies in tests
        return WeatherConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return WeatherConfig()
    return from_mapping(cfg.get("weather") if isinstance(cfg, Mapping) else None)
