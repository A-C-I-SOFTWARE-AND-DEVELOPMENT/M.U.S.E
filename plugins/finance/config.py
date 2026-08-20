"""Config loader for the finance plugin.

Reads a single top-level ``finance:`` block from ``~/.hermes/config.yaml``::

    finance:
      enabled: true

All three data sources (CoinGecko, Frankfurter, Stooq) are free and
key-less, so the only gate is the master ``enabled`` switch (default
False). Mirrors ``plugins/weather/config.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class FinanceConfig:
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


def from_mapping(raw: Mapping[str, Any] | None) -> FinanceConfig:
    if not raw or not isinstance(raw, Mapping):
        return FinanceConfig()
    return FinanceConfig(enabled=_coerce_bool(raw.get("enabled"), default=False))


def load_config() -> FinanceConfig:
    try:
        from hermes_cli.config import load_config as _hermes_load_config
    except Exception:  # pragma: no cover
        return FinanceConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return FinanceConfig()
    return from_mapping(cfg.get("finance") if isinstance(cfg, Mapping) else None)
