from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import hermes_cli.approval_grants as approval_grants
from hermes_cli.approval_grants import ApprovalVerifier

from .achievements import AchievementBridge
from .authorization import (
    AuthorizationError,
    approval_required,
    authorize,
    authoritative_scopes,
)
from .catalog import (
    MANDATORY_VESSEL_ROOMS,
    MODULES,
    OPTIONAL_CLASS_ROOMS,
    PLAYER_MODES,
    REQUIRED_ROOMS,
    STATIONS,
    VESSEL_CLASSES,
    catalog_snapshot,
)
from .models import CommandResult, ProvenanceRecord, UniverseCommand
from .store import CommandIdConflictError, UniverseStore


class ValidationError(ValueError):
    """Raised when a domain invariant rejects a command intent."""


COMMANDS: dict[str, tuple[str, str]] = {
    "realm.create": ("realm", "realm.created"),
    "player.create": ("player", "player.created"),
    "civilization.create": ("civilization", "civilization.created"),
    "membership.invite": ("membership", "membership.invited"),
    "membership.accept": ("membership", "membership.accepted"),
    "presence.update": ("presence", "presence.updated"),
    "governance.propose": ("proposal", "governance.proposed"),
    "governance.vote": ("proposal", "governance.vote_recorded"),
    "governance.execute": ("proposal", "governance.executed"),
    "civilization.diplomacy": ("treaty", "diplomacy.updated"),
    "moderation.report": ("moderation_case", "moderation.reported"),
    "moderation.block": ("block", "moderation.blocked"),
    "station.create": ("station", "station.created"),
    "world.create": ("world", "world.created"),
    "world.region.freeze": ("world", "world.region_frozen"),
    "world.region.regenerate": ("world", "world.region_regenerated"),
    "building.place": ("building", "building.placed"),
    "vessel.create": ("vessel", "vessel.created"),
    "vessel.module.install": ("vessel", "vessel.module_installed"),
    "vessel.cosmetics.update": ("vessel", "vessel.cosmetics_updated"),
    "fleet.create": ("fleet", "fleet.created"),
    "fleet.assign": ("fleet", "fleet.member_assigned"),
    "mission.create": ("mission", "mission.created"),
    "mission.transition": ("mission", "mission.transitioned"),
    "campaign.create": ("campaign", "campaign.created"),
    "expedition.create": ("expedition", "expedition.created"),
    "blueprint.publish": ("blueprint", "blueprint.published"),
    "exchange.listing.publish": ("exchange_listing", "exchange.listing_published"),
    "exchange.listing.remove": ("exchange_listing", "exchange.listing_removed"),
    "marketplace.refund": ("creator_ledger", "marketplace.refunded"),
    "gallery.publish": ("gallery_item", "gallery.published"),
    "asset.register": ("asset", "asset.registered"),
    "operational_ledger.record": ("operational_ledger", "operational.recorded"),
    "creator_ledger.record": ("creator_ledger", "creator.recorded"),
    "creator_ledger.transfer": ("creator_ledger", "creator.transferred"),
    "logistics.update": ("logistics", "logistics.updated"),
    "workspace.lease": ("workspace_lease", "workspace.leased"),
    "release.stage": ("release", "release.staged"),
    "release.promote": ("release", "release.promoted"),
    "cinematic_shot.create": ("cinematic_shot", "cinematic_shot.created"),
    "cinematic_shot.qc": ("cinematic_shot", "cinematic_shot.qc_recorded"),
}

VALIDATORS: dict[str, str] = {
    command: "_validate_" + command.replace(".", "_") for command in COMMANDS
}

