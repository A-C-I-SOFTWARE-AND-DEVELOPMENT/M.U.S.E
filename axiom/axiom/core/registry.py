"""Content-addressed unit registry: resolve-or-fail (defends I1).

Identity is the blake3 hash of canonical form. A reference that does
not resolve is a hard error — never a guess, never a fuzzy match.
Registrations are Ed25519-signed. History is immutable: a registered
hash is never deleted; deprecation only annotates it with a successor.
"""

from __future__ import annotations

import sqlite3
import time

from nacl.signing import SigningKey, VerifyKey

from .canonical import Unit


class UnresolvedReferenceError(KeyError):
    """Raised when a unit hash does not resolve. Never caught silently."""

    def __init__(self, unit_hash: str):
        super().__init__(unit_hash)
        self.unit_hash = unit_hash

    def __str__(self) -> str:
        return f"unresolved reference: {self.unit_hash}"


class Registry:
    """SQLite-backed (WAL) content store for verified units."""

    def __init__(self, path: str = ":memory:"):
        self._db = sqlite3.connect(path, check_same_thread=False)
        if path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS units (
                unit_hash TEXT PRIMARY KEY,
                canonical TEXT NOT NULL,
                name TEXT NOT NULL,
                doc TEXT NOT NULL,
                form TEXT NOT NULL,
                signature TEXT NOT NULL,
                signer TEXT NOT NULL,
                created_ts REAL NOT NULL,
                deprecated_by TEXT
            )"""
        )
        self._db.commit()

    def register(self, unit: Unit, signing_key: SigningKey) -> str:
        """Sign and store *unit*; returns its content hash (idempotent)."""
        import json

        h = unit.unit_hash()
        canonical = unit.canonical()
        sig = signing_key.sign(canonical.encode("utf-8")).signature.hex()
        signer = signing_key.verify_key.encode().hex()
        self._db.execute(
            "INSERT OR IGNORE INTO units "
            "(unit_hash, canonical, name, doc, form, signature, signer, created_ts) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (h, canonical, unit.name, unit.doc, json.dumps(unit.full_form()),
             sig, signer, time.time()),
        )
        self._db.commit()
        return h

    def resolve(self, unit_hash: str) -> Unit:
        """Return the unit for *unit_hash* or raise UnresolvedReferenceError."""
        import json

        row = self._db.execute(
            "SELECT form FROM units WHERE unit_hash = ?", (unit_hash,)
        ).fetchone()
        if row is None:
            raise UnresolvedReferenceError(unit_hash)
        return Unit.from_form(json.loads(row[0]))

    def exists(self, unit_hash: str) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM units WHERE unit_hash = ?", (unit_hash,)
        ).fetchone()
        return row is not None

    def verify_signature(self, unit_hash: str) -> bool:
        """Re-verify the stored registration signature."""
        row = self._db.execute(
            "SELECT canonical, signature, signer FROM units WHERE unit_hash = ?",
            (unit_hash,),
        ).fetchone()
        if row is None:
            raise UnresolvedReferenceError(unit_hash)
        canonical, sig, signer = row
        try:
            VerifyKey(bytes.fromhex(signer)).verify(
                canonical.encode("utf-8"), bytes.fromhex(sig)
            )
            return True
        except Exception:
            return False

    def search(self, name_substr: str) -> list[dict]:
        """Search by name metadata. Names are hints; hashes are truth."""
        rows = self._db.execute(
            "SELECT unit_hash, name, doc, deprecated_by FROM units WHERE name LIKE ?",
            (f"%{name_substr}%",),
        ).fetchall()
        return [
            {"unit_hash": h, "name": n, "doc": d, "deprecated_by": dep}
            for h, n, d, dep in rows
        ]

    def deprecate(self, unit_hash: str, successor_hash: str) -> None:
        """Annotate *unit_hash* with a successor. The old hash still
        resolves — history is immutable — but the verifier will warn."""
        if not self.exists(unit_hash):
            raise UnresolvedReferenceError(unit_hash)
        if not self.exists(successor_hash):
            raise UnresolvedReferenceError(successor_hash)
        self._db.execute(
            "UPDATE units SET deprecated_by = ? WHERE unit_hash = ?",
            (successor_hash, unit_hash),
        )
        self._db.commit()

    def deprecated_by(self, unit_hash: str) -> str | None:
        row = self._db.execute(
            "SELECT deprecated_by FROM units WHERE unit_hash = ?", (unit_hash,)
        ).fetchone()
        if row is None:
            raise UnresolvedReferenceError(unit_hash)
        return row[0]
