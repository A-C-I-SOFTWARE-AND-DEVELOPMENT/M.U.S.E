"""Config loader for the learning plugin.

Reads a top-level ``learning:`` block from ``~/.hermes/config.yaml``::

    learning:
      enabled: true

Open Library, Gutendex and ZenQuotes are key-less; Wolfram|Alpha needs
``WOLFRAM_APP_ID`` in ``~/.hermes/.env`` (read at call time, never stored
here). The only config gate is the master ``enabled`` switch (default False).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class LearningConfig:
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


def from_mapping(raw: Mapping[str, Any] | None) -> LearningConfig:
    if not raw or not isinstance(raw, Mapping):
        return LearningConfig()
    return LearningConfig(enabled=_coerce_bool(raw.get("enabled"), default=False))


def load_config() -> LearningConfig:
    try:
        from hermes_cli.config import load_config as _hermes_load_config
    except Exception:  # pragma: no cover
        return LearningConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return LearningConfig()
    return from_mapping(cfg.get("learning") if isinstance(cfg, Mapping) else None)
