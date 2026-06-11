"""Append-only, hash-chained, Ed25519-signed event ledger (defends I3).

Every consequential act leaves a signed, chained record. verify_chain()
recomputes every event hash, every link, and every signature — it is
the court of record. Merkle checkpoints over the event hashes give
O(log n) inclusion proofs against a stored root.
"""

from __future__ import annotations

import json
import sqlite3
import time

import blake3
from nacl.signing import SigningKey, VerifyKey

from .canonical import canonical_json

GENESIS_PREV = "0"


def _event_hash(kind: str, payload: dict, prev: str, ts: float) -> str:
    body = canonical_json({"kind": kind, "payload": payload, "prev": prev, "ts": ts})
    return blake3.blake3(body.encode("utf-8")).hexdigest()


def _merkle_parent(left: str, right: str) -> str:
    return blake3.blake3((left + right).encode("utf-8")).hexdigest()


class Ledger:
    """SQLite-backed (WAL) append-only event chain."""

    def __init__(self, path: str = ":memory:", signing_key: SigningKey | None = None):
        self._db = sqlite3.connect(path)
        if path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL,
                prev TEXT NOT NULL,
                hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                signer TEXT NOT NULL,
                compacted INTEGER NOT NULL DEFAULT 0
            )"""
        )
        self._db.commit()
        self.signing_key = signing_key or SigningKey.generate()

    # ------------------------------------------------------------------ append
    def append(self, kind: str, payload: dict) -> str:
        """Append a signed event; returns its hash."""
        prev = self._tip()
        ts = time.time()
        h = _event_hash(kind, payload, prev, ts)
        sig = self.signing_key.sign(h.encode("utf-8")).signature.hex()
        signer = self.signing_key.verify_key.encode().hex()
        self._db.execute(
            "INSERT INTO events (ts, kind, payload, prev, hash, signature, signer) "
            "VALUES (?,?,?,?,?,?,?)",
            (ts, kind, json.dumps(payload, sort_keys=True), prev, h, sig, signer),
        )
        self._db.commit()
        return h

    def _tip(self) -> str:
        row = self._db.execute(
            "SELECT hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else GENESIS_PREV

    # ------------------------------------------------------------------ read
    def events(self, kind: str | None = None) -> list[dict]:
        q = ("SELECT seq, ts, kind, payload, prev, hash, signature, signer, "
             "compacted FROM events")
        params: tuple = ()
        if kind is not None:
            q += " WHERE kind = ?"
            params = (kind,)
        q += " ORDER BY seq"
        return [
            {
                "seq": seq, "ts": ts, "kind": k,
                "payload": json.loads(payload),
                "prev": prev, "hash": h, "signature": sig, "signer": signer,
                "compacted": bool(compacted),
            }
            for seq, ts, k, payload, prev, h, sig, signer, compacted in
            self._db.execute(q, params).fetchall()
        ]

    def count(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    # ------------------------------------------------------------------ verify
    def verify_chain(self) -> bool:
        """Recompute every hash, link, and signature. The court of record.

        Compacted events keep their original hash and signature but a
        summarized payload, so verification degrades gracefully: the
        link and the signature over the hash are still checked.
        """
        prev = GENESIS_PREV
        for ev in self.events():
            if ev["prev"] != prev:
                return False
            if not ev["compacted"]:
                recomputed = _event_hash(
                    ev["kind"], ev["payload"], ev["prev"], ev["ts"]
                )
                if ev["hash"] != recomputed:
                    return False
            try:
                VerifyKey(bytes.fromhex(ev["signer"])).verify(
                    ev["hash"].encode("utf-8"), bytes.fromhex(ev["signature"])
                )
            except Exception:
                return False
            prev = ev["hash"]
        return True

    # ------------------------------------------------------------------ merkle
    @staticmethod
    def _merkle_root(leaves: list[str]) -> str:
        if not leaves:
            return blake3.blake3(b"").hexdigest()
        level = list(leaves)
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])  # duplicate last leaf (Bitcoin-style)
            level = [
                _merkle_parent(level[i], level[i + 1])
                for i in range(0, len(level), 2)
            ]
        return level[0]

    def checkpoint(self) -> dict:
        """Record a Merkle root over all event hashes so far."""
        leaves = [ev["hash"] for ev in self.events() if ev["kind"] != "merkle_checkpoint"]
        root = self._merkle_root(leaves)
        payload = {"root": root, "n_leaves": len(leaves)}
        self.append("merkle_checkpoint", payload)
        return payload

    def compact(self, checkpoint: dict) -> int:
        """Summarize the payloads of events covered by *checkpoint*.

        History stays append-only and tamper-evident: hashes, links,
        and signatures are preserved (so inclusion proofs against the
        stored root still verify); only the payload bodies of covered
        non-checkpoint events are replaced by a summary marker.
        Returns the number of events compacted.
        """
        covered = [
            ev for ev in self.events()
            if ev["kind"] != "merkle_checkpoint" and not ev["compacted"]
        ][: checkpoint["n_leaves"]]
        for ev in covered:
            self._db.execute(
                "UPDATE events SET payload = ?, compacted = 1 WHERE seq = ?",
                (json.dumps({"compacted": True, "kind": ev["kind"]}), ev["seq"]),
            )
        self._db.commit()
        return len(covered)

    def inclusion_proof(self, leaf_hash: str, checkpoint: dict) -> list[tuple[str, str]]:
        """Path of (side, sibling_hash) from *leaf_hash* to the checkpoint root.

        Side is "L" if the sibling is on the left, "R" if on the right.
        """
        leaves = [
            ev["hash"] for ev in self.events() if ev["kind"] != "merkle_checkpoint"
        ][: checkpoint["n_leaves"]]
        if leaf_hash not in leaves:
            raise KeyError(f"event {leaf_hash} not under checkpoint")
        idx = leaves.index(leaf_hash)
        proof: list[tuple[str, str]] = []
        level = list(leaves)
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])
            sibling = idx ^ 1
            side = "L" if sibling < idx else "R"
            proof.append((side, level[sibling]))
            level = [
                _merkle_parent(level[i], level[i + 1])
                for i in range(0, len(level), 2)
            ]
            idx //= 2
        return proof

    @staticmethod
    def verify_inclusion(
        leaf_hash: str, proof: list[tuple[str, str]], root: str
    ) -> bool:
        h = leaf_hash
        for side, sibling in proof:
            h = _merkle_parent(sibling, h) if side == "L" else _merkle_parent(h, sibling)
        return h == root
