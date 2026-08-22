"""The ``rooms.*`` JSON-RPC family (``tui_gateway/methods_rooms.py``).

Two things are under test here:

* the family reached the live registry at all — it is installed by the
  ``methods_*`` walk, with no edit to server.py, so "did it register" is a real
  question and not a formality;
* the envelope contract the panel branches on: a client mistake comes back as
  5081 and a store fault as 5080, an unknown id on update yields
  ``room: null`` rather than a resurrected room, and ``memberIds`` present-vs-
  absent stay two different requests all the way down;
* profile scoping — ``params['profile']`` must reach the store, because the
  desktop runs one backend for every profile.

The store is redirected at ``tmp_path`` by patching ``get_hermes_home`` inside
``rooms_db``, so no test touches the real ``$HERMES_HOME/rooms.db``.
"""

from __future__ import annotations

import pytest

import tui_gateway.server as srv
from hermes_cli import rooms_db


ROOM_METHODS = ("rooms.create", "rooms.delete", "rooms.list", "rooms.update")


@pytest.fixture(autouse=True)
def rooms_home(monkeypatch, tmp_path):
    """Point the per-profile store at a throwaway home for every test."""
    monkeypatch.setattr(rooms_db, "get_hermes_home", lambda: tmp_path)
    return tmp_path


def _call(method: str, params: dict) -> dict:
    """Invoke a registered RPC method and return its ``result`` dict."""
    envelope = srv._methods[method](1, params)
    assert "error" not in envelope, envelope.get("error")
    return envelope["result"]


def _error(method: str, params: dict) -> dict:
    """Invoke a method that is expected to fail; return its ``error`` dict."""
    envelope = srv._methods[method](1, params)
    assert "result" not in envelope, envelope.get("result")
    return envelope["error"]


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ROOM_METHODS)
def test_the_family_reached_the_live_method_registry(name):
    """server.py was not edited: the ``methods_*`` walk found this module."""
    assert callable(srv._methods.get(name))


def test_the_walk_lists_the_rooms_module():
    from tui_gateway import method_modules

    assert "methods_rooms" in method_modules.discover_method_modules()


# ---------------------------------------------------------------------------
# rooms.list / rooms.create
# ---------------------------------------------------------------------------


def test_list_starts_empty_and_shows_created_rooms():
    assert _call("rooms.list", {}) == {"rooms": []}

    created = _call("rooms.create", {"memberIds": ["a", "b"], "name": "Crew"})["room"]

    assert created["name"] == "Crew"
    assert created["memberIds"] == ["a", "b"]
    assert set(created) == {"id", "name", "memberIds", "createdAt", "updatedAt"}

    assert _call("rooms.list", {})["rooms"] == [created]


def test_create_without_members_is_an_empty_room():
    room = _call("rooms.create", {"name": "Solo"})["room"]

    assert room["memberIds"] == []


@pytest.mark.parametrize("params", [{}, {"name": ""}, {"name": "   "}])
def test_create_without_a_name_is_a_client_error(params):
    assert _error("rooms.create", params)["code"] == 5081
    assert _call("rooms.list", {})["rooms"] == []


def test_create_with_a_non_list_roster_is_rejected_not_coerced():
    """Coercing to ``[]`` would quietly create a room the user meant to crew."""
    err = _error("rooms.create", {"memberIds": "a,b", "name": "Crew"})

    assert err["code"] == 5081
    assert "memberIds" in err["message"]
    assert _call("rooms.list", {})["rooms"] == []


def test_create_normalizes_the_roster():
    room = _call(
        "rooms.create", {"memberIds": [" a ", "a", "", "b"], "name": "Messy"}
    )["room"]

    assert room["memberIds"] == ["a", "b"]


# ---------------------------------------------------------------------------
# rooms.update
# ---------------------------------------------------------------------------


def test_update_renames_and_replaces_the_roster():
    room = _call("rooms.create", {"memberIds": ["a", "b"], "name": "Old"})["room"]

    updated = _call(
        "rooms.update", {"id": room["id"], "memberIds": ["c"], "name": "New"}
    )["room"]

    assert updated["id"] == room["id"]
    assert updated["name"] == "New"
    assert updated["memberIds"] == ["c"]


