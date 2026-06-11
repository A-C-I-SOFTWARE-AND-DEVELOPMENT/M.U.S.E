"""Optional DuckDB/Parquet analytics over the learning dataset.

The learning dataset is durable JSONL (see :mod:`learning_dataset`). This
module is a thin, fully-optional analytics tier on top of it: it flattens the
approved candidates into columnar rows and writes a Parquet file via DuckDB's
own writer (no pyarrow needed), and runs read-only DuckDB SQL over an exported
Parquet file.

DuckDB is lazy-installed (``analytics.duckdb``) at first use; nothing here is
imported unless the user runs the analytics commands, so the base install and
the JSONL pipeline are unaffected.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from hermes_cli.jarvis_prime.learning_dataset import CandidateStatus, DatasetStore

if TYPE_CHECKING:  # pragma: no cover - typing only
    from hermes_cli.jarvis_prime.learning_dataset import DatasetCandidate


def _ensure_duckdb():
    """Import duckdb, lazy-installing it the first time if needed."""
    from tools.lazy_deps import ensure

    ensure("analytics.duckdb", prompt=False)
    import duckdb  # noqa: WPS433 (intentional lazy import)  # ty: ignore[unresolved-import]  # optional dep

    return duckdb


def _flatten(store: DatasetStore, *, status: Optional[CandidateStatus] = None) -> list[dict]:
    """Flatten candidates into one columnar row each.

    ``content`` is kept as a JSON string column so the schema stays flat and
    stable across heterogeneous trace types while remaining queryable via
    DuckDB's ``json_extract``.
    """
    rows: list[dict] = []
    candidates: list["DatasetCandidate"] = store.entries(status=status)
    for c in candidates:
        q = c.quality.to_dict()
        p = c.provenance.to_dict()
        rows.append(
            {
                "id": c.id,
                "trace_type": c.trace_type.value,
                "status": c.status.value,
                "labels": ",".join(c.labels),
                "task_key": c.task_key,
                "created_at": c.created_at,
                "resolved_at": c.resolved_at,
                "source_kind": p.get("source_kind"),
                "source_uri": p.get("source_uri"),
                "job_id": p.get("job_id"),
                "trust": p.get("trust"),
                "citations": ",".join(p.get("citations") or []),  # ty: ignore[no-matching-overload]  # citations is list[str]
                "tests_passed": bool(q.get("tests_passed")),
                "citations_verified": bool(q.get("citations_verified")),
                "owner_approved": bool(q.get("owner_approved")),
                "reviewer_passed": bool(q.get("reviewer_passed")),
                "rollback_available": bool(q.get("rollback_available")),
                "content_json": json.dumps(c.content, ensure_ascii=False),
            }
        )
    return rows


# Stable column order for the Parquet schema (also used to build an empty
# typed table when there are no rows, so downstream queries never see a
# missing-table error).
_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "VARCHAR"),
    ("trace_type", "VARCHAR"),
    ("status", "VARCHAR"),
    ("labels", "VARCHAR"),
    ("task_key", "VARCHAR"),
    ("created_at", "VARCHAR"),
    ("resolved_at", "VARCHAR"),
    ("source_kind", "VARCHAR"),
    ("source_uri", "VARCHAR"),
    ("job_id", "VARCHAR"),
    ("trust", "VARCHAR"),
    ("citations", "VARCHAR"),
    ("tests_passed", "BOOLEAN"),
    ("citations_verified", "BOOLEAN"),
    ("owner_approved", "BOOLEAN"),
    ("reviewer_passed", "BOOLEAN"),
    ("rollback_available", "BOOLEAN"),
    ("content_json", "VARCHAR"),
)


def export_parquet(
    store: DatasetStore,
    out_path: "Path | str",
    *,
    status: Optional[CandidateStatus] = CandidateStatus.APPROVED,
) -> int:
    """Write the (optionally status-filtered) candidates to a Parquet file.

    Defaults to APPROVED candidates only — matching the JSONL export's
    owner-approval contract. Pass ``status=None`` to export every candidate.
    Returns the number of rows written.
    """
    duckdb = _ensure_duckdb()
    rows = _flatten(store, status=status)
    out_path = str(out_path)

    con = duckdb.connect()
    try:
        col_defs = ", ".join(f'"{name}" {sqltype}' for name, sqltype in _COLUMNS)
        con.execute(f"CREATE TABLE rows ({col_defs})")
        if rows:
            col_names = [name for name, _ in _COLUMNS]
            placeholders = ", ".join(["?"] * len(col_names))
            con.executemany(
                f"INSERT INTO rows VALUES ({placeholders})",
                [[r.get(name) for name in col_names] for r in rows],
            )
        con.execute(
            f"COPY (SELECT * FROM rows) TO '{_sql_literal(out_path)}' (FORMAT PARQUET)"
        )
    finally:
        con.close()
    return len(rows)


def _sql_literal(path: "str | Path") -> str:
    """Escape a filesystem path for embedding as a single-quoted SQL literal.

    DuckDB rejects bound parameters inside DDL like ``CREATE VIEW ...
    read_parquet(?)`` and ``COPY ... TO ?``, so paths must be inlined. Doubling
    single quotes is the standard, injection-safe SQL-literal escape.
    """
    return str(path).replace("'", "''")


def query_dataset(sql: str, parquet_path: "Path | str") -> list[dict]:
    """Run read-only DuckDB SQL against an exported Parquet file.

    The Parquet file is exposed as the view ``dataset``. Returns a list of
    row dicts. Intended for analytics over your own approved traces, e.g.::

        SELECT trace_type, count(*) FROM dataset GROUP BY 1
    """
    duckdb = _ensure_duckdb()
    con = duckdb.connect()
    try:
        con.execute(
            f"CREATE VIEW dataset AS SELECT * FROM read_parquet('{_sql_literal(parquet_path)}')"
        )
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        con.close()
