export const MAX_COMMAND_BYTES = 64 * 1024;
export const MAX_REQUEST_BYTES = MAX_COMMAND_BYTES;
export const MAX_EVENT_PAGE_SIZE = 500;

export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

export type CommandSpec = Readonly<{
  streamType: string;
  eventType: string;
  requiredScope: string;
}>;

export const COMMAND_SPECS: Readonly<Record<string, CommandSpec>> = Object.freeze({
  "realm.create": { streamType: "realm", eventType: "realm.created", requiredScope: "realm:create" },
  "player.create": { streamType: "player", eventType: "player.created", requiredScope: "player:write" },
  "civilization.create": { streamType: "civilization", eventType: "civilization.created", requiredScope: "civilization:write" },
  "membership.invite": { streamType: "membership", eventType: "membership.invited", requiredScope: "membership:invite" },
  "membership.accept": { streamType: "membership", eventType: "membership.accepted", requiredScope: "membership:accept" },
  "presence.update": { streamType: "presence", eventType: "presence.updated", requiredScope: "presence:write" },
  "governance.propose": { streamType: "proposal", eventType: "governance.proposed", requiredScope: "governance:propose" },
  "governance.vote": { streamType: "proposal", eventType: "governance.vote_recorded", requiredScope: "governance:vote" },
  "governance.execute": { streamType: "proposal", eventType: "governance.executed", requiredScope: "governance:execute" },
  "civilization.diplomacy": { streamType: "treaty", eventType: "diplomacy.updated", requiredScope: "diplomacy:write" },
  "moderation.report": { streamType: "moderation_case", eventType: "moderation.reported", requiredScope: "moderation:report" },
  "moderation.block": { streamType: "block", eventType: "moderation.blocked", requiredScope: "moderation:block" },
  "station.create": { streamType: "station", eventType: "station.created", requiredScope: "station:write" },
  "world.create": { streamType: "world", eventType: "world.created", requiredScope: "world:write" },
  "world.region.freeze": { streamType: "world", eventType: "world.region_frozen", requiredScope: "world:freeze" },
  "world.region.regenerate": { streamType: "world", eventType: "world.region_regenerated", requiredScope: "world:regenerate" },
  "building.place": { streamType: "building", eventType: "building.placed", requiredScope: "building:write" },
  "vessel.create": { streamType: "vessel", eventType: "vessel.created", requiredScope: "vessel:write" },
  "vessel.module.install": { streamType: "vessel", eventType: "vessel.module_installed", requiredScope: "vessel:configure" },
  "vessel.cosmetics.update": { streamType: "vessel", eventType: "vessel.cosmetics_updated", requiredScope: "vessel:cosmetics" },
  "fleet.create": { streamType: "fleet", eventType: "fleet.created", requiredScope: "fleet:write" },
  "fleet.assign": { streamType: "fleet", eventType: "fleet.member_assigned", requiredScope: "fleet:assign" },
  "mission.create": { streamType: "mission", eventType: "mission.created", requiredScope: "mission:write" },
  "mission.transition": { streamType: "mission", eventType: "mission.transitioned", requiredScope: "mission:transition" },
  "campaign.create": { streamType: "campaign", eventType: "campaign.created", requiredScope: "campaign:write" },
  "expedition.create": { streamType: "expedition", eventType: "expedition.created", requiredScope: "expedition:write" },
  "blueprint.publish": { streamType: "blueprint", eventType: "blueprint.published", requiredScope: "blueprint:publish" },
  "exchange.listing.publish": { streamType: "exchange_listing", eventType: "exchange.listing_published", requiredScope: "exchange:publish" },
  "exchange.listing.remove": { streamType: "exchange_listing", eventType: "exchange.listing_removed", requiredScope: "exchange:remove" },
  "marketplace.refund": { streamType: "creator_ledger", eventType: "marketplace.refunded", requiredScope: "marketplace:refund" },
  "gallery.publish": { streamType: "gallery_item", eventType: "gallery.published", requiredScope: "gallery:publish" },
  "asset.register": { streamType: "asset", eventType: "asset.registered", requiredScope: "asset:register" },
  "operational_ledger.record": { streamType: "operational_ledger", eventType: "operational.recorded", requiredScope: "operational:record" },
  "creator_ledger.record": { streamType: "creator_ledger", eventType: "creator.recorded", requiredScope: "creator:record" },
  "creator_ledger.transfer": { streamType: "creator_ledger", eventType: "creator.transferred", requiredScope: "creator:transfer" },
  "logistics.update": { streamType: "logistics", eventType: "logistics.updated", requiredScope: "logistics:write" },
  "workspace.lease": { streamType: "workspace_lease", eventType: "workspace.leased", requiredScope: "workspace:lease" },
  "release.stage": { streamType: "release", eventType: "release.staged", requiredScope: "release:stage" },
  "release.promote": { streamType: "release", eventType: "release.promoted", requiredScope: "release:promote" },
  "cinematic_shot.create": { streamType: "cinematic_shot", eventType: "cinematic_shot.created", requiredScope: "cinematic:write" },
  "cinematic_shot.qc": { streamType: "cinematic_shot", eventType: "cinematic_shot.qc_recorded", requiredScope: "cinematic:qc" },
});

