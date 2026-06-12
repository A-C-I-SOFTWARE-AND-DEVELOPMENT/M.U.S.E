"""Config loader for the branding plugin.

Reads a top-level ``branding:`` block from ``~/.hermes/config.yaml``::

    branding:
      enabled: true

TheColorAPI and Lorem Picsum are key-less. Unsplash needs
``UNSPLASH_ACCESS_KEY`` and Google Fonts needs ``GOOGLE_FONTS_API_KEY``
(both read at call time from ``~/.hermes/.env``). The only config gate is
the master ``enabled`` switch (default False).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class BrandingConfig:
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


def from_mapping(raw: Mapping[str, Any] | None) -> BrandingConfig:
    if not raw or not isinstance(raw, Mapping):
        return BrandingConfig()
    return BrandingConfig(enabled=_coerce_bool(raw.get("enabled"), default=False))


def load_config() -> BrandingConfig:
    try:
        from muse_cli.config import load_config as _hermes_load_config
    except Exception:  # pragma: no cover
        return BrandingConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return BrandingConfig()
    return from_mapping(cfg.get("branding") if isinstance(cfg, Mapping) else None)
