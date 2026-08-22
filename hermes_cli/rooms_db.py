"""Per-profile Rooms store — named, ordered rosters the user keeps around.

A **Room** is a human-named group: a name plus an ordered list of member ids.
It is a bookkeeping surface, not a dispatcher — the store records rooms and the
TUI's ``/rooms`` panel creates, renames, re-crews and deletes them.

**Member ids are opaque to this store.** It strips, de-duplicates and orders
them and does nothing else, deliberately: this repository has no single roster
that a "member" must come from, and inventing one here would bake a taxonomy
into a store that no caller can enforce. When something eventually *routes* to
a room, that caller owns the validation — not this file.

Scope: **per-profile**, at ``$HERMES_HOME/rooms.db`` (resolved via
``get_hermes_home()``), mirroring sessions / config / cron / projects rather
than kanban's root-anchored board DB. Two profiles therefore keep two
independent sets of rooms.

Connection handling (WAL with a DELETE fallback, per-path init cache,
``connect_closing``, ``write_txn`` around every write) mirrors
:mod:`hermes_cli.projects_db`, its structural twin. There are no migrations
yet — v1 is the only schema that has ever shipped — and when one is needed it
goes through ``sqlite_util.add_column_if_missing`` like the twin's, so opening
an old DB stays safe.
"""

from __future__ import annotations

