"""Per-profile room store — named boards of agents that meet on a goal.

A **Room** is a human-named group of agents with a *mixture* describing how
they work the problem:

- ``council``  — the room talks it through, then one member decides.
- ``experts``  — a few specialists each take the parts they own.
- ``agents``   — everyone takes a turn, and you get one answer.

This backs the cockpit's Rooms surface. The cockpit persists rooms in its own
SQL table; MUSE had no equivalent — ``gateway/cockpit/room_store.py`` is an
unrelated store for AI-generated *room décor* (Den items), and
``enterprise/council.py`` is a task dispatcher with no notion of a named,
persisted board. So the TUI had nothing to show. This is that missing store.

Scope: **per-profile**, at ``$HERMES_HOME/rooms.db`` (resolved via
``get_hermes_home()``), mirroring sessions / config / cron / projects rather
than kanban's root-anchored board DB.

Presets are seeded once, on first open, and are ordinary rows afterwards:
renaming or re-crewing a preset persists like any other room, and deleting one
keeps it deleted (the seed only runs when the table has never been seeded).
That mirrors the cockpit, where presets are real editable rows rather than
read-only constants.

The schema is intentionally small and additive: column additions go through
:func:`_add_column_if_missing` so opening an old DB is always safe.
"""

from __future__ import annotations

import contextlib
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional, Sequence

MIXTURES = ("agents", "council", "experts")
DEFAULT_MIXTURE = "council"

