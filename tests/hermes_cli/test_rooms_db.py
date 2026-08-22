"""Tests for the per-profile Rooms store (``hermes_cli/rooms_db``).

Every test opens an explicit ``db_path`` under ``tmp_path`` so the real
``$HERMES_HOME/rooms.db`` is never touched.
"""

from __future__ import annotations

import pytest

from hermes_cli import rooms_db as rdb


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "rooms.db"


@pytest.fixture
def conn(db_path):
    c = rdb.connect(db_path=db_path)
    try:
        yield c
    finally:
        c.close()


# ---------------------------------------------------------------------------
# Empty store
# ---------------------------------------------------------------------------


def test_a_fresh_store_is_empty(conn):
    """Nothing is seeded. The panel's empty state is the first-run truth, and
    the write path is how it stops being empty."""
    assert rdb.list_rooms(conn) == []


def test_rooms_db_path_follows_hermes_home(monkeypatch, tmp_path):
    monkeypatch.setattr(rdb, "get_hermes_home", lambda: tmp_path / "profile")

    assert rdb.rooms_db_path() == tmp_path / "profile" / "rooms.db"


# ---------------------------------------------------------------------------
# create_room
# ---------------------------------------------------------------------------


def test_create_room_returns_a_room_that_round_trips(conn):
    room = rdb.create_room(conn, name="  Launch Crew  ", member_ids=("scout", "smith"))

    assert room.id.startswith("room_")
    assert room.name == "Launch Crew"  # whitespace trimmed
    assert room.member_ids == ["scout", "smith"]
    assert room.created_at > 0
    assert room.updated_at == room.created_at

    # The returned object is not the only source of truth.
    stored = rdb.get_room(conn, room.id)
    assert stored is not None
    assert stored.name == "Launch Crew"
    assert stored.member_ids == ["scout", "smith"]


def test_create_room_ids_are_distinct(conn):
    first = rdb.create_room(conn, name="One")
    second = rdb.create_room(conn, name="Two")

    assert first.id != second.id
    assert second.member_ids == []


@pytest.mark.parametrize("bad_name", ["", "   ", "\t\n"])
def test_blank_name_raises_and_writes_nothing(conn, bad_name):
    with pytest.raises(ValueError):
        rdb.create_room(conn, name=bad_name)

    assert rdb.list_rooms(conn) == []


def test_member_ids_are_stripped_deduped_and_ordered(conn):
    room = rdb.create_room(
        conn,
        name="Messy Roster",
        member_ids=("zeta", "", "  alpha  ", "zeta", "   ", "beta", "alpha"),
    )

    # First-seen order wins; blanks and repeats are dropped.
    assert room.member_ids == ["zeta", "alpha", "beta"]
    assert rdb.get_room(conn, room.id).member_ids == ["zeta", "alpha", "beta"]


def test_normalize_member_ids_is_the_whole_contract():
    assert rdb.normalize_member_ids(None) == []
    assert rdb.normalize_member_ids(()) == []
    assert rdb.normalize_member_ids([" a ", "a", "", "b"]) == ["a", "b"]


def test_normalize_name_trims_and_rejects_blank():
    assert rdb.normalize_name("  Room  ") == "Room"

    with pytest.raises(ValueError):
        rdb.normalize_name("   ")


# ---------------------------------------------------------------------------
# update_room
# ---------------------------------------------------------------------------


def test_update_replaces_the_roster_wholesale(conn):
    created = rdb.create_room(conn, name="Trio", member_ids=("a", "b", "c"))

    updated = rdb.update_room(conn, created.id, name="Duo", member_ids=("c", "d"))

    assert updated is not None
    assert updated.id == created.id
    assert updated.name == "Duo"
    # Removed members are gone (not merged), and the new order is preserved.
    assert updated.member_ids == ["c", "d"]
    assert rdb.get_room(conn, created.id).member_ids == ["c", "d"]
    # No second row was created.
    assert len(rdb.list_rooms(conn)) == 1


def test_update_name_only_leaves_the_roster_alone(conn):
    created = rdb.create_room(conn, name="Keep", member_ids=("a", "b"))

    updated = rdb.update_room(conn, created.id, name="Renamed")

    assert updated.name == "Renamed"
    assert updated.member_ids == ["a", "b"]


def test_update_members_only_leaves_the_name_alone(conn):
    created = rdb.create_room(conn, name="Keep", member_ids=("a",))

    updated = rdb.update_room(conn, created.id, member_ids=("b", "c"))

    assert updated.name == "Keep"
    assert updated.member_ids == ["b", "c"]


def test_empty_member_list_clears_the_roster_but_none_does_not(conn):
    """``[]`` and ``None`` are different requests — the panel needs both."""
    created = rdb.create_room(conn, name="Crew", member_ids=("a", "b"))

    kept = rdb.update_room(conn, created.id, name="Crew")
    assert kept.member_ids == ["a", "b"]

    cleared = rdb.update_room(conn, created.id, member_ids=[])
    assert cleared.member_ids == []


