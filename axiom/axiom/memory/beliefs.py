"""AGM-style belief revision with entrenchment (no silent overwrite).

Three states only: ACTIVE, SUPERSEDED, RETRACTED. Revision never
deletes — a superseded belief keeps its lineage link to the belief
that replaced it (we deliberately drop the AGM Recovery postulate in
favor of explicit lineage). A new observation that contradicts a
belief entrenched at or above OWNER_GATE raises OwnerRequired: the
machine never silently overwrites what the owner asserted.

Entrenchment scale: 0.25 hearsay, 0.5 default, 0.8 verified,
1.0 owner-asserted.
"""

from __future__ import annotations

import sqlite3
import time

ACTIVE = "ACTIVE"
SUPERSEDED = "SUPERSEDED"
RETRACTED = "RETRACTED"

ENTRENCH_HEARSAY = 0.25
ENTRENCH_DEFAULT = 0.5
ENTRENCH_VERIFIED = 0.8
ENTRENCH_OWNER = 1.0

OWNER_GATE = ENTRENCH_VERIFIED  # contradicting >= this requires the owner


class OwnerRequired(PermissionError):
    """Revision touches an entrenched belief; only the owner may decide."""

    def __init__(self, belief_id: int, statement: str):
        super().__init__(
            f"belief {belief_id} ({statement!r}) is entrenched; "
            "owner decision required"
        )
        self.belief_id = belief_id
        self.statement = statement


class BeliefBase:
    """SQLite-backed AGM belief set with lineage."""

    def __init__(self, path: str = ":memory:"):
        self._db = sqlite3.connect(path, check_same_thread=False)
        if path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS beliefs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                statement TEXT NOT NULL,
                entrenchment REAL NOT NULL,
                status TEXT NOT NULL,
                superseded_by INTEGER,
                created_ts REAL NOT NULL
            )"""
        )
        self._db.commit()

    def assert_belief(
        self, statement: str, entrenchment: float = ENTRENCH_DEFAULT
    ) -> int:
        cur = self._db.execute(
            "INSERT INTO beliefs (statement, entrenchment, status, created_ts) "
            "VALUES (?,?,?,?)",
            (statement, entrenchment, ACTIVE, time.time()),
        )
        self._db.commit()
        return cur.lastrowid

    def get(self, belief_id: int) -> dict:
        row = self._db.execute(
            "SELECT id, statement, entrenchment, status, superseded_by, created_ts "
            "FROM beliefs WHERE id = ?",
            (belief_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"belief {belief_id} not found")
        return {
            "id": row[0], "statement": row[1], "entrenchment": row[2],
            "status": row[3], "superseded_by": row[4], "created_ts": row[5],
        }

    def active(self) -> list[dict]:
        rows = self._db.execute(
            "SELECT id FROM beliefs WHERE status = ?", (ACTIVE,)
        ).fetchall()
        return [self.get(r[0]) for r in rows]

    def revise(
        self,
        statement: str,
        contradicts: int,
        entrenchment: float = ENTRENCH_DEFAULT,
        owner_override: bool = False,
    ) -> int:
        """Replace a contradicted belief, preserving lineage.

        If the contradicted belief is entrenched at or above OWNER_GATE
        and *owner_override* is False, raise OwnerRequired and change
        nothing.
        """
        old = self.get(contradicts)
        if old["status"] != ACTIVE:
            raise ValueError(f"belief {contradicts} is not ACTIVE")
        if old["entrenchment"] >= OWNER_GATE and not owner_override:
            raise OwnerRequired(contradicts, old["statement"])
        new_id = self.assert_belief(statement, entrenchment)
        self._db.execute(
            "UPDATE beliefs SET status = ?, superseded_by = ? WHERE id = ?",
            (SUPERSEDED, new_id, contradicts),
        )
        self._db.commit()
        return new_id

    def retract(self, belief_id: int, owner_override: bool = False) -> None:
        old = self.get(belief_id)
        if old["entrenchment"] >= OWNER_GATE and not owner_override:
            raise OwnerRequired(belief_id, old["statement"])
        self._db.execute(
            "UPDATE beliefs SET status = ? WHERE id = ?", (RETRACTED, belief_id)
        )
        self._db.commit()

    def lineage(self, belief_id: int) -> list[dict]:
        """The chain of beliefs from *belief_id* forward through revisions."""
        chain = [self.get(belief_id)]
        while chain[-1]["superseded_by"] is not None:
            chain.append(self.get(chain[-1]["superseded_by"]))
        return chain
