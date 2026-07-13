"""Authoritative M.U.S.E Universe plugin surfaces and shared contracts."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from . import api

from .models import (
    AuthorizationDecision,
    CommandResult,
    ProvenanceRecord,
    UniverseCommand,
    UniverseEvent,
)
from .store import (
    AmbiguousEntityError,
    CommandIdConflictError,
    ConflictError,
    UniverseStore,
)


QUERY_SCHEMA: dict[str, Any] = {
    "name": "muse_universe_query",
    "description": (
        "Read authoritative M.U.S.E realm, vessel, mission, and civilization "
        "state."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "enum": ["status", "catalog", "snapshot", "events", "entity"],
                "description": "The authoritative read operation to perform.",
            },
            "realm_id": {
                "type": "string",
                "description": "Realm identifier required by realm-scoped reads.",
            },
            "actor_id": {
                "type": "string",
                "description": (
                    "Authoritative caller identifier required for snapshots and "
                    "entities."
                ),
            },
            "since": {
                "type": "integer",
                "minimum": 0,
                "description": "Resume events strictly after this cursor.",
            },
            "entity_type": {
                "type": "string",
                "description": "Entity family for an entity read.",
            },
            "entity_id": {
                "type": "string",
                "description": "Opaque entity identifier for an entity read.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

COMMAND_SCHEMA: dict[str, Any] = {
    "name": "muse_universe_command",
    "description": (
        "Submit a versioned, policy-checked M.U.S.E universe command."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command_id": {
                "type": "string",
                "description": "Unique idempotency key for this command intent.",
            },
            "command_type": {
                "type": "string",
                "description": "Supported authoritative command name.",
            },
            "realm_id": {
                "type": "string",
                "description": "Realm whose authority and event log own the command.",
            },
            "actor_id": {
                "type": "string",
                "description": "Caller identity resolved against authoritative state.",
            },
            "expected_version": {
                "type": "integer",
                "minimum": 0,
                "description": "Expected version of the target entity stream.",
            },
            "payload": {
                "type": "object",
                "description": "Command-specific intent without roles or credentials.",
                "additionalProperties": True,
            },
            "approval_id": {
                "type": "string",
                "description": (
                    "Identifier of an existing bound approval grant for a sensitive "
                    "command; never an owner phrase."
                ),
            },
            "simulation": {
                "type": "boolean",
                "description": "Whether the command is isolated simulation state.",
            },
        },
        "required": [
            "command_id",
            "command_type",
            "realm_id",
            "actor_id",
            "expected_version",
            "payload",
        ],
        "additionalProperties": False,
    },
}

__all__ = [
    "AuthorizationDecision",
    "AmbiguousEntityError",
    "CommandIdConflictError",
    "CommandResult",
    "ConflictError",
    "ProvenanceRecord",
    "UniverseCommand",
    "UniverseEvent",
    "UniverseStore",
    "COMMAND_SCHEMA",
    "QUERY_SCHEMA",
    "handle_command",
    "handle_query",
    "handle_slash",
    "register",
]


def handle_query(args: object, **kwargs: object) -> str:
    """Run a read-only model-tool request and return deterministic JSON."""
    home = _tool_home(kwargs)
    return api.response_json(api.query_response(args, home=home))


def handle_command(args: object, **kwargs: object) -> str:
    """Run a versioned model-tool command and return deterministic JSON."""
    home = _tool_home(kwargs)
    return api.response_json(api.command_response(args, home=home))


def handle_slash(raw_args: str) -> str:
    """Inspect status, reconnect events, or agent-vessel reconciliation."""
    try:
        parts = shlex.split(raw_args or "")
    except ValueError:
        return "Usage: /universe [status|events [realm_id] [since]|reconcile]"
    action = parts[0].lower() if parts else "status"
    if not parts:
        parts = ["status"]
    if action == "status" and len(parts) == 1:
        response = api.handle_status(_slash_request("GET", "/status"))
    elif action == "events" and len(parts) <= 3:
        realm_id = parts[1] if len(parts) >= 2 else "rlm_local"
        since = parts[2] if len(parts) == 3 else "0"
        response = api.handle_events(
            _slash_request(
                "GET",
                "/events",
                query={"realm_id": realm_id, "since": since},
            )
        )
    elif action == "reconcile" and len(parts) == 1:
        response = api.handle_reconcile(_slash_request("POST", "/reconcile"))
    else:
        return "Usage: /universe [status|events [realm_id] [since]|reconcile]"
    return api.response_json(response)


def register(ctx: Any) -> None:
    """Register authenticated routes, tools, and the universe slash command."""
    for method, path, handler in api.cockpit_routes():
        ctx.register_cockpit_route(method, path, handler)
    ctx.register_tool(
        name="muse_universe_query",
        toolset="muse-universe",
        schema=QUERY_SCHEMA,
        handler=handle_query,
        description=(
            "Read authoritative M.U.S.E realm, vessel, mission, and civilization "
            "state."
        ),
        emoji="🛰️",
    )
    ctx.register_tool(
        name="muse_universe_command",
        toolset="muse-universe",
        schema=COMMAND_SCHEMA,
        handler=handle_command,
        description=(
            "Submit a versioned, policy-checked M.U.S.E universe command."
        ),
        emoji="🚀",
    )
    ctx.register_command(
        "universe",
        handler=handle_slash,
        description="Inspect M.U.S.E realm and fleet status.",
        args_hint="[status|reconcile|events]",
    )


def _tool_home(kwargs: dict[str, object]) -> str | Path | None:
    home = kwargs.get("hermes_home")
    return home if isinstance(home, (str, Path)) else None


def _slash_request(method: str, path: str, **kwargs: Any):
    from gateway.cockpit.handlers import Request

    return Request(method=method, path=path, **kwargs)
