"""Snapshot store for the research fabric — an INDEX, not the truth.

Tamper-evidence lives in the existing hash-chained
:class:`~hermes_cli.jarvis_prime.guardrail_evidence.GuardrailLedger`. This store
is a queryable index over runs/champions/candidates whose rows carry the ledger
``record_hash`` they correspond to, so we never fork a second, untested crypto
scheme (see plan: "store is an index only").

Backends:
  * SQLite (default, local file — offline/dev).
  * Supabase Postgres (production) — selected by setting
    RESEARCH_FABRIC_STORE=postgres plus SUPABASE_DB_URL (or
    SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY via the PostgREST fallback is
    NOT supported; use the direct connection string). Schema lives in
    supabase/migrations/202607200001_research_fabric_snapshots.sql.

Both backends keep the internal ``row_hash`` chained off the previous row
(reusing ``canonical_json``/``sha256_hex`` from the guardrail module) so a
``verify_chain`` over the store alone can detect tampering.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import (
    GENESIS_HASH,
    canonical_json,
    sha256_hex,
)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StoreChainDiagnostics:
    ok: bool
    length: int
    head_hash: Optional[str] = None
    broken_at: Optional[int] = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "length": self.length,
            "head_hash": self.head_hash,
            "broken_at": self.broken_at,
            "reason": self.reason,
        }


class SnapshotStore:
    """A small SQLite index of research-fabric activity."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                subject TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                ledger_record_hash TEXT NOT NULL DEFAULT '',
                prev_row_hash TEXT NOT NULL,
                row_hash TEXT NOT NULL UNIQUE
            );
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- writes -----------------------------------------------------------

    def _head_row_hash(self) -> str:
        row = self.conn.execute(
            "SELECT row_hash FROM snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["row_hash"] if row else GENESIS_HASH

    def record_snapshot(
        self,
        kind: str,
        subject: str,
        payload: Mapping[str, Any],
        *,
        ledger_record_hash: str = "",
    ) -> str:
        """Append one indexed snapshot row; return its ``row_hash``."""

        created_at = _utc_iso()
        payload_json = canonical_json(dict(payload))
        prev = self._head_row_hash()
        row_hash = sha256_hex(
            canonical_json(
                {
                    "created_at": created_at,
                    "kind": kind,
                    "subject": subject,
                    "payload_json": payload_json,
                    "ledger_record_hash": ledger_record_hash,
                    "prev_row_hash": prev,
                }
            )
        )
        self.conn.execute(
            "INSERT INTO snapshots "
            "(created_at, kind, subject, payload_json, ledger_record_hash, "
            " prev_row_hash, row_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (created_at, kind, subject, payload_json, ledger_record_hash, prev, row_hash),
        )
        self.conn.commit()
        return row_hash

    # -- reads ------------------------------------------------------------

    def list_snapshots(self, kind: Optional[str] = None) -> list[dict[str, Any]]:
        if kind is None:
            rows = self.conn.execute(
                "SELECT * FROM snapshots ORDER BY id ASC"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM snapshots WHERE kind = ? ORDER BY id ASC", (kind,)
            ).fetchall()
        return [dict(r) for r in rows]

    def latest(self, kind: str) -> Optional[dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM snapshots WHERE kind = ? ORDER BY id DESC LIMIT 1",
            (kind,),
        ).fetchone()
        return dict(row) if row else None

    # -- integrity --------------------------------------------------------

    def verify_chain(self) -> StoreChainDiagnostics:
        rows = self.conn.execute(
            "SELECT created_at, kind, subject, payload_json, ledger_record_hash, "
            "prev_row_hash, row_hash FROM snapshots ORDER BY id ASC"
        ).fetchall()
        prev = GENESIS_HASH
        for idx, r in enumerate(rows):
            expected = sha256_hex(
                canonical_json(
                    {
                        "created_at": r["created_at"],
                        "kind": r["kind"],
                        "subject": r["subject"],
                        "payload_json": r["payload_json"],
                        "ledger_record_hash": r["ledger_record_hash"],
                        "prev_row_hash": r["prev_row_hash"],
                    }
                )
            )
            if r["row_hash"] != expected:
                return StoreChainDiagnostics(
                    ok=False, length=len(rows), broken_at=idx,
                    reason=f"row_hash mismatch at index {idx}",
                )
            if r["prev_row_hash"] != prev:
                return StoreChainDiagnostics(
                    ok=False, length=len(rows), broken_at=idx,
                    reason=f"broken link at index {idx}",
                )
            prev = r["row_hash"]
        return StoreChainDiagnostics(
            ok=True,
            length=len(rows),
            head_hash=rows[-1]["row_hash"] if rows else None,
            reason="chain intact" if rows else "empty store",
        )


# --------------------------------------------------------------------------- #
# Supabase Postgres backend
# --------------------------------------------------------------------------- #

class PgSnapshotStore:
    """Supabase Postgres index of research-fabric activity.

    Same contract as :class:`SnapshotStore`; rows land in
    ``public.research_fabric_snapshots`` (see
    supabase/migrations/202607200001_research_fabric_snapshots.sql).
    Connects with the service-role connection string from ``SUPABASE_DB_URL``
    — RLS is enabled with no policies, so only the service role can
    read/write.
    """

    TABLE = "public.research_fabric_snapshots"

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg  # psycopg 3
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "pg backend requires psycopg: pip install 'psycopg[binary]'"
            ) from exc
        self._psycopg = psycopg
        self.conn = psycopg.connect(dsn, autocommit=True)

    def close(self) -> None:
        self.conn.close()

    # -- writes -----------------------------------------------------------

    def _head_row_hash(self) -> str:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT row_hash FROM {self.TABLE} ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
        return row[0] if row else GENESIS_HASH

    def record_snapshot(
        self,
        kind: str,
        subject: str,
        payload: Mapping[str, Any],
        *,
        ledger_record_hash: str = "",
    ) -> str:
        """Append one indexed snapshot row; return its ``row_hash``."""

        created_at = _utc_iso()
        payload_json = canonical_json(dict(payload))
        prev = self._head_row_hash()
        row_hash = sha256_hex(
            canonical_json(
                {
                    "created_at": created_at,
                    "kind": kind,
                    "subject": subject,
                    "payload_json": payload_json,
                    "ledger_record_hash": ledger_record_hash,
                    "prev_row_hash": prev,
                }
            )
        )
        with self.conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {self.TABLE} "
                "(created_at, kind, subject, payload, ledger_record_hash, "
                " prev_row_hash, row_hash) "
                "VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)",
                (created_at, kind, subject, payload_json, ledger_record_hash, prev, row_hash),
            )
        return row_hash

    # -- reads ------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: tuple) -> dict[str, Any]:
        (rid, created_at, kind, subject, payload, ledger_record_hash,
         prev_row_hash, row_hash) = row
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
        # Keep the historical payload_json TEXT field so hashing semantics
        # match the SQLite backend exactly.
        payload_json = payload if isinstance(payload, str) else canonical_json(payload)
        return {
            "id": rid,
            "created_at": created_at,
            "kind": kind,
            "subject": subject,
            "payload_json": payload_json,
            "ledger_record_hash": ledger_record_hash,
            "prev_row_hash": prev_row_hash,
            "row_hash": row_hash,
        }

    _COLS = "id, created_at, kind, subject, payload, ledger_record_hash, prev_row_hash, row_hash"

    def list_snapshots(self, kind: Optional[str] = None) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            if kind is None:
                cur.execute(f"SELECT {self._COLS} FROM {self.TABLE} ORDER BY id ASC")
            else:
                cur.execute(
                    f"SELECT {self._COLS} FROM {self.TABLE} WHERE kind = %s ORDER BY id ASC",
                    (kind,),
                )
            return [self._row_to_dict(r) for r in cur.fetchall()]

    def latest(self, kind: str) -> Optional[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS} FROM {self.TABLE} WHERE kind = %s "
                "ORDER BY id DESC LIMIT 1",
                (kind,),
            )
            row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    # -- integrity --------------------------------------------------------

    def verify_chain(self) -> StoreChainDiagnostics:
        rows = self.list_snapshots()
        prev = GENESIS_HASH
        for idx, r in enumerate(rows):
            expected = sha256_hex(
                canonical_json(
                    {
                        "created_at": r["created_at"],
                        "kind": r["kind"],
                        "subject": r["subject"],
                        "payload_json": r["payload_json"],
                        "ledger_record_hash": r["ledger_record_hash"],
                        "prev_row_hash": r["prev_row_hash"],
                    }
                )
            )
            if r["row_hash"] != expected:
                return StoreChainDiagnostics(
                    ok=False, length=len(rows), broken_at=idx,
                    reason=f"row_hash mismatch at index {idx}",
                )
            if r["prev_row_hash"] != prev:
                return StoreChainDiagnostics(
                    ok=False, length=len(rows), broken_at=idx,
                    reason=f"broken link at index {idx}",
                )
            prev = r["row_hash"]
        return StoreChainDiagnostics(
            ok=True,
            length=len(rows),
            head_hash=rows[-1]["row_hash"] if rows else None,
            reason="chain intact" if rows else "empty store",
        )


# --------------------------------------------------------------------------- #
# Backend selection
# --------------------------------------------------------------------------- #

def open_store(db_path: Optional[Path] = None):
    """Open the configured snapshot store.

    ``RESEARCH_FABRIC_STORE=postgres`` selects the Supabase backend (requires
    ``SUPABASE_DB_URL``); anything else falls back to local SQLite at
    ``db_path`` (default: .hermes/research_fabric/snapshots.db).
    """

    backend = os.environ.get("RESEARCH_FABRIC_STORE", "sqlite").strip().lower()
    if backend in {"postgres", "pg", "supabase"}:
        dsn = os.environ.get("SUPABASE_DB_URL", "").strip()
        if not dsn:
            raise RuntimeError(
                "RESEARCH_FABRIC_STORE=postgres requires SUPABASE_DB_URL "
                "(service-role Postgres connection string)"
            )
        return PgSnapshotStore(dsn)
    if db_path is None:
        db_path = Path(".hermes") / "research_fabric" / "snapshots.db"
    return SnapshotStore(db_path)


__all__ = ["SnapshotStore", "PgSnapshotStore", "StoreChainDiagnostics", "open_store"]