export type UniverseCommandInput = Readonly<{
  command_id: string;
  command_type: string;
  realm_id: string;
  stream_id: string;
  expected_version: number;
  payload: Readonly<Record<string, JsonValue>>;
  causation_id?: string;
  correlation_id?: string;
  approval_id?: string;
  simulation: boolean;
}>;

export class ContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ContractError";
  }
}

const OPAQUE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const ALLOWED_FIELDS = new Set([
  "command_id",
  "command_type",
  "realm_id",
  "stream_id",
  "expected_version",
  "payload",
  "causation_id",
  "correlation_id",
  "approval_id",
  "simulation",
]);
const FORBIDDEN_AUTHORITY_FIELDS = new Set([
  "__muse_internal__",
  "actor_id",
  "authorization",
  "owner_authorization",
  "provenance",
  "roles",
  "scopes",
  "stream_type",
]);
const SECRET_KEYS = new Set([
  "apikey",
  "authorization",
  "ownerauthorization",
  "ownerphrase",
  "privatekey",
  "providerkey",
  "token",
]);
const STREAM_ID_FIELDS: Readonly<Record<string, string>> = Object.freeze({
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
});

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function opaqueId(value: unknown, field: string): string {
  if (typeof value !== "string" || !OPAQUE_ID.test(value)) {
    throw new ContractError(`${field} must be an opaque identifier of at most 128 characters`);
  }
  return value;
}

function optionalId(value: unknown, field: string): string | undefined {
  if (value === undefined || value === null) return undefined;
  return opaqueId(value, field);
}

function normalizedKey(key: string): string {
  return key.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function secretLikeKey(key: string): boolean {
  const normalized = normalizedKey(key);
  return SECRET_KEYS.has(normalized)
    || normalized.endsWith("token")
    || /(bearer|cookie|credential|password|passwd|secret)/.test(normalized);
}

function validateJson(value: unknown, path: string, depth = 0): asserts value is JsonValue {
  if (depth > 12) throw new ContractError(`${path} exceeds the maximum nesting depth`);
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new ContractError(`${path} contains a non-finite number`);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => validateJson(item, `${path}[${index}]`, depth + 1));
    return;
  }
  if (isObject(value)) {
    for (const [key, item] of Object.entries(value)) {
      if (secretLikeKey(key)) {
        throw new ContractError(`credential-shaped field is not allowed at ${path}.${key}`);
      }
      validateJson(item, `${path}.${key}`, depth + 1);
    }
    return;
  }
  throw new ContractError(`${path} contains an unsupported JSON value`);
}

export function validateRealmId(value: unknown): string {
  return opaqueId(value, "realm_id");
}

export function parseUniverseCommand(value: unknown): UniverseCommandInput {
  if (!isObject(value)) throw new ContractError("command body must be a JSON object");
  for (const key of Object.keys(value)) {
    if (FORBIDDEN_AUTHORITY_FIELDS.has(key)) {
      throw new ContractError(`${key} is server-authoritative and must not be supplied`);
    }
    if (!ALLOWED_FIELDS.has(key)) throw new ContractError(`unsupported command field: ${key}`);
  }

  const commandId = opaqueId(value.command_id, "command_id");
  const commandType = typeof value.command_type === "string" ? value.command_type : "";
  if (!Object.hasOwn(COMMAND_SPECS, commandType)) {
    throw new ContractError(`unsupported command_type: ${commandType || "<missing>"}`);
  }
  const realmId = opaqueId(value.realm_id, "realm_id");
  if (!isObject(value.payload)) throw new ContractError("payload must be a JSON object");
  const streamField = STREAM_ID_FIELDS[commandType] ?? "id";
  const streamId = value.stream_id === undefined
    ? opaqueId(value.payload[streamField], streamField)
    : opaqueId(value.stream_id, "stream_id");
  if (!Number.isSafeInteger(value.expected_version) || Number(value.expected_version) < 0) {
    throw new ContractError("expected_version must be a non-negative safe integer");
  }
  validateJson(value.payload, "payload");
  if (
    typeof value.payload[streamField] === "string"
    && value.payload[streamField] !== streamId
  ) {
    throw new ContractError(`${streamField} must match stream_id`);
  }
  if (commandType === "realm.create" && streamId !== realmId) {
    throw new ContractError("realm.create stream_id must match realm_id");
  }
  if (value.simulation !== undefined && typeof value.simulation !== "boolean") {
    throw new ContractError("simulation must be a boolean");
  }

  return Object.freeze({
    command_id: commandId,
    command_type: commandType,
    realm_id: realmId,
    stream_id: streamId,
    expected_version: Number(value.expected_version),
    payload: Object.freeze(value.payload as Record<string, JsonValue>),
    causation_id: optionalId(value.causation_id, "causation_id"),
    correlation_id: optionalId(value.correlation_id, "correlation_id"),
    approval_id: optionalId(value.approval_id, "approval_id"),
    simulation: value.simulation === true,
  });
}

export function parseBoundedInteger(
  value: string | null,
  field: string,
  minimum: number,
  maximum: number,
  fallback: number,
): number {
  if (value === null || value === "") return fallback;
  if (!/^(0|[1-9][0-9]*)$/.test(value)) {
    throw new ContractError(`${field} must be an integer`);
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < minimum || parsed > maximum) {
    throw new ContractError(`${field} must be between ${minimum} and ${maximum}`);
  }
  return parsed;
}
