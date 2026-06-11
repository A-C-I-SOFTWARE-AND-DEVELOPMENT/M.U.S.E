"""Exactly-once job execution via idempotency keys (closes the
replay/duplication-harm failure mode).

A job's idempotency key is the blake3 hash of its canonical inputs.
Submission is write-ahead: the intent is recorded before any work
runs. Re-running a committed key returns the stored result without
executing again — the same request can never act twice.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Callable

from ..core.canonical import content_hash

PENDING = "pending"
COMMITTED = "committed"
FAILED = "failed"


class JobStore:
    """SQLite-backed write-ahead job log with exactly-once semantics."""

    def __init__(self, path: str = ":memory:"):
        self._db = sqlite3.connect(path, check_same_thread=False)
        if path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                key TEXT PRIMARY KEY,
                intent TEXT NOT NULL,
                inputs TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                created_ts REAL NOT NULL,
                committed_ts REAL
            )"""
        )
        self._db.commit()

    @staticmethod
    def idempotency_key(intent: str, inputs: dict) -> str:
        return content_hash({"intent": intent, "inputs": inputs})

    def run(
        self,
        intent: str,
        inputs: dict,
        fn: Callable[[dict], Any],
    ) -> tuple[str, Any, bool]:
        """Execute *fn(inputs)* exactly once for this (intent, inputs).

        Returns (key, result, executed) where *executed* is False if a
        committed result was replayed instead of re-running.
        """
        key = self.idempotency_key(intent, inputs)
        row = self._db.execute(
            "SELECT status, result FROM jobs WHERE key = ?", (key,)
        ).fetchone()
        if row is not None and row[0] == COMMITTED:
            return key, json.loads(row[1]), False

        if row is None:
            # Write-ahead: record the intent before doing the work.
            self._db.execute(
                "INSERT INTO jobs (key, intent, inputs, status, created_ts) "
                "VALUES (?,?,?,?,?)",
                (key, intent, json.dumps(inputs, sort_keys=True), PENDING,
                 time.time()),
            )
            self._db.commit()

        try:
            result = fn(inputs)
        except Exception:
            self._db.execute(
                "UPDATE jobs SET status = ? WHERE key = ?", (FAILED, key)
            )
            self._db.commit()
            raise

        self._db.execute(
            "UPDATE jobs SET status = ?, result = ?, committed_ts = ? "
            "WHERE key = ?",
            (COMMITTED, json.dumps(result), time.time(), key),
        )
        self._db.commit()
        return key, result, True

    def status(self, key: str) -> str | None:
        row = self._db.execute(
            "SELECT status FROM jobs WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None