_STREAM_ID_FIELDS: dict[str, str] = {
    "realm.create": "id",
    "world.region.freeze": "world_id",
    "world.region.regenerate": "world_id",
    "vessel.module.install": "vessel_id",
    "vessel.cosmetics.update": "vessel_id",
    "fleet.assign": "fleet_id",
    "mission.transition": "mission_id",
    "governance.vote": "proposal_id",
    "governance.execute": "proposal_id",
    "exchange.listing.remove": "listing_id",
    "release.promote": "release_id",
    "cinematic_shot.qc": "shot_id",
}
_UNTRUSTED_METADATA = frozenset(
    {
        "approval",
        "approval_id",
        "approval_metadata",
        "owner_approval",
        "owner_phrase",
        "causation_id",
        "correlation_id",
        "authorization",
    }
)
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_PUBLICATION_COMMANDS = frozenset(
    {"blueprint.publish", "exchange.listing.publish", "gallery.publish", "asset.register"}
)
_MISSION_TRANSITIONS = {
    "draft": {"planned", "cancelled"},
    "planned": {"active", "cancelled"},
    "active": {"completed", "failed", "cancelled"},
    "failed": {"planned", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


class UniverseService:
    def __init__(
        self,
        store: UniverseStore,
        *,
        approval_verifier: ApprovalVerifier | None = None,
        achievement_bridge: AchievementBridge | None = None,
        progression_enabled: bool = True,
        public_policy_hook: Callable[[str, dict[str, Any], dict[str, Any]], bool]
        | None = None,
        clock: Callable[[], float] = time.time,
        presence_min_interval: float = 0.25,
    ) -> None:
        self.store = store
        self.approval_verifier = approval_verifier or approval_grants
        self.achievement_bridge = achievement_bridge or AchievementBridge(
            enabled=progression_enabled
        )
        self.public_policy_hook = public_policy_hook
        self.clock = clock
        self.presence_min_interval = presence_min_interval

    def catalog(self) -> dict[str, Any]:
        return catalog_snapshot()

    def snapshot(self, realm_id: str) -> dict[str, list[dict[str, Any]]]:
        return self.store.snapshot(realm_id)

    def entity(
        self, entity_type: str, entity_id: str, realm_id: str | None = None
    ) -> dict[str, Any] | None:
        return self.store.entity(entity_type, entity_id, realm_id)

    def create_local_realm(
        self,
        owner_id: str,
        *,
        realm_id: str = "rlm_local",
        mode: str = "local",
        visibility: str = "private",
    ) -> CommandResult:
        return self.execute(
            "realm.create",
            owner_id,
            realm_id,
            {
                "id": realm_id,
                "owner_id": owner_id,
                "mode": mode,
                "visibility": visibility,
                "ruleset": "muse-universe-v1",
                "retention": "owner_controlled",
            },
            0,
            f"cmd_create_{realm_id}",
        )

    def execute(
        self,
        command_type: str,
        actor_id: str,
        realm_id: str,
        payload: Mapping[str, Any],
        expected_version: int,
        command_id: str,
        approval_id: str | None = None,
        simulation: bool = False,
    ) -> CommandResult:
        if command_type not in COMMANDS:
            raise AuthorizationError(f"unsupported command: {command_type}")
        if not isinstance(payload, Mapping):
            raise ValidationError("payload must be a mapping")
        intent_payload = deepcopy(dict(payload))
        _reject_untrusted_metadata(intent_payload, path="payload")
        if not isinstance(expected_version, int) or expected_version < 0:
            raise ValidationError("expected_version must be a non-negative integer")
        _required_text(command_id, "command_id")
        intent = _approval_subject(
            command_type,
            actor_id,
            realm_id,
            intent_payload,
            expected_version,
            command_id,
            simulation,
        )
        signature = _intent_hash(intent)

        provisional_approval = approval_id
        if provisional_approval is None and approval_required(command_type, intent_payload):
            provisional_approval = "validation-pending"
        decision = authorize(
            self.store,
            command_type,
            actor_id,
            realm_id,
            intent_payload,
            approval_id=provisional_approval,
            simulation=simulation,
        )

        stored = self._stored_result(realm_id, command_id)
        if stored is not None:
            if approval_required(command_type, intent_payload):
                self._verify_approval(approval_id, intent)
            if stored.event.provenance.signature != signature:
                raise CommandIdConflictError(command_id)
            return stored.model_copy(update={"idempotent_replay": True})

        validator_name = VALIDATORS[command_type]
        validator = getattr(self, validator_name)
        normalized = validator(
            actor_id, realm_id, intent_payload, expected_version, simulation
        )
        if command_type in _PUBLICATION_COMMANDS:
            self._apply_public_policy(actor_id, realm_id, normalized)
        if approval_required(command_type, intent_payload):
            self._verify_approval(approval_id, intent)
        if command_type == "mission.transition" and normalized.get("state") == "completed":
            reference = self.achievement_bridge.record_completed_mission(normalized)
            if reference is not None:
                normalized = {**normalized, "achievement_evidence": reference}

        stream_type, event_type = COMMANDS[command_type]
        stream_id = self._stream_id(command_type, realm_id, intent_payload)
        command = UniverseCommand(
            command_id=command_id,
            command_type=command_type,
            realm_id=realm_id,
            actor_id=actor_id,
            stream_type=stream_type,
            stream_id=stream_id,
            expected_version=expected_version,
            payload=normalized,
            authorization=decision,
            provenance=ProvenanceRecord(
                source="universe_service",
                evidence=(f"command:{command_id}",),
                confidence=1.0,
                signature=signature,
            ),
            causation_id=command_id,
            correlation_id=command_id,
            simulation=simulation,
        )
        return self.store.append(command, event_type)

    def _verify_approval(
        self, approval_id: str | None, subject: dict[str, Any]
    ) -> None:
        if not approval_id:
            raise AuthorizationError("owner approval is required")
        try:
            self.approval_verifier.validate_and_consume_approval(
                approval_id,
                str(subject["actor_id"]),
                str(subject["command_type"]),
                str(subject["realm_id"]),
                str(subject["command_id"]),
                subject,
            )
        except Exception as exc:
            raise AuthorizationError("owner approval verification failed") from exc

    def _stored_result(self, realm_id: str, command_id: str) -> CommandResult | None:
        with self.store._connection() as connection:
            row = connection.execute(
                "SELECT result_json FROM command_results WHERE realm_id = ? AND command_id = ?",
                (realm_id, command_id),
            ).fetchone()
        return None if row is None else CommandResult.model_validate_json(row["result_json"])

    def _stream_id(
        self, command_type: str, realm_id: str, payload: dict[str, Any]
    ) -> str:
        field = _STREAM_ID_FIELDS.get(command_type, "id")
        if command_type == "realm.create":
            return realm_id
        return _required_text(payload.get(field), field)

    def _apply_public_policy(
        self, actor_id: str, realm_id: str, payload: dict[str, Any]
    ) -> None:
        realm = self._require_entity("realm", realm_id, realm_id)
        public = realm.get("mode") == "public" or payload.get("visibility") == "public"
        if public and self.public_policy_hook is not None:
            try:
                allowed = self.public_policy_hook(actor_id, realm, payload)
            except Exception as exc:
                raise ValidationError("public age/region policy failed closed") from exc
            if not allowed:
                raise ValidationError("public age/region policy rejected request")

    def _require_entity(
        self, entity_type: str, entity_id: object, realm_id: str
    ) -> dict[str, Any]:
        identifier = _required_text(entity_id, f"{entity_type}_id")
        entity = self.store.entity(entity_type, identifier, realm_id)
        if entity is None:
            raise ValidationError(f"{entity_type} does not exist")
        return entity

    def _validate_realm_create(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        if payload.get("id") != realm or payload.get("owner_id") != actor:
            raise ValidationError("realm id and owner must match trusted arguments")
        if payload.get("mode") not in {"local", "private", "invite_only", "team", "public", "academy", "simulation"}:
            raise ValidationError("realm mode is invalid")
        if payload.get("visibility") not in {"private", "invite_only", "team", "public"}:
            raise ValidationError("realm visibility is invalid")
        return {**payload, "authority": "server", "version_policy": "optimistic"}

    def _validate_player_create(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, realm, version, simulation
        _required_text(payload.get("id"), "id")
        _required_text(payload.get("display_name"), "display_name")
        cleaned = dict(payload)
        for client_progression in ("achievements", "badges", "tier"):
            cleaned.pop(client_progression, None)
        return cleaned

    def _validate_civilization_create(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del realm, version, simulation
        _required_text(payload.get("id"), "id")
        _required_text(payload.get("name"), "name")
        _required_text(payload.get("charter"), "charter")
        governance = _required_mapping(payload.get("governance"), "governance")
        if int(governance.get("quorum", 0)) < 1:
            raise ValidationError("governance quorum must be positive")
        return {**payload, "founder_id": actor}

    def _validate_membership_invite(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        _required_text(payload.get("id"), "id")
        player_id = _required_text(payload.get("player_id"), "player_id")
        civilization_id = _required_text(payload.get("civilization_id"), "civilization_id")
        self._require_entity("civilization", civilization_id, realm)
        scopes = _string_list(payload.get("scopes", []), "scopes")
        inviter_scopes = authoritative_scopes(self.store, actor, realm)
        if "*" not in inviter_scopes and not set(scopes).issubset(inviter_scopes):
            raise AuthorizationError("cannot grant membership scopes the actor lacks")
        normalized = {
            **payload,
            "player_id": player_id,
            "civilization_id": civilization_id,
            "scopes": scopes,
            "status": "invited",
        }
        self._apply_public_policy(actor, realm, normalized)
        return normalized

    def _validate_membership_accept(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        membership = self._require_entity("membership", payload.get("id"), realm)
        if membership.get("player_id") != actor:
            raise AuthorizationError("membership belongs to another actor")
        requested = payload.get("status", "active")
        if requested not in {"active", "removed"}:
            raise ValidationError("membership status transition is invalid")
        if membership.get("status") == "removed":
            raise ValidationError("removed membership cannot be reactivated")
        normalized = {**membership, "status": requested}
        if requested == "active":
            self._apply_public_policy(actor, realm, normalized)
        return normalized

    def _validate_presence_update(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        if payload.get("id") != actor:
            raise AuthorizationError("presence identity must match actor")
        forbidden = {"inventory", "capabilities", "scopes", "roles", "currency", "rank"}
        if forbidden & payload.keys():
            raise ValidationError("presence cannot carry authoritative inventory or capabilities")
        sequence = payload.get("sequence")
        if not isinstance(sequence, int) or sequence < 1:
            raise ValidationError("presence sequence must be a positive integer")
        current = self.store.entity("presence", actor, realm)
        now = float(self.clock())
        if current is not None:
            if sequence <= int(current.get("sequence", 0)):
                raise ValidationError("presence sequence must increase")
            if now - float(current.get("server_timestamp", 0)) < self.presence_min_interval:
                raise ValidationError("presence rate limit exceeded")
        visibility = payload.get("visibility", "realm")
        if visibility not in {"private", "crew", "realm", "public"}:
            raise ValidationError("presence privacy is invalid")
        allowed = {"id", "sequence", "status", "visibility", "mode", "position"}
        normalized = {key: value for key, value in payload.items() if key in allowed}
        if normalized.get("mode") is not None and normalized["mode"] not in PLAYER_MODES:
            raise ValidationError("presence player mode is invalid")
        if visibility == "private":
            normalized.pop("position", None)
        return {**normalized, "server_timestamp": now}

    def _validate_governance_propose(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version, simulation
        _required_text(payload.get("id"), "id")
        self._require_entity("civilization", payload.get("civilization_id"), realm)
        _required_text(payload.get("title"), "title")
        _required_mapping(payload.get("action"), "action")
        deadline = _utc_datetime(payload.get("deadline_utc"), "deadline_utc")
        if deadline <= datetime.now(timezone.utc):
            raise ValidationError("governance deadline must be in the future")
        return {**payload, "state": "open", "votes": [], "executed": False}

    def _validate_governance_vote(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        proposal = self._require_entity("proposal", payload.get("proposal_id"), realm)
        if proposal.get("state") != "open":
            raise ValidationError("governance proposal is closed")
        realm_entity = self._require_entity("realm", realm, realm)
        if realm_entity.get("owner_id") != actor and not self._has_active_civilization_membership(
            actor,
            realm,
            proposal.get("civilization_id"),
            "governance:vote",
        ):
            raise AuthorizationError("governance voter is outside the civilization")
        if datetime.now(timezone.utc) >= _utc_datetime(proposal.get("deadline_utc"), "deadline_utc"):
            raise ValidationError("governance vote deadline has closed")
        choice = payload.get("choice")
        if choice not in {"yes", "no", "abstain"}:
            raise ValidationError("governance vote choice is invalid")
        votes = list(proposal.get("votes", []))
        if any(vote.get("actor_id") == actor for vote in votes if isinstance(vote, dict)):
            raise ValidationError("duplicate governance vote")
        votes.append({"actor_id": actor, "choice": choice})
        return {**proposal, "votes": votes}

    def _validate_governance_execute(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version, simulation
        proposal = self._require_entity("proposal", payload.get("proposal_id"), realm)
        if proposal.get("executed"):
            raise ValidationError("governance proposal was already executed")
        if datetime.now(timezone.utc) < _utc_datetime(proposal.get("deadline_utc"), "deadline_utc"):
            raise ValidationError("governance deadline is still open")
        votes = proposal.get("votes", [])
        yes = sum(vote.get("choice") == "yes" for vote in votes)
        no = sum(vote.get("choice") == "no" for vote in votes)
        civilization = self._require_entity("civilization", proposal.get("civilization_id"), realm)
        quorum = int(civilization.get("governance", {}).get("quorum", 1))
        if len(votes) < quorum or yes <= no:
            raise ValidationError("governance proposal did not pass")
        return {**proposal, "state": "executed", "executed": True, "outcome": "passed"}

    def _validate_civilization_diplomacy(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version, simulation
        _required_text(payload.get("id"), "id")
        source = _required_text(payload.get("from_civilization_id"), "from_civilization_id")
        target = _required_text(payload.get("to_civilization_id"), "to_civilization_id")
        if source == target:
            raise ValidationError("diplomacy requires distinct civilizations")
        self._require_entity("civilization", source, realm)
        self._require_entity("civilization", target, realm)
        if payload.get("status") not in {"proposed", "active", "suspended", "ended"}:
            raise ValidationError("diplomacy status is invalid")
        _required_mapping(payload.get("terms"), "terms")
        return payload

    def _validate_moderation_report(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del realm, version, simulation
        _required_text(payload.get("id"), "id")
        target = _required_text(payload.get("target_id"), "target_id")
        if target == actor:
            raise ValidationError("moderation report target must differ from reporter")
        _required_text(payload.get("reason"), "reason")
        return {**payload, "reporter_id": actor, "status": "open"}

    def _validate_moderation_block(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del realm, version, simulation
        _required_text(payload.get("id"), "id")
        target = _required_text(payload.get("target_id"), "target_id")
        if target == actor:
            raise ValidationError("moderation block target must differ from actor")
        _required_text(payload.get("reason"), "reason")
        return {**payload, "blocker_id": actor, "active": True}

    def _validate_station_create(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        _required_text(payload.get("id"), "id")
        station_type = _required_text(payload.get("station_type"), "station_type")
        station_ids = {station["id"] for station in STATIONS} | {"atlas_crown"}
        if station_type not in station_ids:
            raise ValidationError("station type is not in the authoritative catalog")
        owner_id = _required_text(payload.get("owner_id"), "owner_id")
        if owner_id != actor:
            self._require_entity("civilization", owner_id, realm)
        rooms = _string_list(payload.get("rooms", []), "rooms")
        allowed_rooms = set(REQUIRED_ROOMS) | set(OPTIONAL_CLASS_ROOMS)
        if not set(rooms).issubset(allowed_rooms):
            raise ValidationError("station room is not in the authoritative catalog")
        return {**payload, "rooms": rooms}

    def _validate_world_create(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del realm, version, simulation
        _required_text(payload.get("id"), "id")
        if payload.get("owner_id") != actor:
            raise AuthorizationError("world owner must match actor")
        regions = _string_list(payload.get("regions"), "regions")
        if len(regions) != len(set(regions)):
            raise ValidationError("world regions must be unique")
        budgets = _required_mapping(payload.get("performance_budget"), "performance_budget")
        if any(_number(value, "performance budget") < 0 for value in budgets.values()):
            raise ValidationError("world performance budget cannot be negative")
        navigation = _required_mapping(payload.get("navigation"), "navigation")
        if _number(navigation.get("minimum_clearance"), "minimum_clearance") <= 0:
            raise ValidationError("world navigation clearance must be positive")
        return {**payload, "regions": regions, "frozen_regions": []}

    def _validate_world_region_freeze(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version, simulation
        world = self._require_entity("world", payload.get("world_id"), realm)
        region = _required_text(payload.get("region_id"), "region_id")
        if region not in world.get("regions", []):
            raise ValidationError("world region does not exist")
        frozen = list(world.get("frozen_regions", []))
        if region in frozen:
            raise ValidationError("world region is already frozen")
        frozen.append(region)
        return {**world, "frozen_regions": frozen, "last_region_action": "freeze"}

    def _validate_world_region_regenerate(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version, simulation
        world = self._require_entity("world", payload.get("world_id"), realm)
        region = _required_text(payload.get("region_id"), "region_id")
        if region not in world.get("regions", []):
            raise ValidationError("world region does not exist")
        if region in world.get("frozen_regions", []):
            raise ValidationError("frozen world region cannot be regenerated")
        recipe = _required_mapping(payload.get("recipe"), "recipe")
        return {
            **world,
            "last_region_action": "regenerate",
            "regenerated_region": region,
            "region_recipe": recipe,
            "regeneration_diff": payload.get("diff", {}),
            "regeneration_rollback": payload.get("rollback", {"region_id": region}),
        }

    def _validate_building_place(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        _required_text(payload.get("id"), "id")
        world = self._require_entity("world", payload.get("world_id"), realm)
        if payload.get("expected_world_version") != world.get("version"):
            raise ValidationError("building expected world version is stale")
        owner_id = payload.get("owner_id")
        if owner_id != actor and not self._has_active_civilization_membership(
            actor, realm, owner_id, "building:write"
        ):
            raise AuthorizationError("building ownership does not match actor membership")
        region = _required_text(payload.get("region_id"), "region_id")
        if region not in world.get("regions", []) or region in world.get("frozen_regions", []):
            raise ValidationError("building region is unavailable")
        if payload.get("collision_valid") is not True:
            raise ValidationError("building collision validation failed")
        minimum = _number(
            world.get("navigation", {}).get("minimum_clearance"),
            "world navigation clearance",
        )
        if _number(payload.get("navigation_clearance"), "navigation_clearance") < minimum:
            raise ValidationError("building navigation budget exceeded")
        cost = _required_mapping(payload.get("performance_cost"), "performance_cost")
        budget = world.get("performance_budget", {})
        for name, value in cost.items():
            if _number(value, f"performance cost {name}") > _number(
                budget.get(name, 0), f"performance budget {name}"
            ):
                raise ValidationError("building performance budget exceeded")
        return payload

    def _validate_vessel_create(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del realm, version, simulation
        _required_text(payload.get("id"), "id")
        if payload.get("owner_id") != actor:
            raise AuthorizationError("vessel owner must match actor")
        if payload.get("vessel_class") not in VESSEL_CLASSES:
            raise ValidationError("vessel class is not in the authoritative catalog")
        rooms = _string_list(payload.get("rooms"), "rooms")
        if not set(MANDATORY_VESSEL_ROOMS).issubset(rooms):
            raise ValidationError("vessel is missing a mandatory room")
        if not set(rooms).issubset(set(REQUIRED_ROOMS) | set(OPTIONAL_CLASS_ROOMS)):
            raise ValidationError("vessel contains an unsupported room")
        attachment_points = _string_list(payload.get("attachment_points"), "attachment_points")
        budgets = _required_mapping(payload.get("budgets"), "budgets")
        for name in ("power", "heat", "compute", "context"):
            if _number(budgets.get(name), f"vessel {name} budget") < 0:
                raise ValidationError("vessel budgets cannot be negative")
        modules = _string_list(payload.get("installed_modules", []), "installed_modules")
        if any(module_id not in MODULES for module_id in modules):
            raise ValidationError("vessel contains an unknown module")
        licenses = _string_list(payload.get("allowed_licenses"), "allowed_licenses")
        return {
            **payload,
            "rooms": rooms,
            "attachment_points": attachment_points,
            "installed_modules": modules,
            "allowed_licenses": licenses,
            "budget_usage": _module_usage(modules),
        }

    def _validate_vessel_module_install(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        vessel = self._require_entity("vessel", payload.get("vessel_id"), realm)
        module_id = _required_text(payload.get("module_id"), "module_id")
        module = MODULES.get(module_id)
        if module is None:
            raise ValidationError("vessel module is not in the authoritative catalog")
        if vessel.get("owner_id") != actor:
            scopes = authoritative_scopes(self.store, actor, realm)
            if "vessel:configure:any" not in scopes and "*" not in scopes:
                raise AuthorizationError("vessel module scope does not cover this vessel")
        attachment = _required_text(payload.get("attachment_type"), "attachment_type")
        if attachment not in module["attachment_types"]:
            raise ValidationError("vessel module attachment is incompatible")
        if attachment not in vessel.get("attachment_points", []):
            raise ValidationError("vessel has no compatible attachment point")
        installed = list(vessel.get("installed_modules", []))
        if module_id in installed:
            raise ValidationError("vessel module is already installed")
        if not set(module["requires"]).issubset(installed):
            raise ValidationError("vessel module requirements are not installed")
        if set(module["conflicts"]) & set(installed):
            raise ValidationError("vessel module conflicts with installed configuration")
        if vessel.get("path_reachable") is not True:
            raise ValidationError("vessel module path is not reachable")
        if module["license"] not in vessel.get("allowed_licenses", []):
            raise ValidationError("vessel module license is not allowed")
        usage = _module_usage([*installed, module_id])
        for name, value in usage.items():
            if value > _number(vessel.get("budgets", {}).get(name), f"vessel {name} budget"):
                raise ValidationError(f"vessel module {name} budget exceeded")
        scopes = authoritative_scopes(self.store, actor, realm)
        if "*" not in scopes and not set(module["capabilities"]).issubset(scopes):
            raise AuthorizationError("vessel module capability scope is missing")
        installed.append(module_id)
        return {
            **vessel,
            "installed_modules": installed,
            "budget_usage": usage,
            "last_module_id": module_id,
        }

    def _validate_vessel_cosmetics_update(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        vessel = self._require_entity("vessel", payload.get("vessel_id"), realm)
        if vessel.get("owner_id") != actor:
            raise AuthorizationError("vessel cosmetics ownership does not match actor")
        forbidden = {"modules", "installed_modules", "capabilities", "budgets", "scopes"}
        if forbidden & payload.keys():
            raise ValidationError("vessel cosmetics cannot alter function")
        cosmetics = _required_mapping(payload.get("cosmetics"), "cosmetics")
        return {**vessel, "cosmetics": cosmetics}

    def _validate_fleet_create(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        _required_text(payload.get("id"), "id")
        if payload.get("owner_id") != actor:
            raise AuthorizationError("fleet owner must match actor")
        members = _string_list(payload.get("members", []), "members")
        if len(members) != len(set(members)):
            raise ValidationError("fleet members must be unique")
        for vessel_id in members:
            self._require_entity("vessel", vessel_id, realm)
        dependencies = payload.get("dependencies", [])
        _validate_dependency_graph(members, dependencies)
        return {**payload, "members": members, "dependencies": dependencies}

    def _validate_fleet_assign(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        fleet = self._require_entity("fleet", payload.get("fleet_id"), realm)
        if fleet.get("owner_id") != actor:
            raise AuthorizationError("fleet assignment ownership does not match actor")
        vessel_id = _required_text(payload.get("vessel_id"), "vessel_id")
        self._require_entity("vessel", vessel_id, realm)
        members = list(fleet.get("members", []))
        if vessel_id in members:
            raise ValidationError("fleet vessel is already assigned")
        members.append(vessel_id)
        return {**fleet, "members": members}

    def _validate_mission_create(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, realm, version
        _required_text(payload.get("id"), "id")
        _required_text(payload.get("source_type"), "source_type")
        _required_text(payload.get("source_id"), "source_id")
        mode = payload.get("mode", "simulation" if simulation else "real")
        if mode not in {"real", "simulation"} or (simulation and mode != "simulation"):
            raise ValidationError("mission simulation mode is inconsistent")
        return {**payload, "mode": mode, "state": "draft", "evidence": []}

    def _validate_mission_transition(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version
        mission = self._require_entity("mission", payload.get("mission_id"), realm)
        if simulation and mission.get("mode") != "simulation":
            raise AuthorizationError("simulation cannot transition a real mission")
        current = mission.get("state")
        target = payload.get("to_state")
        if target not in _MISSION_TRANSITIONS.get(str(current), set()):
            raise ValidationError("mission transition is invalid")
        normalized = {**mission, "state": target}
        if target == "completed":
            evidence = _string_list(payload.get("evidence"), "evidence")
            if not evidence:
                raise ValidationError("completed mission requires evidence")
            normalized["evidence"] = evidence
            if mission.get("mode") == "simulation":
                if payload.get("evidence_label") != "simulation":
                    raise ValidationError("simulation evidence must be explicitly labeled")
                normalized["evidence_label"] = "simulation"
        return normalized

    def _validate_campaign_create(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version, simulation
        _required_text(payload.get("id"), "id")
        _required_text(payload.get("name"), "name")
        missions = _string_list(payload.get("mission_ids", []), "mission_ids")
        for mission_id in missions:
            self._require_entity("mission", mission_id, realm)
        return {**payload, "mission_ids": missions, "state": "planned"}

    def _validate_expedition_create(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version, simulation
        _required_text(payload.get("id"), "id")
        _required_text(payload.get("destination_id"), "destination_id")
        fleet_id = _required_text(payload.get("fleet_id"), "fleet_id")
        self._require_entity("fleet", fleet_id, realm)
        mission_ids = _string_list(payload.get("mission_ids", []), "mission_ids")
        for mission_id in mission_ids:
            self._require_entity("mission", mission_id, realm)
        return {**payload, "mission_ids": mission_ids, "state": "planned"}

    def _validate_blueprint_publish(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, realm, version, simulation
        _required_text(payload.get("id"), "id")
        _validate_creator_package(payload)
        dependencies = payload.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise ValidationError("blueprint dependencies must be a list")
        compatibility = payload.get("compatibility", {})
        if not isinstance(compatibility, Mapping):
            raise ValidationError("blueprint compatibility must be a mapping")
        return {**payload, "published": True}

    def _validate_exchange_listing_publish(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version, simulation
        _required_text(payload.get("id"), "id")
        subject_type = payload.get("subject_type")
        if subject_type not in {"asset", "blueprint"}:
            raise ValidationError("exchange listing subject type is invalid")
        subject_id = _required_text(payload.get("subject_id"), "subject_id")
        self._require_entity(subject_type, subject_id, realm)
        if _number(payload.get("quantity"), "listing quantity") <= 0:
            raise ValidationError("exchange listing quantity must be positive")
        if _number(payload.get("price", 0), "listing price") < 0:
            raise ValidationError("exchange listing price cannot be negative")
        _validate_creator_package(payload)
        return {**payload, "visibility": "public", "status": "active"}

    def _validate_exchange_listing_remove(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version, simulation
        listing = self._require_entity("exchange_listing", payload.get("listing_id"), realm)
        if listing.get("status") != "active":
            raise ValidationError("exchange listing is not active")
        _required_text(payload.get("reason"), "reason")
        return {**listing, "status": "removed", "removal_reason": payload["reason"]}

    def _validate_marketplace_refund(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version, simulation
        _required_text(payload.get("id"), "id")
        transfer = self._require_entity("creator_ledger", payload.get("transfer_id"), realm)
        if transfer.get("transaction_type") != "transfer":
            raise ValidationError("marketplace refund requires a creator transfer")
        prior_refunds = self.store.snapshot(realm).get("creator_ledgers", [])
        if transfer.get("refunded") or any(
            item.get("transaction_type") == "refund"
            and item.get("transfer_id") == transfer.get("id")
            for item in prior_refunds
        ):
            raise ValidationError("marketplace transfer was already refunded")
        _required_text(payload.get("reason"), "reason")
        entries = transfer.get("entries", [])
        if len(entries) != 2:
            raise ValidationError("creator transfer does not preserve both ledger sides")
        reversed_entries = [
            {"owner_id": entry["owner_id"], "quantity": -entry["quantity"]}
            for entry in reversed(entries)
        ]
        return {
            **payload,
            "asset_id": transfer.get("asset_id"),
            "entries": reversed_entries,
            "transaction_type": "refund",
        }

    def _validate_gallery_publish(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, realm, version, simulation
        _required_text(payload.get("id"), "id")
        _validate_creator_package(payload)
        return {**payload, "published": True}

    def _validate_asset_register(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, realm, version, simulation
        _required_text(payload.get("id"), "id")
        _validate_creator_package(payload)
        return {**payload, "registered": True}

    def _validate_operational_ledger_record(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, realm, version, simulation
        _required_text(payload.get("id"), "id")
        _required_text(payload.get("provider"), "provider")
        if _number(payload.get("compute_seconds"), "compute_seconds") < 0:
            raise ValidationError("operational compute cannot be negative")
        if _number(payload.get("cost_usd"), "cost_usd") < 0:
            raise ValidationError("operational cost cannot be negative")
        if {"asset_id", "quantity", "from_id", "to_id"} & payload.keys():
            raise ValidationError("operational ledger cannot contain creator entries")
        return {**payload, "ledger_kind": "operational"}

    def _validate_creator_ledger_record(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del realm, version, simulation
        _required_text(payload.get("id"), "id")
        _required_text(payload.get("asset_id"), "asset_id")
        owner = _required_text(payload.get("owner_id", actor), "owner_id")
        quantity = _number(payload.get("quantity"), "creator quantity")
        if quantity <= 0:
            raise ValidationError("creator quantity must be positive")
        if {"provider", "compute_seconds", "cost_usd", "storage_bytes"} & payload.keys():
            raise ValidationError("creator ledger cannot contain operational fields")
        return {
            **payload,
            "owner_id": owner,
            "quantity": quantity,
            "entries": [{"owner_id": owner, "quantity": quantity}],
            "transaction_type": "record",
            "ledger_kind": "creator",
        }

    def _validate_creator_ledger_transfer(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        _required_text(payload.get("id"), "id")
        asset_id = _required_text(payload.get("asset_id"), "asset_id")
        source = _required_text(payload.get("from_id"), "from_id")
        target = _required_text(payload.get("to_id"), "to_id")
        if source == target:
            raise ValidationError("creator transfer requires distinct ledger sides")
        if source != actor:
            raise AuthorizationError("creator transfer source must match actor")
        quantity = _number(payload.get("quantity"), "creator transfer quantity")
        if quantity <= 0:
            raise ValidationError("creator transfer quantity must be positive")
        if self._creator_balance(realm, source, asset_id) < quantity:
            raise ValidationError("creator transfer has insufficient balance")
        return {
            **payload,
            "entries": [
                {"owner_id": source, "quantity": -quantity},
                {"owner_id": target, "quantity": quantity},
            ],
            "transaction_type": "transfer",
            "ledger_kind": "creator",
        }

    def _creator_balance(self, realm: str, owner_id: str, asset_id: str) -> float:
        total = 0.0
        for entry in self.store.snapshot(realm).get("creator_ledgers", []):
            if entry.get("asset_id") != asset_id:
                continue
            for side in entry.get("entries", []):
                if side.get("owner_id") == owner_id:
                    total += float(side.get("quantity", 0))
        return total

    def _validate_logistics_update(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, realm, version
        _required_text(payload.get("id"), "id")
        kind = payload.get("kind")
        if kind not in {"game", "simulation", "operational"}:
            raise ValidationError("logistics kind is invalid")
        if simulation and kind == "operational":
            raise AuthorizationError("simulation cannot alter operational logistics")
        _required_text(payload.get("resource"), "resource")
        if _number(payload.get("quantity"), "logistics quantity") < 0:
            raise ValidationError("logistics quantity cannot be negative")
        if kind != "operational" and {"cost_usd", "provider"} & payload.keys():
            raise ValidationError("game logistics cannot disguise operational cost")
        return payload

    def _validate_workspace_lease(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del version, simulation
        _required_text(payload.get("id"), "id")
        _required_text(payload.get("provider"), "provider")
        _required_text(payload.get("project_id"), "project_id")
        if _number(payload.get("cost_usd", 0), "workspace cost") < 0:
            raise ValidationError("workspace cost cannot be negative")
        if _utc_datetime(payload.get("expiry_utc"), "expiry_utc") <= datetime.now(timezone.utc):
            raise ValidationError("workspace expiry must be in the future")
        _required_text(payload.get("checkpoint"), "checkpoint")
        preview = _required_text(payload.get("signed_preview"), "signed_preview")
        if not _HASH.fullmatch(preview):
            raise ValidationError("workspace signed preview hash is invalid")
        self._apply_public_policy(actor, realm, payload)
        return {**payload, "status": "leased"}

    def _has_active_civilization_membership(
        self,
        actor_id: str,
        realm_id: str,
        civilization_id: object,
        required_scope: str,
    ) -> bool:
        for membership in self.store.snapshot(realm_id).get("memberships", []):
            if (
                membership.get("player_id") == actor_id
                and membership.get("civilization_id") == civilization_id
                and membership.get("status") == "active"
                and required_scope in membership.get("scopes", ())
            ):
                return True
        return False

    def _validate_release_stage(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, realm, version, simulation
        _required_text(payload.get("id"), "id")
        _required_text(payload.get("artifact_id"), "artifact_id")
        _required_text(payload.get("target"), "target")
        verification = _required_mapping(payload.get("verification"), "verification")
        if verification.get("status") != "passed" or not verification.get("evidence"):
            raise ValidationError("release verification evidence must pass")
        _required_mapping(payload.get("rollback"), "rollback")
        return {**payload, "status": "staged"}

    def _validate_release_promote(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version, simulation
        release = self._require_entity("release", payload.get("release_id"), realm)
        if release.get("status") != "staged":
            raise ValidationError("release is not staged")
        target = _required_text(payload.get("target"), "target")
        if target != release.get("target"):
            raise ValidationError("release promotion target does not match stage")
        return {**release, "status": "promoted", "promoted_target": target}

    def _validate_cinematic_shot_create(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, realm, version, simulation
        _required_text(payload.get("id"), "id")
        _required_text(payload.get("scene_id"), "scene_id")
        cameras = payload.get("cameras")
        if not isinstance(cameras, list) or not cameras:
            raise ValidationError("cinematic shot requires cameras")
        _required_mapping(payload.get("lens"), "lens")
        stereo = _required_mapping(payload.get("stereo"), "stereo")
        if _number(stereo.get("interaxial_mm"), "interaxial_mm") <= 0:
            raise ValidationError("cinematic stereo interaxial must be positive")
        if _number(stereo.get("convergence_m"), "convergence_m") <= 0:
            raise ValidationError("cinematic stereo convergence must be positive")
        render = _required_mapping(payload.get("render_config"), "render_config")
        _required_text(render.get("version"), "render config version")
        return {**payload, "qc_status": "pending"}

    def _validate_cinematic_shot_qc(
        self, actor: str, realm: str, payload: dict[str, Any], version: int, simulation: bool
    ) -> dict[str, Any]:
        del actor, version, simulation
        shot = self._require_entity("cinematic_shot", payload.get("shot_id"), realm)
        status = payload.get("status")
        if status not in {"passed", "failed"}:
            raise ValidationError("cinematic QC status is invalid")
        checks = _required_mapping(payload.get("checks"), "checks")
        evidence = _string_list(payload.get("evidence"), "evidence")
        if not evidence:
            raise ValidationError("cinematic QC requires evidence")
        all_passed = all(value == "passed" for value in checks.values())
        if (status == "passed") != all_passed:
            raise ValidationError("cinematic QC status contradicts checks")
        return {**shot, "qc_status": status, "qc_checks": checks, "qc_evidence": evidence}


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    return value.strip()


def _required_mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise ValidationError(f"{field} keys must be strings")
    return {str(key): item for key, item in value.items()}


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValidationError(f"{field} must be a list of strings")
    return [item for item in value if isinstance(item, str)]


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")
    return float(value)


def _utc_datetime(value: object, field: str) -> datetime:
    text = _required_text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValidationError(f"{field} must be UTC")
    return parsed


def _validate_creator_package(payload: Mapping[str, Any]) -> None:
    for field in ("license", "content_hash", "provenance", "verification", "moderation"):
        if field not in payload:
            raise ValidationError(f"creator package requires {field}")
    _required_text(payload.get("license"), "license")
    content_hash = _required_text(payload.get("content_hash"), "content_hash")
    if not _HASH.fullmatch(content_hash):
        raise ValidationError("content_hash must be a full sha256 digest")
    provenance = _required_mapping(payload.get("provenance"), "provenance")
    _required_text(provenance.get("source"), "provenance source")
    if not _string_list(provenance.get("evidence"), "provenance evidence"):
        raise ValidationError("provenance evidence is required")
    verification = _required_mapping(payload.get("verification"), "verification")
    if verification.get("status") != "passed":
        raise ValidationError("verification must pass")
    moderation = _required_mapping(payload.get("moderation"), "moderation")
    if moderation.get("status") != "approved":
        raise ValidationError("moderation must approve creator content")


def _module_usage(module_ids: list[str]) -> dict[str, float]:
    return {
        name: sum(float(MODULES[module_id][name]) for module_id in module_ids)
        for name in ("power", "heat", "compute", "context")
    }


def _validate_dependency_graph(nodes: list[str], dependencies: object) -> None:
    if not isinstance(dependencies, list):
        raise ValidationError("fleet dependencies must be a list")
    graph = {node: set() for node in nodes}
    for edge in dependencies:
        if not isinstance(edge, Mapping):
            raise ValidationError("fleet dependency must be a mapping")
        source = edge.get("from")
        target = edge.get("to")
        if (
            not isinstance(source, str)
            or not isinstance(target, str)
            or source not in graph
            or target not in graph
            or source == target
        ):
            raise ValidationError("fleet dependency references invalid members")
        graph[source].add(target)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValidationError("fleet dependency graph contains a cycle")
        if node in visited:
            return
        visiting.add(node)
        for target in graph[node]:
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in nodes:
        visit(node)


def _reject_untrusted_metadata(value: object, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if normalized in _UNTRUSTED_METADATA:
                raise ValidationError(f"untrusted metadata is not allowed in {path}")
            _reject_untrusted_metadata(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_untrusted_metadata(item, path=f"{path}[{index}]")


def _approval_subject(
    command_type: str,
    actor_id: str,
    realm_id: str,
    payload: dict[str, Any],
    expected_version: int,
    command_id: str,
    simulation: bool,
) -> dict[str, Any]:
    return {
        "command_id": command_id,
        "command_type": command_type,
        "actor_id": actor_id,
        "realm_id": realm_id,
        "expected_version": expected_version,
        "payload": payload,
        "simulation": simulation,
    }


def _intent_hash(intent: Mapping[str, Any]) -> str:
    encoded = json.dumps(intent, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
