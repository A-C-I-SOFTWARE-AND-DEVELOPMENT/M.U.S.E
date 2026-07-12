from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .catalog import MODULES
from .models import AuthorizationDecision
from .store import UniverseStore


class AuthorizationError(PermissionError):
    """Raised when authoritative realm policy denies a command."""


COMMAND_SCOPES: dict[str, str] = {
    "realm.create": "realm:create",
    "player.create": "player:write",
    "civilization.create": "civilization:write",
    "membership.invite": "membership:invite",
    "membership.accept": "membership:accept",
    "presence.update": "presence:write",
    "governance.propose": "governance:propose",
    "governance.vote": "governance:vote",
    "governance.execute": "governance:execute",
    "civilization.diplomacy": "diplomacy:write",
    "moderation.report": "moderation:report",
    "moderation.block": "moderation:block",
    "station.create": "station:write",
    "world.create": "world:write",
    "world.region.freeze": "world:freeze",
    "world.region.regenerate": "world:regenerate",
    "building.place": "building:write",
    "vessel.create": "vessel:write",
    "vessel.module.install": "vessel:configure",
    "vessel.cosmetics.update": "vessel:cosmetics",
    "fleet.create": "fleet:write",
    "fleet.assign": "fleet:assign",
    "mission.create": "mission:write",
    "mission.transition": "mission:transition",
    "campaign.create": "campaign:write",
    "expedition.create": "expedition:write",
    "blueprint.publish": "blueprint:publish",
    "exchange.listing.publish": "exchange:publish",
    "exchange.listing.remove": "exchange:remove",
    "marketplace.refund": "marketplace:refund",
    "gallery.publish": "gallery:publish",
    "asset.register": "asset:register",
    "operational_ledger.record": "operational:record",
    "creator_ledger.record": "creator:record",
    "creator_ledger.transfer": "creator:transfer",
    "logistics.update": "logistics:write",
    "workspace.lease": "workspace:lease",
    "release.stage": "release:stage",
    "release.promote": "release:promote",
    "cinematic_shot.create": "cinematic:write",
    "cinematic_shot.qc": "cinematic:qc",
}

_ALWAYS_SENSITIVE = frozenset(
    {
        "exchange.listing.publish",
        "exchange.listing.remove",
        "marketplace.refund",
        "release.promote",
        "world.region.regenerate",
    }
)
_PUBLIC_COMMANDS = frozenset(
    {"blueprint.publish", "gallery.publish", "asset.register"}
)
_SIMULATION_REAL_MUTATIONS = frozenset(
    {"release.promote", "workspace.lease", "exchange.listing.publish"}
)


def approval_required(command_type: str, payload: Mapping[str, Any]) -> bool:
    if command_type in _ALWAYS_SENSITIVE:
        return True
    if command_type in _PUBLIC_COMMANDS and payload.get("visibility") == "public":
        return True
    if command_type == "workspace.lease":
        return payload.get("provider") != "local" and float(payload.get("cost_usd", 0)) > 0
    if command_type == "vessel.module.install":
        module = MODULES.get(str(payload.get("module_id", "")))
        return bool(module and module["capabilities"])
    return False


def authoritative_scopes(
    store: UniverseStore, actor_id: str, realm_id: str
) -> tuple[str, ...]:
    realm = store.entity("realm", realm_id, realm_id)
    if realm is not None and realm.get("owner_id") == actor_id:
        return ("*",)

    memberships = store.snapshot(realm_id).get("memberships", [])
    for membership in memberships:
        if membership.get("player_id") != actor_id:
            continue
        if membership.get("realm_id") != realm_id:
            raise AuthorizationError("membership realm mismatch")
        if membership.get("status") != "active":
            raise AuthorizationError("actor has no active membership")
        scopes = membership.get("scopes", [])
        if not isinstance(scopes, (list, tuple)):
            raise AuthorizationError("membership scopes are invalid")
        return tuple(str(scope) for scope in scopes)

    for other_realm in _realms_with_membership(store, actor_id):
        if other_realm != realm_id:
            raise AuthorizationError("membership realm mismatch")
    raise AuthorizationError("actor has no active membership scope")


def authorize(
    store: UniverseStore,
    command_type: str,
    actor_id: str,
    realm_id: str,
    payload: Mapping[str, Any],
    *,
    approval_id: str | None = None,
    simulation: bool = False,
) -> AuthorizationDecision:
    required_scope = COMMAND_SCOPES.get(command_type)
    if required_scope is None:
        raise AuthorizationError(f"unsupported command: {command_type}")
    if not actor_id or not realm_id:
        raise AuthorizationError("actor and realm are required")
    if simulation and (
        command_type in _SIMULATION_REAL_MUTATIONS
        or (command_type in _PUBLIC_COMMANDS and payload.get("visibility") == "public")
    ):
        raise AuthorizationError("simulation cannot mutate real or public state")

    if command_type == "realm.create":
        if store.entity("realm", realm_id, realm_id) is not None:
            raise AuthorizationError("realm already exists")
        if payload.get("owner_id") != actor_id:
            raise AuthorizationError("realm owner must match actor")
        scopes = ("*",)
    elif command_type == "membership.accept" and _is_self_membership_action(
        store, actor_id, realm_id, payload
    ):
        scopes = ("membership:accept",)
    else:
        scopes = authoritative_scopes(store, actor_id, realm_id)

    if "*" not in scopes and required_scope not in scopes:
        raise AuthorizationError(f"missing required scope: {required_scope}")
    if approval_required(command_type, payload) and not approval_id:
        raise AuthorizationError(f"owner approval required for {command_type}")
    return AuthorizationDecision(
        allowed=True,
        reason="local owner" if "*" in scopes else "active realm membership",
        scopes=scopes,
        owner_gate="required" if approval_required(command_type, payload) else "not_required",
    )


def _is_self_membership_action(
    store: UniverseStore,
    actor_id: str,
    realm_id: str,
    payload: Mapping[str, Any],
) -> bool:
    membership_id = payload.get("id")
    if not isinstance(membership_id, str):
        return False
    membership = store.entity("membership", membership_id, realm_id)
    return bool(
        membership
        and membership.get("player_id") == actor_id
        and membership.get("status") in {"invited", "active"}
    )


def _realms_with_membership(store: UniverseStore, actor_id: str) -> set[str]:
    realms: set[str] = set()
    with store._connection() as connection:  # authoritative cross-realm lookup
        rows = connection.execute(
            "SELECT realm_id, entity_json FROM entities WHERE entity_type = 'membership'"
        ).fetchall()
    import json

    for row in rows:
        membership = json.loads(row["entity_json"])
        if membership.get("player_id") == actor_id:
            realms.add(str(row["realm_id"]))
    return realms