import contextlib
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from hermes_cli.sqlite_util import write_txn
from hermes_constants import get_hermes_home

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def rooms_db_path() -> Path:
    """The per-profile rooms DB path (``$HERMES_HOME/rooms.db``).

    Profile-aware: ``get_hermes_home()`` already points at the active profile's
    home. Tests pass an explicit ``db_path`` to :func:`connect`.
    """
    return get_hermes_home() / "rooms.db"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rooms (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS room_members (
    room_id    TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    member_id  TEXT NOT NULL,
    position   INTEGER NOT NULL,
    PRIMARY KEY (room_id, member_id)
);

CREATE INDEX IF NOT EXISTS idx_room_members_room
    ON room_members(room_id, position);
"""


# ---------------------------------------------------------------------------
# Id + value helpers
# ---------------------------------------------------------------------------


def _new_room_id() -> str:
    return "room_" + secrets.token_hex(4)


def _now() -> int:
    return int(time.time())


def normalize_name(name: str) -> str:
    """Trim a room name; raise when nothing is left.

    Rejecting rather than defaulting is the point: a room called "" is
    unpickable in every list that renders it, and a silent ``"Untitled"``
    hides the client bug that produced it.
    """
    clean = str(name or "").strip()
    if not clean:
        raise ValueError("room name must not be empty")
    return clean


def normalize_member_ids(values: Optional[Iterable[str]]) -> List[str]:
    """Strip, drop blanks, de-duplicate — preserving first-seen order.

    Order is data here (it is the order the panel shows the roster in), so
    de-duplication keeps the FIRST occurrence rather than the last.
    """
    out: List[str] = []
    seen: set[str] = set()
    for value in values or ():
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_INITIALIZED_PATHS: set[str] = set()


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open (and initialize if needed) the per-profile rooms DB.

    WAL with DELETE fallback for network filesystems (shared helper from
    ``hermes_state``). Schema init is idempotent (``CREATE TABLE IF NOT
    EXISTS``) and cached per-path per-process, exactly like ``projects_db``.
    """
    path = db_path if db_path is not None else rooms_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = str(path.resolve())
    conn = sqlite3.connect(str(path))
    try:
        conn.row_factory = sqlite3.Row
        from hermes_state import apply_wal_with_fallback

        apply_wal_with_fallback(conn, db_label="rooms.db")
        # Load-bearing, not decoration: room_members rows are reaped by the
        # ON DELETE CASCADE, which SQLite ignores unless this is on. It is a
        # per-CONNECTION pragma, so every open must set it.
        conn.execute("PRAGMA foreign_keys=ON")
        if resolved not in _INITIALIZED_PATHS:
            conn.executescript(SCHEMA_SQL)
            _INITIALIZED_PATHS.add(resolved)
    except Exception:
        conn.close()
        raise
    return conn


@contextlib.contextmanager
def connect_closing(db_path: Optional[Path] = None):
    """Open a rooms DB connection and guarantee it is closed on exit.

    sqlite3's connection context manager only commits/rollbacks; it does NOT
    close the file descriptor. The gateway opens one connection per RPC call,
    so without this the descriptors to ``rooms.db`` would accumulate for the
    life of the process. Mirrors ``projects_db.connect_closing``.
    """
    conn = connect(db_path=db_path)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class Room:
    """A named, ordered roster."""

    id: str
    name: str
    created_at: int
    updated_at: int
    member_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """The wire shape the ``rooms.*`` RPC methods return.

        ``member_ids`` is copied: the gateway hands this dict straight to the
        JSON encoder, and a shared list would let a caller's mutation reach
        back into the Room it came from.
        """
        return {
            "id": self.id,
            "name": self.name,
            "memberIds": list(self.member_ids),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


def _load_members(conn: sqlite3.Connection, room_id: str) -> List[str]:
    rows = conn.execute(
        "SELECT member_id FROM room_members WHERE room_id = ? "
        "ORDER BY position ASC, member_id ASC",
        (room_id,),
    ).fetchall()
    return [r["member_id"] for r in rows]


def _room_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> Room:
    return Room(
        id=row["id"],
        name=row["name"],
        created_at=int(row["created_at"] or 0),
        updated_at=int(row["updated_at"] or 0),
        member_ids=_load_members(conn, row["id"]),
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def _write_members_locked(
    conn: sqlite3.Connection, room_id: str, member_ids: Sequence[str]
) -> None:
    """Replace a room's roster wholesale (caller already holds a write txn).

    Wholesale, not a diff: the client owns the full roster, and merging would
    silently keep members the user just removed.
    """
    conn.execute("DELETE FROM room_members WHERE room_id = ?", (room_id,))
    conn.executemany(
        "INSERT INTO room_members (room_id, member_id, position) VALUES (?, ?, ?)",
        [(room_id, mid, pos) for pos, mid in enumerate(member_ids)],
    )


def create_room(
    conn: sqlite3.Connection,
    *,
    name: str,
    member_ids: Optional[Iterable[str]] = None,
) -> Room:
    """Create a room and return it. Raises ``ValueError`` on a blank name."""
    clean_name = normalize_name(name)
    members = normalize_member_ids(member_ids)
    rid = _new_room_id()
    now = _now()

    with write_txn(conn):
        conn.execute(
            "INSERT INTO rooms (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (rid, clean_name, now, now),
        )
        _write_members_locked(conn, rid, members)

    return Room(
        id=rid, name=clean_name, created_at=now, updated_at=now, member_ids=members
    )


def update_room(
    conn: sqlite3.Connection,
    room_id: str,
    *,
    name: Optional[str] = None,
    member_ids: Optional[Iterable[str]] = None,
) -> Optional[Room]:
    """Patch a room. ``None`` leaves a field untouched; returns None if unknown.

    Passing an empty ``member_ids`` sequence CLEARS the roster — that is the
    difference between ``[]`` and ``None`` here, and it is how the panel empties
    a room. A blank ``name`` raises rather than clearing, since a nameless room
    cannot be picked out of the list again.

    Returning ``None`` for an unknown id rather than creating one is deliberate:
    the panel only ever sends ids it read from ``list_rooms``, so an unknown id
    means the room was deleted underneath it — resurrecting it as a fresh empty
    room would be the wrong answer to a lost race.
    """
    row = conn.execute("SELECT id FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if row is None:
        return None

    clean_name = normalize_name(name) if name is not None else None
    members = normalize_member_ids(member_ids) if member_ids is not None else None
    now = _now()

    with write_txn(conn):
        if clean_name is not None:
            conn.execute(
                "UPDATE rooms SET name = ?, updated_at = ? WHERE id = ?",
                (clean_name, now, room_id),
            )
        else:
            conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now, room_id))
        if members is not None:
            _write_members_locked(conn, room_id, members)

    return get_room(conn, room_id)


def list_rooms(conn: sqlite3.Connection) -> List[Room]:
    """Every room, most recently touched first, name as the tiebreak.

    Rooms written in the same second would otherwise come back in an order that
    depends on rowid; the name tiebreak makes the list stable and alphabetical
    within a second.
    """
    rows = conn.execute(
        "SELECT * FROM rooms ORDER BY updated_at DESC, name COLLATE NOCASE ASC"
    ).fetchall()
    return [_room_from_row(conn, r) for r in rows]


def get_room(conn: sqlite3.Connection, room_id: str) -> Optional[Room]:
    row = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    return _room_from_row(conn, row) if row is not None else None


def delete_room(conn: sqlite3.Connection, room_id: str) -> bool:
    """Delete a room and its roster (cascade). False when already gone."""
    with write_txn(conn):
        cur = conn.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
    return cur.rowcount > 0
