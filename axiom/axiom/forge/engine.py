"""The Forge engine: persistent ratings, real-unit tournaments,
trajectory export (Phase 3; defends I2 against reward hacking over
time, not just within one run).

The hard gate is the Verifier — static checks plus runtime probes.
A cheat that passes every static check dies at the runtime
postcondition, by theorem, before any judge sees it. Soft preference
among verified candidates is op-count: the shorter proof wins.
Verifier-passed trajectories are exported for future distillation;
failures go to the negatives file — the cheat's lineage is never
distilled forward.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..core.canonical import Unit
from ..core.contracts import PostconditionViolation
from ..core.verifier import Attestation, Verifier
from . import ratings
from .ratings import Rating
from .tournament import Candidate, Tournament


class RatingStore:
    """SQLite-persisted Glicko-2 ratings with rating periods.

    A candidate that sits out a period has its RD inflated by the
    empty-period update (Glickman step 6) — uncertainty grows with
    idleness, capped at the default RD.
    """

    def __init__(self, path: str = ":memory:"):
        self._db = sqlite3.connect(path, check_same_thread=False)
        if path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS ratings (
                cid TEXT PRIMARY KEY,
                rating REAL NOT NULL,
                rd REAL NOT NULL,
                vol REAL NOT NULL
            )"""
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        self._db.commit()

    def get(self, cid: str) -> Rating:
        row = self._db.execute(
            "SELECT rating, rd, vol FROM ratings WHERE cid = ?", (cid,)
        ).fetchone()
        if row is None:
            return Rating()
        return Rating(rating=row[0], rd=row[1], vol=row[2])

    def known(self, cid: str) -> bool:
        return self._db.execute(
            "SELECT 1 FROM ratings WHERE cid = ?", (cid,)
        ).fetchone() is not None

    def upsert(self, cid: str, r: Rating) -> None:
        self._db.execute(
            "INSERT INTO ratings (cid, rating, rd, vol) VALUES (?,?,?,?) "
            "ON CONFLICT(cid) DO UPDATE SET rating=excluded.rating, "
            "rd=excluded.rd, vol=excluded.vol",
            (cid, r.rating, r.rd, r.vol),
        )
        self._db.commit()

    def all_cids(self) -> list[str]:
        return [r[0] for r in self._db.execute("SELECT cid FROM ratings")]

    def begin_period(self, active_cids: set[str]) -> None:
        """Start a rating period: idle candidates' RD inflates, capped
        at the default RD (you can't be *more* unknown than new)."""
        for cid in self.all_cids():
            if cid in active_cids:
                continue
            r = self.get(cid)
            inflated = ratings.update(r, [])
            inflated.rd = min(inflated.rd, ratings.DEFAULT_RD)
            self.upsert(cid, inflated)


class ForgeEngine:
    """Tournaments over real AXIOM units with persistent state."""

    def __init__(self, verifier: Verifier, ratings_path: str = ":memory:",
                 data_dir: str = "data"):
        self.verifier = verifier
        self.ratings = RatingStore(ratings_path)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ hard gate
    def _gate(self, cid: str, unit: Unit, probes: list[dict]) -> tuple[bool, str, str]:
        """Static verification plus runtime probes. Returns
        (passed, reason, unit_hash)."""
        outcome = self.verifier.verify(unit)
        if not isinstance(outcome, Attestation):
            return False, f"static: {list(outcome.errors)}", ""
        for probe in probes:
            try:
                self.verifier.run(outcome.unit_hash, probe)
            except PostconditionViolation as e:
                return False, f"runtime postcondition: {e.clause}", outcome.unit_hash
        return True, "", outcome.unit_hash

    # ----------------------------------------------------------- tournament
    def run_spec_tournament(
        self, units: dict[str, Unit], probes: list[dict]
    ) -> dict:
        """Gate every variant, duel the survivors (shorter verified unit
        wins), persist ratings, ledger the champion, export trajectories."""
        ledger = self.verifier.ledger
        self.ratings.begin_period(active_cids=set(units))

        t = Tournament(ledger)
        hashes: dict[str, str] = {}
        reasons: dict[str, str] = {}
        for cid, unit in units.items():
            cand = Candidate(cid=cid, payload={"ops": len(unit.body)})
            cand.rating = self.ratings.get(cid)
            t.add(cand)

        gate_results: dict[str, bool] = {}
        for cid, unit in units.items():
            passed, reason, h = self._gate(cid, unit, probes)
            gate_results[cid] = passed
            hashes[cid] = h
            reasons[cid] = reason

        failed = t.gate(lambda c: gate_results[c.cid], reasons=reasons)

        survivors = [c for c in t.candidates.values() if c.gate_passed]
        try:
            # Round-robin duels; the shorter verified unit wins.
            for i, a in enumerate(survivors):
                for b in survivors[i + 1:]:
                    winner = a.cid if a.payload["ops"] <= b.payload["ops"] else b.cid
                    t.duel(a.cid, b.cid, winner=winner)
        finally:
            # Persist whatever ratings were earned, even on a halt.
            for cand in t.candidates.values():
                self.ratings.upsert(cand.cid, cand.rating)

        champion = t.champion()
        ledger.append(
            "forge_champion",
            {"cid": champion.cid, "unit_hash": hashes[champion.cid],
             "rating": champion.rating.rating},
        )
        self._export(units, gate_results, hashes, t)
        return {
            "champion": champion.cid,
            "gate_failed": failed,
            "ratings": {c.cid: c.rating.rating for c in t.candidates.values()},
        }

    # --------------------------------------------------------------- export
    def _export(self, units, gate_results, hashes, tournament) -> None:
        traj = self.data_dir / "trajectories.jsonl"
        negs = self.data_dir / "negatives.jsonl"
        with traj.open("a") as tf, negs.open("a") as nf:
            for cid, unit in units.items():
                rec = {
                    "cid": cid,
                    "unit_hash": hashes[cid],
                    "gate_passed": gate_results[cid],
                    "ops": len(unit.body),
                    "rating": tournament.candidates[cid].rating.rating,
                    "form": unit.full_form(),
                }
                (tf if gate_results[cid] else nf).write(
                    json.dumps(rec, sort_keys=True) + "\n"
                )
