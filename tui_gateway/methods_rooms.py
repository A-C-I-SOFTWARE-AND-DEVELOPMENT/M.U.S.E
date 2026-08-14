"""Rooms JSON-RPC handlers — the TUI's window onto the per-profile room store.

A **room** is a human-named board of agents plus a *mixture* saying how they
work a problem (``council`` / ``experts`` / ``agents``). The cockpit has had
this surface for a while, backed by its own SQL table; the TUI had nothing to
show because MUSE had no equivalent store. ``hermes_cli/rooms_db.py`` is that
store, and these three methods are the only thing standing between it and the
cockpit's Rooms surface in the terminal:

- ``rooms.list``   — every room, presets first, then newest-updated.
- ``rooms.upsert`` — create a room, or edit the one at ``id`` (members are
  replaced wholesale: the client owns the full roster).
- ``rooms.delete`` — remove a room; ``deleted`` is false when it was already
  gone, which is a normal outcome and not an error.

Each handler opens and closes its own connection (``connect_closing``) rather
than holding one on the gateway: the store is a small per-profile SQLite file,
and a per-call connection keeps profile switches honest.

``rooms_db`` is imported inside the handler bodies, not at module level: these
handlers are rebound onto server.py's globals at install time (see
method_ctx.py), so a module-level import here would not be visible to them.
"""

from .method_ctx import HandlerRegistry

_registry = HandlerRegistry()
method = _registry.method
_profile_scoped = _registry.profile_scoped


@method("rooms.list")
def _(rid, params: dict) -> dict:
    """Every room in the active profile's store, as the TUI renders them."""
    try:
        from hermes_cli import rooms_db as rdb

        with rdb.connect_closing() as conn:
            rooms = [room.to_dict() for room in rdb.list_rooms(conn)]
        return _ok(rid, {"rooms": rooms})
    except Exception as e:
        return _err(rid, 5064, str(e))


@method("rooms.upsert")
def _(rid, params: dict) -> dict:
    """Create a room, or update the one at ``id``.

    An empty/missing ``name`` is the client's mistake, not a server fault, so
    it comes back as a plain client error rather than a stack-trace 5064.
    """
    try:
        from hermes_cli import rooms_db as rdb

        room_id = str(params.get("id") or "").strip() or None
        name = str(params.get("name") or "").strip()
        if not name:
            return _err(rid, 5065, "name required")

        raw_mixture = params.get("mixture")
        mixture = str(raw_mixture).strip() if raw_mixture is not None else None

        raw_members = params.get("memberIds")
        if raw_members is None:
            member_ids: list[str] = []
        elif isinstance(raw_members, (list, tuple)):
            member_ids = [str(m) for m in raw_members if str(m or "").strip()]
        else:
            return _err(rid, 5065, "memberIds must be a list")

        with rdb.connect_closing() as conn:
            room = rdb.upsert_room(
                conn,
                room_id=room_id,
                name=name,
                mixture=mixture,
                member_ids=member_ids,
            )
        return _ok(rid, {"room": room.to_dict()})
    except ValueError as e:
        # rooms_db rejects an empty name; the guard above catches the common
        # case, this catches anything else the store considers unusable input.
        return _err(rid, 5065, str(e))
    except Exception as e:
        return _err(rid, 5064, str(e))


@method("rooms.delete")
def _(rid, params: dict) -> dict:
    """Delete a room. ``deleted`` is false when it was already gone."""
    try:
        from hermes_cli import rooms_db as rdb

        room_id = str(params.get("id") or "").strip()
        if not room_id:
            return _err(rid, 5065, "id required")

        with rdb.connect_closing() as conn:
            deleted = rdb.delete_room(conn, room_id)
        return _ok(rid, {"deleted": bool(deleted)})
    except Exception as e:
        return _err(rid, 5064, str(e))


def register(server) -> None:
    """Bind this module's handlers onto ``server``'s globals and registry."""
    _registry.install(server)
