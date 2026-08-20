"""Config loader for the codeintel plugin.

Reads a top-level ``codeintel:`` block from ``~/.hermes/config.yaml``::

    codeintel:
      enabled: true
      allow_code_execution: false   # extra gate for run_code

``dependency_audit`` and ``dependency_info`` only need ``enabled``. The
``run_code`` tool needs BOTH ``enabled`` and ``allow_code_execution`` — it
ships off by default because it sends the supplied code to a third-party
public sandbox (Piston). Both default False.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CodeintelConfig:
    enabled: bool = False
    allow_code_execution: bool = False


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


def from_mapping(raw: Mapping[str, Any] | None) -> CodeintelConfig:
    if not raw or not isinstance(raw, Mapping):
        return CodeintelConfig()
    return CodeintelConfig(
        enabled=_coerce_bool(raw.get("enabled"), default=False),
        allow_code_execution=_coerce_bool(
            raw.get("allow_code_execution"), default=False
        ),
    )


def load_config() -> CodeintelConfig:
    try:
        from hermes_cli.config import load_config as _hermes_load_config
    except Exception:  # pragma: no cover
        return CodeintelConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return CodeintelConfig()
    return from_mapping(cfg.get("codeintel") if isinstance(cfg, Mapping) else None)
