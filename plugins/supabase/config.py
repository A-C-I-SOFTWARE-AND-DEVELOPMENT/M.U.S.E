"""Config loader + safety gates for the supabase plugin.

The plugin reads a single top-level ``supabase:`` block from
``~/.hermes/config.yaml``::

    supabase:
      enabled: true
      allow_writes: false
      allow_service_role: false
      allowed_tables:
        - "public.posts"
        - "profiles"

Defaults err on the safer side:

  * ``enabled``            — False. Operator opts in.
  * ``allow_writes``      — False. ``supabase_execute_sql`` and
    ``supabase_apply_migration`` refuse to run.
  * ``allow_service_role`` — False. Read tools use the anon key; the
    service-role key is only consulted when this is explicitly True. The
    service-role key is never returned to the model or the cockpit.
  * ``allowed_tables``     — empty tuple. **Empty means "no allowlist
    enforced"** for read queries. A table name may be given bare
    (``profiles``) or schema-qualified (``public.profiles``); both forms
    are accepted on the list and matched leniently.

Mirrors ``plugins/github_assistant/config.py`` — pure-Python, no I/O at
import, re-read on every tool call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


# Postgres identifiers: optional schema-qualifier then a table name.
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


@dataclass(frozen=True)
class SupabaseConfig:
    """Resolved supabase-plugin configuration."""

    enabled: bool = False
    allow_writes: bool = False
    allow_service_role: bool = False
    allowed_tables: tuple[str, ...] = ()

    def is_table_allowed(self, table: str) -> bool:
        """Allowlist check. Empty list = no allowlist enforced.

        Matches either the bare table name or its schema-qualified form, so
        ``profiles`` on the list permits ``public.profiles`` and vice versa.
        """
        if not self.allowed_tables:
            return True
        bare = table.split(".")[-1]
        allowed_bare = {t.split(".")[-1] for t in self.allowed_tables}
        return table in self.allowed_tables or bare in allowed_bare


class ConfigError(ValueError):
    """Raised when the supabase: block in config.yaml has the wrong shape."""


def _coerce_bool(value: Any, *, key: str, default: bool) -> bool:
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
    raise ConfigError(f"supabase.{key} must be a boolean, got {value!r}")


def _coerce_table_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ConfigError("supabase.allowed_tables must be a list of strings")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ConfigError(
                f"supabase.allowed_tables entry must be a string, got {item!r}"
            )
        item = item.strip()
        if not _TABLE_RE.match(item):
            raise ConfigError(
                f"supabase.allowed_tables entry {item!r} is not a valid table name"
            )
        out.append(item)
    return tuple(out)


def from_mapping(raw: Mapping[str, Any] | None) -> SupabaseConfig:
    """Parse a supabase: block (already loaded from YAML) into SupabaseConfig."""
    if not raw:
        return SupabaseConfig()
    if not isinstance(raw, Mapping):
        raise ConfigError(f"supabase: must be a mapping, got {type(raw).__name__}")
    return SupabaseConfig(
        enabled=_coerce_bool(raw.get("enabled"), key="enabled", default=False),
        allow_writes=_coerce_bool(
            raw.get("allow_writes"), key="allow_writes", default=False
        ),
        allow_service_role=_coerce_bool(
            raw.get("allow_service_role"), key="allow_service_role", default=False
        ),
        allowed_tables=_coerce_table_list(raw.get("allowed_tables")),
    )


def load_config() -> SupabaseConfig:
    """Read ``supabase:`` from the active Hermes config. Returns defaults on miss.

    Called lazily; any failure degrades to safe defaults (disabled, writes
    blocked, service-role off).
    """
    try:
        from hermes_cli.config import load_config as _hermes_load_config  # heavy
    except Exception:  # pragma: no cover — config import path varies in tests
        return SupabaseConfig()
    try:
        cfg = _hermes_load_config()
    except Exception:
        return SupabaseConfig()
    return from_mapping(cfg.get("supabase") if isinstance(cfg, Mapping) else None)


def validate_table(table: str) -> None:
    """Reject injection attempts before a table name reaches PostgREST."""
    if not isinstance(table, str) or not table:
        raise ConfigError("table must be a non-empty string")
    if not _TABLE_RE.match(table):
        raise ConfigError(
            f"table {table!r} must be a valid identifier (optionally schema-qualified)"
        )
