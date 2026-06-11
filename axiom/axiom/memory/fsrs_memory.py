"""FSRS-backed memory economy (supports I2's feedback loop).

Verifier outcome is the review grade: a memory confirmed by
verification strengthens (Good); one contradicted by reality lapses
(Again) and demotes. Tier promotion is earned by stability:
  working -> session at stability >= 7.0 days
  session -> durable at stability >= 60.0 days
A lapse always demotes to working. Retrievability below 0.7 marks a
memory as cold for retrieval purposes.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone

from fsrs import Card, Rating, Scheduler

TIER_WORKING = "working"
TIER_SESSION = "session"
TIER_DURABLE = "durable"

SESSION_STABILITY_DAYS = 7.0
DURABLE_STABILITY_DAYS = 60.0
COLD_RETRIEVABILITY = 0.7


class MemoryStore:
    """SQLite-backed memory store with an FSRS scheduling economy."""

    def __init__(self, path: str = ":memory:"):
        self._db = sqlite3.connect(path)
        if path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                source_grade TEXT NOT NULL DEFAULT '',
                tier TEXT NOT NULL,
                card TEXT NOT NULL,
                created_ts REAL NOT NULL
            )"""
        )
        self._db.commit()
        self.scheduler = Scheduler()

    # ----------------------------------------------------------------- write
    def observe(self, content: str, source_grade: str = "") -> int:
        """Record a new memory in the working tier."""
        card = Card()
        cur = self._db.execute(
            "INSERT INTO memories (content, source_grade, tier, card, created_ts) "
            "VALUES (?,?,?,?,?)",
            (content, source_grade, TIER_WORKING,
             json.dumps(card.to_dict()), time.time()),
        )
        self._db.commit()
        return cur.lastrowid

    def on_verification(
        self,
        memory_id: int,
        passed: bool,
        review_datetime: datetime | None = None,
    ) -> str:
        """Grade a memory by verifier outcome; returns the new tier."""
        row = self._db.execute(
            "SELECT card, tier FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"memory {memory_id} not found")
        card = Card.from_dict(json.loads(row[0]))
        rating = Rating.Good if passed else Rating.Again
        when = review_datetime or datetime.now(timezone.utc)
        card, _log = self.scheduler.review_card(card, rating, when)

        if not passed:
            tier = TIER_WORKING  # contradiction always demotes
        elif card.stability is not None and card.stability >= DURABLE_STABILITY_DAYS:
            tier = TIER_DURABLE
        elif card.stability is not None and card.stability >= SESSION_STABILITY_DAYS:
            tier = TIER_SESSION
        else:
            tier = TIER_WORKING

        self._db.execute(
            "UPDATE memories SET card = ?, tier = ? WHERE id = ?",
            (json.dumps(card.to_dict()), tier, memory_id),
        )
        self._db.commit()
        return tier

    # ------------------------------------------------------------------ read
    def get(self, memory_id: int) -> dict:
        row = self._db.execute(
            "SELECT id, content, source_grade, tier, card, created_ts "
            "FROM memories WHERE id = ?",
            (memory_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"memory {memory_id} not found")
        return self._row_to_dict(row)

    def all(self) -> list[dict]:
        rows = self._db.execute(
            "SELECT id, content, source_grade, tier, card, created_ts FROM memories"
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def retrievability(
        self, memory_id: int, at: datetime | None = None
    ) -> float:
        card = Card.from_dict(json.loads(
            self._db.execute(
                "SELECT card FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()[0]
        ))
        if card.last_review is None:
            return 1.0  # never reviewed: fresh by definition
        return float(self.scheduler.get_card_retrievability(
            card, at or datetime.now(timezone.utc)
        ))

    def _row_to_dict(self, row) -> dict:
        mid, content, source_grade, tier, card_json, created = row
        return {
            "id": mid,
            "content": content,
            "source_grade": source_grade,
            "tier": tier,
            "card": json.loads(card_json),
            "created_ts": created,
            "retrievability": self.retrievability(mid),
        }
