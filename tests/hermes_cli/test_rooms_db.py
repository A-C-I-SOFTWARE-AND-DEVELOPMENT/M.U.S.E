"""Tests for the per-profile Rooms store (hermes_cli/rooms_db).

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


def _by_id(conn):
    return {room.id: room for room in rdb.list_rooms(conn)}


def test_presets_seeded_on_first_open_with_declared_member_order(conn):
    """First open materialises a preset per registry section, each with its
    roster in registry order (position, not alphabetical)."""
    rooms = _by_id(conn)
    presets = rdb.preset_rooms()

    assert presets, "the council registry should yield at least one preset"
    assert set(rooms) == {preset[0] for preset in presets}

    for room_id, name, mixture, members in presets:
        room = rooms[room_id]
        assert room.name == name
        assert room.mixture == mixture
        assert room.preset is True
        assert room.member_ids == list(members)


def test_preset_members_are_real_dispatchable_agents(conn):
    """Every seeded member must exist in the council registry.

    The presets were originally ported from the cockpit, whose member ids are
    its OWN agent namespace — only 7 of 39 existed in MUSE, so six of the seven
    boards were full of agents nothing could route to. Presets are now derived
    from the registry; this is the assertion that keeps them honest.
    """
    from hermes_cli.jarvis_prime.aos_council import dispatcher

    known = {
        str(member.id)
        for members in dispatcher.roster().values()
        for member in members
    }

    seeded = {mid for room in rdb.list_rooms(conn) for mid in room.member_ids}

    assert seeded, "presets should seed at least one member"
    assert seeded <= known, f"unknown agent ids seeded: {sorted(seeded - known)}"


def test_presets_seeded_exactly_once_so_deletes_stay_deleted(db_path):
    """Seeding is guarded by a ``rooms_meta`` flag, not by "table is empty":
    deleting every preset and reopening must NOT resurrect them."""
    with rdb.connect_closing(db_path) as conn:
        for room in rdb.list_rooms(conn):
            assert rdb.delete_room(conn, room.id) is True
        assert rdb.list_rooms(conn) == []

    with rdb.connect_closing(db_path) as conn:
        assert rdb.list_rooms(conn) == []
        assert rdb.get_room(conn, "preset-council") is None


def test_deleting_one_preset_survives_reopen(db_path):
    """The single-preset case of the same guarantee."""
    presets = rdb.preset_rooms()
    assert len(presets) >= 2, "this test needs two presets to tell them apart"
    doomed, kept = presets[0][0], presets[1][0]

    with rdb.connect_closing(db_path) as conn:
        assert rdb.delete_room(conn, doomed) is True

    with rdb.connect_closing(db_path) as conn:
        ids = {room.id for room in rdb.list_rooms(conn)}
        assert doomed not in ids
        assert kept in ids


def test_upsert_without_id_creates_non_preset_room_with_generated_id(conn):
    room = rdb.upsert_room(
        conn, name="  Launch Room  ", mixture="experts", member_ids=("axiom", "warden")
    )

    assert room.id and room.id not in {p[0] for p in rdb.preset_rooms()}
    assert room.id.startswith("room-")
    assert room.name == "Launch Room"  # whitespace trimmed
    assert room.mixture == "experts"
    assert room.preset is False
    assert room.member_ids == ["axiom", "warden"]
    assert room.created_at > 0 and room.updated_at > 0

    # Round-trips through the store, not just the returned object.
    assert rdb.get_room(conn, room.id).member_ids == ["axiom", "warden"]

    other = rdb.upsert_room(conn, name="Second")
    assert other.id != room.id
    assert other.member_ids == []


def test_upsert_with_existing_id_replaces_roster_wholesale(conn):
    created = rdb.upsert_room(
        conn, name="Trio", mixture="agents", member_ids=("a", "b", "c")
    )

    updated = rdb.upsert_room(
        conn,
        room_id=created.id,
        name="Duo",
        mixture="council",
        member_ids=("c", "d"),
    )

    assert updated.id == created.id
    assert updated.name == "Duo"
    assert updated.mixture == "council"
    # Removed members are gone (not merged), and the new order is preserved.
    assert updated.member_ids == ["c", "d"]
    assert rdb.get_room(conn, created.id).member_ids == ["c", "d"]
    # No duplicate room row was created.
    assert len([r for r in rdb.list_rooms(conn) if not r.preset]) == 1


def test_upsert_with_empty_roster_clears_members(conn):
    created = rdb.upsert_room(conn, name="Crew", member_ids=("a", "b"))

    cleared = rdb.upsert_room(conn, room_id=created.id, name="Crew")

    assert cleared.member_ids == []


def test_editing_a_preset_keeps_the_preset_flag(conn):
    """``preset`` is provenance ("shipped with muse"), not immutability."""
    target = rdb.preset_rooms()[0][0]

    edited = rdb.upsert_room(
        conn,
        room_id=target,
        name="My Own Board",
        mixture="experts",
        member_ids=("council-director",),
    )

    assert edited.preset is True
    assert edited.name == "My Own Board"
    assert edited.mixture == "experts"
    assert edited.member_ids == ["council-director"]

    reloaded = rdb.get_room(conn, target)
    assert reloaded.preset is True
    assert reloaded.member_ids == ["council-director"]


def test_member_ids_deduplicated_blanks_skipped_order_preserved(conn):
    room = rdb.upsert_room(
        conn,
        name="Messy Roster",
        member_ids=("zeta", "", "  alpha  ", "zeta", "   ", "beta", "alpha"),
    )

    assert room.member_ids == ["zeta", "alpha", "beta"]
    assert rdb.get_room(conn, room.id).member_ids == ["zeta", "alpha", "beta"]


@pytest.mark.parametrize("bad_name", ["", "   ", "\t\n"])
def test_blank_name_raises_value_error(conn, bad_name):
    with pytest.raises(ValueError):
        rdb.upsert_room(conn, name=bad_name)

    assert [r for r in rdb.list_rooms(conn) if not r.preset] == []


def test_blank_name_on_update_does_not_touch_existing_room(conn):
    created = rdb.upsert_room(conn, name="Keep Me", member_ids=("a",))

    with pytest.raises(ValueError):
        rdb.upsert_room(conn, room_id=created.id, name="  ")

    survivor = rdb.get_room(conn, created.id)
    assert survivor.name == "Keep Me"
    assert survivor.member_ids == ["a"]


@pytest.mark.parametrize("value", list(rdb.MIXTURES))
def test_normalize_mixture_preserves_known_values(value):
    assert rdb.normalize_mixture(value) == value


@pytest.mark.parametrize(
    "value",
    [None, "", "   ", "swarm", "COUNCIL!", "123", "counc"],
)
def test_normalize_mixture_falls_back_to_default(value):
    assert rdb.normalize_mixture(value) == rdb.DEFAULT_MIXTURE


@pytest.mark.parametrize("value", ["  Council  ", "EXPERTS", "AgEnTs"])
def test_normalize_mixture_trims_and_lowercases(value):
    assert rdb.normalize_mixture(value) == value.strip().lower()
    assert rdb.normalize_mixture(value) in rdb.MIXTURES


def test_unknown_mixture_is_stored_as_default(conn):
    room = rdb.upsert_room(conn, name="Odd", mixture="telepathy")

    assert room.mixture == rdb.DEFAULT_MIXTURE
    assert rdb.get_room(conn, room.id).mixture == rdb.DEFAULT_MIXTURE


def test_delete_room_returns_true_then_false(conn):
    room = rdb.upsert_room(conn, name="Temp", member_ids=("a", "b"))

    assert rdb.delete_room(conn, room.id) is True
    assert rdb.get_room(conn, room.id) is None
    assert rdb.delete_room(conn, room.id) is False
    assert rdb.delete_room(conn, "never-existed") is False

    # Members went with the room rather than lingering for a recycled id.
    orphans = conn.execute(
        "SELECT COUNT(*) AS n FROM room_members WHERE room_id = ?", (room.id,)
    ).fetchone()["n"]
    assert orphans == 0


def test_get_room_returns_none_for_unknown_id(conn):
    assert rdb.get_room(conn, "room-does-not-exist") is None


def test_to_dict_uses_camel_case_wire_keys(conn):
    room = rdb.upsert_room(
        conn, name="Wire", mixture="experts", member_ids=("a", "b")
    )

    payload = room.to_dict()

    assert set(payload) == {
        "id",
        "name",
        "mixture",
        "preset",
        "memberIds",
        "createdAt",
        "updatedAt",
    }
    assert payload["memberIds"] == ["a", "b"]
    assert payload["name"] == "Wire"
    assert payload["mixture"] == "experts"
    assert payload["preset"] is False
    assert isinstance(payload["createdAt"], int)
    assert isinstance(payload["updatedAt"], int)

    # memberIds is a copy — mutating it must not corrupt the Room.
    payload["memberIds"].append("c")
    assert room.member_ids == ["a", "b"]


def test_rooms_persist_across_reopen(db_path):
    with rdb.connect_closing(db_path) as conn:
        created = rdb.upsert_room(
            conn, name="Persisted", mixture="agents", member_ids=("x", "y")
        )
        room_id = created.id

    with rdb.connect_closing(db_path) as conn:
        room = rdb.get_room(conn, room_id)
        assert room is not None
        assert room.name == "Persisted"
        assert room.mixture == "agents"
        assert room.member_ids == ["x", "y"]
        assert room.preset is False


def test_stores_are_isolated_per_db_path(tmp_path):
    """Two db_paths stand in for two profiles' HERMES_HOME."""
    a_path = tmp_path / "a" / "rooms.db"
    b_path = tmp_path / "b" / "rooms.db"

    with rdb.connect_closing(a_path) as a:
        rdb.upsert_room(a, name="Only In A")

    with rdb.connect_closing(b_path) as b:
        names = {room.name for room in rdb.list_rooms(b)}
        assert "Only In A" not in names


def test_list_rooms_puts_presets_first(conn):
    rdb.upsert_room(conn, name="Custom Board")

    rooms = rdb.list_rooms(conn)
    flags = [room.preset for room in rooms]

    assert flags == sorted(flags, reverse=True)
    assert rooms[-1].name == "Custom Board"