# Mirrors the cockpit's PRESET_ROOMS so a user moving between the two surfaces
# sees the same starting boards. Seeded once; editable and deletable after.
PRESET_ROOMS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "preset-aos",
        "Active Council",
        "council",
        (
            "council-director",
            "evidence-architect",
            "delivery-scope-controller",
            "product-experience-architect",
            "assurance-risk-director",
            "contrarian-reviewer",
        ),
    ),
    (
        "preset-shipping",
        "Shipping Board",
        "council",
        ("commander", "verdict", "nitpick", "warden", "axiom", "council-director"),
    ),
    (
        "preset-security",
        "Security Circle",
        "agents",
        ("warden", "cipher", "breach", "auditrix", "clause", "hazmat"),
    ),
    (
        "preset-product",
        "Product Studio",
        "experts",
        ("product", "ux", "empath", "mirror", "strategist", "devux"),
    ),
    (
        "preset-architecture",
        "The Stacks",
        "agents",
        ("axiom", "lattice", "forgemind", "foreman", "pipeline"),
    ),
    (
        "preset-research",
        "Research Vault",
        "experts",
        ("oracle", "archivist", "radar", "evidence", "mneme"),
    ),
    (
        "preset-care",
        "Care Board",
        "agents",
        ("companion", "empath", "nourish", "patch", "mirror"),
    ),
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rooms (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    mixture     TEXT NOT NULL DEFAULT 'council',
    preset      INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS room_members (
    room_id   TEXT NOT NULL,
    agent_id  TEXT NOT NULL,
    position  INTEGER NOT NULL,
    PRIMARY KEY (room_id, agent_id),
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_room_members_room ON room_members(room_id, position);

CREATE TABLE IF NOT EXISTS rooms_meta (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
"""

_SEEDED_KEY = "presets_seeded"


@dataclass
class Room:
    """A named board of agents."""

    id: str
    name: str
    mixture: str = DEFAULT_MIXTURE
    preset: bool = False
    member_ids: List[str] = field(default_factory=list)
    created_at: int = 0
    updated_at: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "mixture": self.mixture,
            "preset": self.preset,
            "memberIds": list(self.member_ids),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


def rooms_db_path() -> Path:
    """``$HERMES_HOME/rooms.db`` — per profile, like sessions and projects."""
    from hermes_constants import get_hermes_home

    return get_hermes_home() / "rooms.db"


def _now() -> int:
    return int(time.time())


def _new_room_id() -> str:
    return f"room-{uuid.uuid4().hex[:12]}"


def normalize_mixture(value: Optional[str]) -> str:
    """Coerce to a known mixture. Unknown values fall back to the default
    rather than raising: a room with an odd mixture should still be listed."""
    candidate = (value or "").strip().lower()

    return candidate if candidate in MIXTURES else DEFAULT_MIXTURE


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}

    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open (and idempotently initialise) the room store.

    Schema init is idempotent (``CREATE TABLE IF NOT EXISTS``), so opening an
    existing DB is always safe.
    """
    path = db_path if db_path is not None else rooms_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    _migrate(conn)
    _seed_presets_once(conn)
    conn.commit()

    return conn


@contextlib.contextmanager
def connect_closing(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive-only migrations. Kept separate so new columns never require a
    rebuild of an existing store."""
    _add_column_if_missing(conn, "rooms", "mixture", "TEXT NOT NULL DEFAULT 'council'")
    _add_column_if_missing(conn, "rooms", "preset", "INTEGER NOT NULL DEFAULT 0")


def _seed_presets_once(conn: sqlite3.Connection) -> None:
    """Seed the cockpit's preset boards exactly once.

    Guarded by a meta flag rather than by row count: seeding on "table is
    empty" would resurrect every preset the moment a user deleted the last
    room, which is the opposite of what deleting means.
    """
    seeded = conn.execute("SELECT value FROM rooms_meta WHERE key = ?", (_SEEDED_KEY,)).fetchone()

    if seeded is not None:
        return

    now = _now()

    for room_id, name, mixture, members in PRESET_ROOMS:
        conn.execute(
            "INSERT OR IGNORE INTO rooms (id, name, mixture, preset, created_at, updated_at)"
            " VALUES (?, ?, ?, 1, ?, ?)",
            (room_id, name, normalize_mixture(mixture), now, now),
        )
        for position, agent_id in enumerate(members):
            conn.execute(
                "INSERT OR IGNORE INTO room_members (room_id, agent_id, position) VALUES (?, ?, ?)",
                (room_id, agent_id, position),
            )

    conn.execute("INSERT OR REPLACE INTO rooms_meta (key, value) VALUES (?, ?)", (_SEEDED_KEY, "1"))


def _members(conn: sqlite3.Connection, room_id: str) -> List[str]:
    rows = conn.execute(
        "SELECT agent_id FROM room_members WHERE room_id = ? ORDER BY position, agent_id",
        (room_id,),
    )

    return [row["agent_id"] for row in rows]


def _room_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> Room:
    return Room(
        id=row["id"],
        name=row["name"],
        mixture=normalize_mixture(row["mixture"]),
        preset=bool(row["preset"]),
        member_ids=_members(conn, row["id"]),
        created_at=int(row["created_at"] or 0),
        updated_at=int(row["updated_at"] or 0),
    )


def list_rooms(conn: sqlite3.Connection) -> List[Room]:
    """Every room: presets first in their declared order, then user rooms
    newest-updated.

    Presets are all seeded in the same second, so ordering them by
    ``updated_at`` collapses to the name tiebreak and returns them
    alphabetically — "Active Council" is meant to lead, not "Care Board".
    Insertion order (``rowid``) is the declared order from PRESET_ROOMS, so
    presets sort by that instead.
    """
    rows = conn.execute(
        "SELECT * FROM rooms"
        " ORDER BY preset DESC,"
        "          CASE WHEN preset = 1 THEN rowid END ASC,"
        "          updated_at DESC,"
        "          name COLLATE NOCASE"
    ).fetchall()

    return [_room_from_row(conn, row) for row in rows]


def get_room(conn: sqlite3.Connection, room_id: str) -> Optional[Room]:
    row = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()

    return _room_from_row(conn, row) if row is not None else None


def upsert_room(
    conn: sqlite3.Connection,
    *,
    room_id: Optional[str] = None,
    name: str,
    mixture: Optional[str] = None,
    member_ids: Sequence[str] = (),
) -> Room:
    """Create a room, or update the one at *room_id*.

    Editing a preset is allowed and keeps its ``preset`` flag — the flag marks
    provenance ("this shipped with muse"), not immutability.
    """
    clean_name = (name or "").strip()

    if not clean_name:
        raise ValueError("room name must not be empty")

    now = _now()
    rid = room_id or _new_room_id()
    existing = conn.execute("SELECT id, preset, created_at FROM rooms WHERE id = ?", (rid,)).fetchone()

    if existing is None:
        conn.execute(
            "INSERT INTO rooms (id, name, mixture, preset, created_at, updated_at) VALUES (?, ?, ?, 0, ?, ?)",
            (rid, clean_name, normalize_mixture(mixture), now, now),
        )
    else:
        conn.execute(
            "UPDATE rooms SET name = ?, mixture = ?, updated_at = ? WHERE id = ?",
            (clean_name, normalize_mixture(mixture), now, rid),
        )

    # Members are replaced wholesale: the caller owns the full roster, and a
    # diff would silently keep members the user just removed.
    conn.execute("DELETE FROM room_members WHERE room_id = ?", (rid,))

    seen: set[str] = set()
    position = 0

    for agent_id in member_ids:
        clean = (agent_id or "").strip()

        if not clean or clean in seen:
            continue

        seen.add(clean)
        conn.execute(
            "INSERT INTO room_members (room_id, agent_id, position) VALUES (?, ?, ?)",
            (rid, clean, position),
        )
        position += 1

    conn.commit()

    room = get_room(conn, rid)

    if room is None:  # pragma: no cover — the row was just written
        raise RuntimeError(f"room {rid} vanished during upsert")

    return room


def delete_room(conn: sqlite3.Connection, room_id: str) -> bool:
    """Delete a room. Returns False when it was already gone."""
    cur = conn.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
    conn.execute("DELETE FROM room_members WHERE room_id = ?", (room_id,))
    conn.commit()

    return cur.rowcount > 0
