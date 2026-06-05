"""Config loader for the webutils plugin.

Reads a top-level ``webutils:`` block from ``~/.hermes/config.yaml``::

    webutils:
      enabled: true

All sources (goQR, ipapi.co, ipify, SunriseSunset.io) are free and key-less,
so the only gate is the master ``enabled`` switch (default False).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class WebutilsConfig:
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


def from_mapping(raw: Mapping[str, Any] | None) -> WebutilsConfig:
    if not raw or not isinstance(raw, Mapping):
        return WebutilsConfig()
    return WebutilsConfig(enabled=_coerce_bool(raw.get("enabled"), default=False))


def load_config() -> WebutilsConfig:
    try:
        from hermes_cli.config import load_config as _hermes_load_config
    except Exception:  # pragma: no cover
        return WebutilsConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return WebutilsConfig()
    return from_mapping(cfg.get("webutils") if isinstance(cfg, Mapping) else None)
