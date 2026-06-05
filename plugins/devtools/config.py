"""Config loader for the devtools plugin.

Reads a single top-level ``devtools:`` block from ``~/.hermes/config.yaml``::

    devtools:
      enabled: true

All sources (PyPI, npm, crates.io, Stack Exchange) are free and key-less,
so the only gate is the master ``enabled`` switch (default False). Mirrors
``plugins/weather/config.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class DevtoolsConfig:
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


def from_mapping(raw: Mapping[str, Any] | None) -> DevtoolsConfig:
    if not raw or not isinstance(raw, Mapping):
        return DevtoolsConfig()
    return DevtoolsConfig(enabled=_coerce_bool(raw.get("enabled"), default=False))


def load_config() -> DevtoolsConfig:
    try:
        from hermes_cli.config import load_config as _hermes_load_config
    except Exception:  # pragma: no cover
        return DevtoolsConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return DevtoolsConfig()
    return from_mapping(cfg.get("devtools") if isinstance(cfg, Mapping) else None)
