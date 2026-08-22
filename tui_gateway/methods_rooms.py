"""Rooms JSON-RPC handlers — the TUI's window onto the per-profile room store.

A **room** is a human-named, ordered roster the user keeps around
(``hermes_cli/rooms_db.py``). Four methods cover the whole surface the
``/rooms`` panel needs, and the panel is the live caller of every one of them:

- ``rooms.list``   — every room, most recently touched first.
- ``rooms.create`` — a new room from a name and an optional roster.
- ``rooms.update`` — patch name and/or roster; the roster is REPLACED, not
  merged, because the client owns it. ``room`` comes back null when the id is
  unknown (the room was deleted underneath the panel), which is a normal race
  and not a fault.
- ``rooms.delete`` — remove a room; ``deleted`` is false when it was already
  gone, likewise not an error.

Error codes: **5080** means the store faulted (disk, lock, corruption); **5081**
means the client sent something unusable. Splitting them keeps a client bug
from reading as a gateway fault in the logs. Both were unused across
``tui_gateway`` before this module.

Each handler opens and closes its own connection (``connect_closing``) rather
than holding one on the gateway: the store is a small per-profile SQLite file,
and a per-call connection keeps profile switches honest — a switched
``HERMES_HOME`` is picked up by the next call instead of by a restart.

Every handler is ``@_profile_scoped``, exactly like the ``projects.*`` family
whose store this one mirrors. ``rooms.db`` is resolved through
``get_hermes_home()``, so in app-global remote mode — one backend serving every
profile, which is how the desktop runs — a request carrying ``params['profile']``
must be answered from THAT profile's home. Without the decorator these four
would quietly read and write the launch profile's rooms instead.

Two things this module deliberately does NOT do, both for the same reason:
``HandlerRegistry.install`` rebinds every handler's ``__globals__`` to
server.py's namespace (see method_ctx.py), so a handler body can only see names
that exist THERE.

* ``rooms_db`` is imported inside each body, never at module level.
* There are no shared helpers or constants at module level either — the
  roster-parsing block is repeated in ``create`` and ``update`` because a
  factored-out ``_parse_members`` would be a ``NameError`` at call time, not
  an import error at startup.
"""

from .method_ctx import HandlerRegistry

_registry = HandlerRegistry()
method = _registry.method
_profile_scoped = _registry.profile_scoped


@method("rooms.list")
@_profile_scoped
def _(rid, params: dict) -> dict:
    """Every room in the active profile's store, as the TUI renders them."""
    try:
        from hermes_cli import rooms_db

        with rooms_db.connect_closing() as conn:
            rooms = [room.to_dict() for room in rooms_db.list_rooms(conn)]
        return _ok(rid, {"rooms": rooms})
    except Exception as e:
        return _err(rid, 5080, str(e))


@method("rooms.create")
@_profile_scoped
def _(rid, params: dict) -> dict:
    """Create a room from ``name`` plus an optional ``memberIds`` roster."""
    try:
        from hermes_cli import rooms_db

        name = str(params.get("name") or "").strip()
        if not name:
            return _err(rid, 5081, "name required")

        raw_members = params.get("memberIds")
        if raw_members is None:
            member_ids = []
        elif isinstance(raw_members, (list, tuple)):
            member_ids = [str(m) for m in raw_members]
        else:
            # NOT coerced to an empty roster: that would quietly create a room
            # the user meant to crew.
            return _err(rid, 5081, "memberIds must be a list")

        with rooms_db.connect_closing() as conn:
            room = rooms_db.create_room(conn, name=name, member_ids=member_ids)
        return _ok(rid, {"room": room.to_dict()})
    except ValueError as e:
        return _err(rid, 5081, str(e))
    except Exception as e:
        return _err(rid, 5080, str(e))


@method("rooms.update")
@_profile_scoped
def _(rid, params: dict) -> dict:
    """Patch the room at ``id``. Omitted fields are left alone.

    ``memberIds: []`` clears the roster; omitting ``memberIds`` keeps it. The
    two are different requests and the handler must not collapse them.
    """
    try:
        from hermes_cli import rooms_db

        room_id = str(params.get("id") or "").strip()
        if not room_id:
            return _err(rid, 5081, "id required")

        raw_name = params.get("name")
        name = str(raw_name) if raw_name is not None else None

        raw_members = params.get("memberIds")
        if raw_members is None:
            member_ids = None
        elif isinstance(raw_members, (list, tuple)):
            member_ids = [str(m) for m in raw_members]
        else:
            # NOT coerced to []: that spelling CLEARS the roster, so coercing
            # a malformed parameter would delete the room's members outright.
            return _err(rid, 5081, "memberIds must be a list")

        with rooms_db.connect_closing() as conn:
            room = rooms_db.update_room(conn, room_id, name=name, member_ids=member_ids)
        return _ok(rid, {"room": room.to_dict() if room is not None else None})
    except ValueError as e:
        # rooms_db rejects a blank name even when the key was present.
        return _err(rid, 5081, str(e))
    except Exception as e:
        return _err(rid, 5080, str(e))


@method("rooms.delete")
@_profile_scoped
def _(rid, params: dict) -> dict:
    """Delete a room. ``deleted`` is false when it was already gone."""
    try:
        from hermes_cli import rooms_db

        room_id = str(params.get("id") or "").strip()
        if not room_id:
            return _err(rid, 5081, "id required")

        with rooms_db.connect_closing() as conn:
            deleted = rooms_db.delete_room(conn, room_id)
        return _ok(rid, {"deleted": bool(deleted)})
    except Exception as e:
        return _err(rid, 5080, str(e))


def register(server) -> None:
    """Bind this module's handlers onto ``server``'s globals and registry."""
    _registry.install(server)
