"""SQLite snapshot store for the research fabric — an INDEX, not the truth.

Tamper-evidence lives in the existing hash-chained
:class:`~hermes_cli.jarvis_prime.guardrail_evidence.GuardrailLedger`. This store
is a queryable index over runs/champions/candidates whose rows carry the ledger
``record_hash`` they correspond to, so we never fork a second, untested crypto
scheme (see plan: "SQLite is an index only").

Each row additionally keeps an internal ``row_hash`` chained off the previous
row (reusing ``canonical_json``/``sha256_hex`` from the guardrail module) so a
``verify_chain`` over the DB alone can detect local tampering even offline.
"""

from __future__ import annotations

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


__all__ = ["SnapshotStore", "StoreChainDiagnostics"]
