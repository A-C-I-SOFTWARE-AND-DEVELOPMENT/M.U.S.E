"""Agent-facing Supabase tools registered by the supabase plugin.

Two read tools (PostgREST row query, table listing) and two owner-gated write
tools (execute SQL, apply migration). Writes do **not** mutate a live database
in this release — when authorized they author a timestamped migration file
under ``supabase/migrations/`` for the operator to apply with ``supabase db
push``. A live PostgREST/Management-API execution path is a deliberate
follow-up.

Safety model (defence in depth):

  1. ``supabase.enabled`` is True and the project is configured (``check_fn``).
  2. ``supabase.allow_writes`` is True (master switch for the write tools).
  3. A unified :class:`DecisionVerdict` is computed: writes are owner-gated
     (``ask`` + exact owner phrase) and a secret embedded in the SQL forces a
     ``refuse``.

The service-role key bypasses row-level security and is only used by
``supabase_query`` when ``supabase.allow_service_role`` is True *and* the call
opts in. Keys are never logged or returned. Returned rows are size-capped.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from plugins.supabase import config as supabase_config
from plugins.supabase.client import DEFAULT_ROW_CAP, HARD_ROW_CAP, SupabaseClient

logger = logging.getLogger("supabase.tools")

_MAX_SQL_BYTES = 100_000


def _json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _err(error: str, message: str = "", **extra: Any) -> str:
    body: Dict[str, Any] = {"success": False, "error": error}
    if message:
        body["message"] = message
    body.update(extra)
    return _json(body)


def _ok(**payload: Any) -> str:
    return _json({"success": True, **payload})


def check_supabase_requirements() -> bool:
    """True when ``supabase.enabled`` and the project is configured."""
    cfg = supabase_config.load_config()
    if not cfg.enabled:
        return False
    return SupabaseClient().has_config()


class _GateFailure(Exception):
    def __init__(self, payload_json: str) -> None:
        self.payload_json = payload_json
        super().__init__(payload_json)


def _require_enabled() -> supabase_config.SupabaseConfig:
    cfg = supabase_config.load_config()
    if not cfg.enabled:
        raise _GateFailure(_err("plugin_disabled", "supabase.enabled is false"))
    return cfg


def _require_client() -> SupabaseClient:
    client = SupabaseClient()
    if not client.has_config():
        raise _GateFailure(
            _err(
                "not_configured",
                "SUPABASE_URL and SUPABASE_ANON_KEY are not configured. "
                "Set them in ~/.hermes/.env.",
            )
        )
    return client


def _scan_secrets(text: str) -> list[Any]:
    """Return secret findings in ``text`` (empty list when the scanner is absent)."""
    try:
        from hermes_cli import secrets_policy

        return list(secrets_policy.scan_text(text, location="migration_sql"))
    except Exception:  # pragma: no cover — secrets_policy import path varies in tests
        return []


def _gate_write(
    cfg: supabase_config.SupabaseConfig,
    action_type: str,
    *,
    summary: str,
    sql: str = "",
    authorization: str = "",
) -> tuple[Optional[str], Any]:
    """Owner-gated verdict for a write. See plugins/vercel/tools.py._gate_write."""
    from hermes_cli.decision_engine import (
        merge_decision_inputs,
        owner_gate_input,
        secret_input,
    )

    findings = _scan_secrets(sql) if sql else []
    verdict = merge_decision_inputs(
        action_type=action_type,
        inputs=[owner_gate_input(True, action=summary), secret_input(findings)],
    )
    redacted = verdict.to_redacted_dict()

    if verdict.is_refuse:
        return _err(
            "refused", verdict.rationale, verdict=redacted, executed=False
        ), verdict
    if not cfg.allow_writes:
        return (
            _err(
                "writes_disabled",
                "supabase.allow_writes is false; refusing to author a migration. "
                "Set supabase.allow_writes: true in ~/.hermes/config.yaml to enable.",
                verdict=redacted,
                executed=False,
            ),
            verdict,
        )
    required = verdict.required_owner_phrase or ""
    if authorization.strip() != required:
        return (
            _json({
                "success": True,
                "executed": False,
                "approval_required": True,
                "verdict": redacted,
                "message": (
                    "Owner authorization required. Re-call this tool with "
                    f"authorization set to exactly: {required!r}"
                ),
            }),
            verdict,
        )
    return None, verdict


def _write_migration(name: str, sql: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_") or "migration"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    out_dir = Path.cwd() / "supabase" / "migrations"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{ts}_{slug}.sql"
    path.write_text(sql if sql.endswith("\n") else sql + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_AUTH_PROP = {
    "type": "string",
    "description": (
        "Owner authorization phrase. Leave empty to preview the decision "
        "verdict; supply the exact required phrase to authorize."
    ),
}

QUERY_SCHEMA: Dict[str, Any] = {
    "name": "supabase_query",
    "description": (
        "Read rows from a Supabase table via PostgREST (read-only). Uses the "
        "anon key unless service-role is explicitly opted in and allowed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "table": {
                "type": "string",
                "description": "Table name (optionally schema.table).",
            },
            "select": {
                "type": "string",
                "description": "PostgREST select list (default '*').",
            },
            "limit": {"type": "integer", "description": f"Max rows (≤{HARD_ROW_CAP})."},
            "use_service_role": {
                "type": "boolean",
                "description": "Use the service-role key (bypasses RLS). Requires supabase.allow_service_role.",
            },
        },
        "required": ["table"],
        "additionalProperties": False,
    },
}

LIST_TABLES_SCHEMA: Dict[str, Any] = {
    "name": "supabase_list_tables",
    "description": "List tables exposed by the project's PostgREST endpoint (read-only).",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

EXECUTE_SQL_SCHEMA: Dict[str, Any] = {
    "name": "supabase_execute_sql",
    "description": (
        "Author a SQL migration file (OWNER-GATED, dry-run by default). When "
        "authorized, writes the SQL to supabase/migrations/<ts>.sql for the "
        "operator to apply with `supabase db push`. Does NOT touch a live DB."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "SQL statement(s) to write into the migration.",
            },
            "name": {
                "type": "string",
                "description": "Short migration name (default 'adhoc').",
            },
            "authorization": _AUTH_PROP,
        },
        "required": ["sql"],
        "additionalProperties": False,
    },
}

APPLY_MIGRATION_SCHEMA: Dict[str, Any] = {
    "name": "supabase_apply_migration",
    "description": (
        "Author a named SQL migration file (OWNER-GATED, dry-run by default). "
        "When authorized, writes supabase/migrations/<ts>_<name>.sql for the "
        "operator to apply with `supabase db push`. Does NOT touch a live DB."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Migration name (e.g. 'add_profiles').",
            },
            "sql": {"type": "string", "description": "Migration SQL."},
            "authorization": _AUTH_PROP,
        },
        "required": ["name", "sql"],
        "additionalProperties": False,
    },
}


# ---------------------------------------------------------------------------
# Read handlers
# ---------------------------------------------------------------------------


def handle_query(args: Dict[str, Any], **_kw) -> str:
    try:
        cfg = _require_enabled()
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    table = args.get("table")
    if not isinstance(table, str) or not table:
        return _err("bad_args", "table is required")
    try:
        supabase_config.validate_table(table)
    except supabase_config.ConfigError as exc:
        return _err("bad_args", str(exc))
    if not cfg.is_table_allowed(table):
        return _err("table_not_allowed", f"{table} is not in supabase.allowed_tables")

    use_service_role = bool(args.get("use_service_role"))
    if use_service_role:
        if not cfg.allow_service_role:
            return _err(
                "service_role_disabled",
                "supabase.allow_service_role is false; refusing to use the service-role key.",
            )
        if not client.has_service_role():
            return _err(
                "no_service_role", "SUPABASE_SERVICE_ROLE_KEY is not configured."
            )

    select = args.get("select")
    limit = int(args.get("limit") or DEFAULT_ROW_CAP)
    res = client.query(
        table,
        select=select if isinstance(select, str) and select else "*",
        limit=limit,
        service_role=use_service_role,
    )
    if not res.get("success"):
        return _json(res)
    rows = res.get("payload")
    rows = rows if isinstance(rows, list) else []
    return _ok(table=table, row_count=len(rows), rows=rows[:HARD_ROW_CAP])


def handle_list_tables(args: Dict[str, Any], **_kw) -> str:
    try:
        _require_enabled()
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    res = client.list_tables()
    if not res.get("success"):
        return _json(res)
    return _ok(tables=res.get("tables") or [])


# ---------------------------------------------------------------------------
# Write handlers (owner-gated; author local migration files only)
# ---------------------------------------------------------------------------


def _validate_sql(args: Dict[str, Any]) -> str:
    sql = args.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        raise _GateFailure(_err("bad_args", "sql is required"))
    if len(sql.encode("utf-8")) > _MAX_SQL_BYTES:
        raise _GateFailure(_err("bad_args", f"sql exceeds {_MAX_SQL_BYTES} bytes"))
    return sql


def handle_execute_sql(args: Dict[str, Any], **_kw) -> str:
    try:
        cfg = _require_enabled()
        sql = _validate_sql(args)
    except _GateFailure as exc:
        return exc.payload_json
    name = args.get("name") if isinstance(args.get("name"), str) else "adhoc"

    stop, verdict = _gate_write(
        cfg,
        "supabase.execute_sql",
        summary=f"author SQL migration '{name}'",
        sql=sql,
        authorization=str(args.get("authorization") or ""),
    )
    if stop is not None:
        return stop
    path = _write_migration(name or "adhoc", sql)
    return _ok(
        executed=True,
        wrote_migration=True,
        applied=False,
        migration_path=str(path),
        verdict=verdict.to_redacted_dict(),
        message="Migration file written. Run `supabase db push` to apply it to the database.",
    )


def handle_apply_migration(args: Dict[str, Any], **_kw) -> str:
    try:
        cfg = _require_enabled()
        sql = _validate_sql(args)
    except _GateFailure as exc:
        return exc.payload_json
    name = args.get("name")
    if not isinstance(name, str) or not name.strip():
        return _err("bad_args", "name is required")

    stop, verdict = _gate_write(
        cfg,
        "supabase.apply_migration",
        summary=f"author migration '{name}'",
        sql=sql,
        authorization=str(args.get("authorization") or ""),
    )
    if stop is not None:
        return stop
    path = _write_migration(name, sql)
    return _ok(
        executed=True,
        wrote_migration=True,
        applied=False,
        migration_path=str(path),
        verdict=verdict.to_redacted_dict(),
        message="Migration file written. Run `supabase db push` to apply it to the database.",
    )


TOOL_REGISTRATIONS = (
    ("supabase_query", QUERY_SCHEMA, handle_query, "🗄️"),
    ("supabase_list_tables", LIST_TABLES_SCHEMA, handle_list_tables, "📚"),
    ("supabase_execute_sql", EXECUTE_SQL_SCHEMA, handle_execute_sql, "🧱"),
    ("supabase_apply_migration", APPLY_MIGRATION_SCHEMA, handle_apply_migration, "🧬"),
)