def test_omitting_member_ids_keeps_the_roster_but_an_empty_list_clears_it():
    room = _call("rooms.create", {"memberIds": ["a", "b"], "name": "Crew"})["room"]

    kept = _call("rooms.update", {"id": room["id"], "name": "Crew II"})["room"]
    assert kept["memberIds"] == ["a", "b"]

    cleared = _call("rooms.update", {"id": room["id"], "memberIds": []})["room"]
    assert cleared["memberIds"] == []
    assert cleared["name"] == "Crew II"


def test_update_of_an_unknown_id_returns_a_null_room_not_an_error():
    """The panel treats this as "deleted underneath me", which is a race and
    not a fault — so it must not arrive as an error envelope."""
    assert _call("rooms.update", {"id": "room_missing", "name": "Ghost"})["room"] is None
    assert _call("rooms.list", {})["rooms"] == []


def test_update_without_an_id_is_a_client_error():
    assert _error("rooms.update", {"name": "x"})["code"] == 5081


def test_update_with_a_blank_name_is_a_client_error_and_changes_nothing():
    room = _call("rooms.create", {"memberIds": ["a"], "name": "Keep Me"})["room"]

    assert _error("rooms.update", {"id": room["id"], "name": "  "})["code"] == 5081
    assert _call("rooms.list", {})["rooms"] == [room]


def test_update_with_a_non_list_roster_leaves_the_roster_intact():
    """The dangerous coercion: ``[]`` is the CLEAR spelling, so a malformed
    ``memberIds`` must not be read as one."""
    room = _call("rooms.create", {"memberIds": ["a", "b"], "name": "Crew"})["room"]

    assert _error("rooms.update", {"id": room["id"], "memberIds": 7})["code"] == 5081
    assert _call("rooms.list", {})["rooms"][0]["memberIds"] == ["a", "b"]


# ---------------------------------------------------------------------------
# rooms.delete
# ---------------------------------------------------------------------------


def test_delete_reports_true_then_false():
    room = _call("rooms.create", {"name": "Temp"})["room"]

    assert _call("rooms.delete", {"id": room["id"]}) == {"deleted": True}
    assert _call("rooms.delete", {"id": room["id"]}) == {"deleted": False}
    assert _call("rooms.list", {})["rooms"] == []


def test_delete_without_an_id_is_a_client_error():
    assert _error("rooms.delete", {})["code"] == 5081


# ---------------------------------------------------------------------------
# Fault mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,params",
    [
        ("rooms.create", {"name": "x"}),
        ("rooms.delete", {"id": "room_x"}),
        ("rooms.list", {}),
        ("rooms.update", {"id": "room_x", "name": "x"}),
    ],
)
def test_a_broken_store_is_a_5080_fault_not_a_5081_client_error(
    monkeypatch, method, params
):
    def explode(*_a, **_kw):
        raise OSError("disk went away")

    monkeypatch.setattr(rooms_db, "connect_closing", explode)

    assert _error(method, params)["code"] == 5080


# ---------------------------------------------------------------------------
# Profile scoping
# ---------------------------------------------------------------------------


def test_a_profile_param_moves_the_store_to_that_profiles_home(
    monkeypatch, tmp_path
):
    """``rooms.db`` hangs off ``get_hermes_home()``, so a request naming a
    profile must be answered from THAT profile's home.

    Not a flag check: the launch profile and the named profile get real,
    separate DBs here, and the assertion is that a room created under one is
    invisible from the other. Drop ``@_profile_scoped`` from the handlers and
    both writes land in the launch home and this fails.
    """
    from hermes_constants import get_hermes_home as real_get_hermes_home

    launch = tmp_path / "launch"
    other = tmp_path / "other"
    other.mkdir(parents=True)

    # Undo the autouse redirect: this test needs the REAL resolution chain,
    # because the override the decorator installs is what is under test.
    monkeypatch.setattr(rooms_db, "get_hermes_home", real_get_hermes_home)
    monkeypatch.setenv("HERMES_HOME", str(launch))
    monkeypatch.setattr(
        srv, "_profile_home", lambda name: other if name == "other" else None
    )

    _call("rooms.create", {"name": "Launch Room"})
    _call("rooms.create", {"name": "Other Room", "profile": "other"})

    assert [r["name"] for r in _call("rooms.list", {})["rooms"]] == ["Launch Room"]
    assert [
        r["name"] for r in _call("rooms.list", {"profile": "other"})["rooms"]
    ] == ["Other Room"]

    assert (launch / "rooms.db").exists()
    assert (other / "rooms.db").exists()
