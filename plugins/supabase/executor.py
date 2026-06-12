"""Out-of-band executor for Supabase write actions.

Invoked only by the owner-approval path via :mod:`muse_cli.action_executors`,
never the model's tool loop. On owner approval, the proposed migration is
authored as a timestamped file under ``supabase/migrations/``; applying it to a
live database remains the operator's explicit step (``supabase db push``), so
this never mutates a database on its own.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _write_migration(name: str, sql: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_") or "migration"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    out_dir = Path.cwd() / "supabase" / "migrations"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{ts}_{slug}.sql"
    path.write_text(sql if sql.endswith("\n") else sql + "\n", encoding="utf-8")
    return path


def apply_migration(params: Dict[str, Any]) -> Dict[str, Any]:
    name = params.get("name") or "adhoc"
    sql = params.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        return {"success": False, "error": "bad_params", "executed": False}
    path = _write_migration(str(name), sql)
    return {
        "success": True,
        "executed": True,
        "wrote_migration": True,
        "applied": False,
        "migration_path": str(path),
        "message": "Migration file authored. Run `supabase db push` to apply it.",
    }


def register_executors() -> None:
    """Register the Supabase executors. Safe to call repeatedly (idempotent)."""
    from muse_cli.action_executors import register

    register("supabase.execute_sql", apply_migration)
    register("supabase.apply_migration", apply_migration)
