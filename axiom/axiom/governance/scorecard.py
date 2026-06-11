"""The trust scorecard: trust is measured from outside, never
self-reported (Phase 6.1; Lee & See 2004 — trust should track
demonstrated performance).

Three measurements per capability:
  - prediction accuracy: was the claim right?
  - promise-keeping: jobs committed vs jobs claimed;
  - calibration: Brier score over self-reported confidence — an
    overconfident system is measurably untrustworthy even when it is
    often right.
"""

from __future__ import annotations

import sqlite3
import time


class TrustScorecard:
    """SQLite-backed per-capability trust measurements."""

    def __init__(self, path: str = ":memory:"):
        self._db = sqlite3.connect(path, check_same_thread=False)
        if path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capability TEXT NOT NULL,
                confidence REAL NOT NULL,
                outcome INTEGER NOT NULL,
                ts REAL NOT NULL
            )"""
        )
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS promises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capability TEXT NOT NULL,
                kept INTEGER NOT NULL,
                ts REAL NOT NULL
            )"""
        )
        self._db.commit()

    def record_prediction(
        self, capability: str, confidence: float, outcome: bool
    ) -> None:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        self._db.execute(
            "INSERT INTO predictions (capability, confidence, outcome, ts) "
            "VALUES (?,?,?,?)",
            (capability, confidence, int(outcome), time.time()),
        )
        self._db.commit()

    def record_promise(self, capability: str, kept: bool) -> None:
        self._db.execute(
            "INSERT INTO promises (capability, kept, ts) VALUES (?,?,?)",
            (capability, int(kept), time.time()),
        )
        self._db.commit()

    def stats(self, capability: str, window: int | None = None) -> dict:
        """Rolling-window stats. *window* limits to the N most recent
        predictions/promises (None = all)."""
        limit = f" ORDER BY id DESC LIMIT {int(window)}" if window else ""
        preds = self._db.execute(
            "SELECT confidence, outcome FROM predictions WHERE capability = ?"
            + limit,
            (capability,),
        ).fetchall()
        proms = self._db.execute(
            "SELECT kept FROM promises WHERE capability = ?" + limit,
            (capability,),
        ).fetchall()

        n = len(preds)
        if n:
            accuracy = sum(
                1 for conf, out in preds if (conf >= 0.5) == bool(out)
            ) / n
            brier = sum((conf - out) ** 2 for conf, out in preds) / n
        else:
            accuracy = 0.0
            brier = 1.0  # no evidence = worst assumption
        promise_rate = (
            sum(k for (k,) in proms) / len(proms) if proms else 0.0
        )
        return {
            "n_predictions": n,
            "n_promises": len(proms),
            "accuracy": accuracy,
            "brier": brier,
            "promise_rate": promise_rate,
        }