def test_update_of_an_unknown_id_returns_none_and_creates_nothing(conn):
    """A stale id means the room was deleted underneath the panel. Recreating
    it as a fresh empty room would be the wrong answer to a lost race."""
    assert rdb.update_room(conn, "room_deadbeef", name="Ghost") is None
    assert rdb.list_rooms(conn) == []


def test_blank_name_on_update_does_not_touch_the_existing_room(conn):
    created = rdb.create_room(conn, name="Keep Me", member_ids=("a",))

    with pytest.raises(ValueError):
        rdb.update_room(conn, created.id, name="  ")

    survivor = rdb.get_room(conn, created.id)
    assert survivor.name == "Keep Me"
    assert survivor.member_ids == ["a"]


def test_update_bumps_updated_at_without_touching_created_at(conn, monkeypatch):
    created = rdb.create_room(conn, name="Aging")

    monkeypatch.setattr(rdb, "_now", lambda: created.created_at + 60)
    updated = rdb.update_room(conn, created.id, name="Aged")

    assert updated.created_at == created.created_at
    assert updated.updated_at == created.created_at + 60


# ---------------------------------------------------------------------------
# list / get / delete
# ---------------------------------------------------------------------------


def test_list_rooms_is_most_recently_touched_first(conn, monkeypatch):
    clock = {"t": 1_000}
    monkeypatch.setattr(rdb, "_now", lambda: clock["t"])

    first = rdb.create_room(conn, name="First")
    clock["t"] += 10
    second = rdb.create_room(conn, name="Second")

    assert [r.id for r in rdb.list_rooms(conn)] == [second.id, first.id]

    clock["t"] += 10
    rdb.update_room(conn, first.id, name="First Again")

    assert [r.id for r in rdb.list_rooms(conn)] == [first.id, second.id]


def test_rooms_written_in_the_same_second_sort_by_name(conn, monkeypatch):
    """Otherwise the order of a scripted setup depends on rowid."""
    monkeypatch.setattr(rdb, "_now", lambda: 500)

    rdb.create_room(conn, name="zulu")
    rdb.create_room(conn, name="Alpha")

    assert [r.name for r in rdb.list_rooms(conn)] == ["Alpha", "zulu"]


def test_get_room_returns_none_for_unknown_id(conn):
    assert rdb.get_room(conn, "room_does_not_exist") is None


def test_delete_room_returns_true_then_false(conn):
    room = rdb.create_room(conn, name="Temp", member_ids=("a", "b"))

    assert rdb.delete_room(conn, room.id) is True
    assert rdb.get_room(conn, room.id) is None
    assert rdb.delete_room(conn, room.id) is False
    assert rdb.delete_room(conn, "never-existed") is False


def test_deleting_a_room_reaps_its_members(conn):
    """The cascade only fires because ``connect`` sets PRAGMA foreign_keys=ON;
    without it the rows would linger and re-attach to a recycled id."""
    room = rdb.create_room(conn, name="Temp", member_ids=("a", "b"))

    rdb.delete_room(conn, room.id)

    orphans = conn.execute(
        "SELECT COUNT(*) AS n FROM room_members WHERE room_id = ?", (room.id,)
    ).fetchone()["n"]
    assert orphans == 0


# ---------------------------------------------------------------------------
# Wire shape + persistence
# ---------------------------------------------------------------------------


def test_to_dict_uses_camel_case_wire_keys(conn):
    room = rdb.create_room(conn, name="Wire", member_ids=("a", "b"))

    payload = room.to_dict()

    assert set(payload) == {"id", "name", "memberIds", "createdAt", "updatedAt"}
    assert payload["memberIds"] == ["a", "b"]
    assert payload["name"] == "Wire"
    assert isinstance(payload["createdAt"], int)
    assert isinstance(payload["updatedAt"], int)

    # memberIds is a copy — mutating it must not corrupt the Room.
    payload["memberIds"].append("c")
    assert room.member_ids == ["a", "b"]


def test_rooms_persist_across_reopen(db_path):
    with rdb.connect_closing(db_path) as conn:
        room_id = rdb.create_room(conn, name="Persisted", member_ids=("x", "y")).id

    with rdb.connect_closing(db_path) as conn:
        room = rdb.get_room(conn, room_id)
        assert room is not None
        assert room.name == "Persisted"
        assert room.member_ids == ["x", "y"]


def test_stores_are_isolated_per_db_path(tmp_path):
    """Two db_paths stand in for two profiles' HERMES_HOME."""
    a_path = tmp_path / "a" / "rooms.db"
    b_path = tmp_path / "b" / "rooms.db"

    with rdb.connect_closing(a_path) as a:
        rdb.create_room(a, name="Only In A")

    with rdb.connect_closing(b_path) as b:
        assert [room.name for room in rdb.list_rooms(b)] == []


def test_connect_creates_the_parent_directory(tmp_path):
    nested = tmp_path / "does" / "not" / "exist" / "rooms.db"

    with rdb.connect_closing(nested) as conn:
        rdb.create_room(conn, name="Made The Dir")

    assert nested.exists()
