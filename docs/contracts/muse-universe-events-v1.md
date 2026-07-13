# M.U.S.E Universe events v1

Status: **frozen**. This contract defines the authoritative command and event
envelopes shared by local/private realms and network realms. The checked-in
schemas are:

- `plugins/muse_universe/schemas/universe_command.schema.json`
- `plugins/muse_universe/schemas/universe_event.schema.json`
- `plugins/muse_universe/schemas/command_result.schema.json`

The executable freeze specifications live in
`tests/muse_universe/test_replay.py`. New optional fields and new command/event
families may be added compatibly. Existing v1 fields, meanings, command names,
and event names may not be removed, renamed, or repurposed.

## Authority selection

Authority is selected per realm, never per request retry.

- A local/private realm uses the local `UniverseService` and append-only
  `UniverseStore`. The database path is supplied from the active profile's
  Hermes home; callers must not hardcode `~/.hermes`.
- A network/team/public realm uses its configured remote authority. The client
  sends the caller's user credential to that authority; it never sends a
  service-role credential from a client process.
- Loss of the remote authority is an availability failure. A network realm must
  not silently fail over to a local database, because doing so would create two
  conflicting authorities.
- An explicitly separate local realm remains usable while a remote realm is
  unavailable. Its ids, command-id namespace, events, and projections remain
  isolated under that local realm id.

The server resolves identity, membership, scopes, approval grants, and current
versions from authoritative state. Client visuals, badges, rank, currency,
claimed roles, and claimed scopes are never authority.

## Command envelope

`UniverseCommand` is the server-enriched command written to the store. All of
the following are required in v1 except `simulation`, which defaults to
`false`:

| Field | Type | Contract |
|---|---|---|
| `command_id` | string | Idempotency key, unique within one realm. |
| `command_type` | string | Frozen command name from the naming table. |
| `realm_id` | string | Authority and isolation boundary. |
| `actor_id` | string | Authenticated or local-owner identity. |
| `stream_type` | string | Projection family selected by the server. |
| `stream_id` | string | Projection id selected from validated intent. |
| `expected_version` | integer >= 0 | Optimistic concurrency precondition. Booleans and numeric strings are invalid. |
| `payload` | object | Validated domain payload; secret-like keys are forbidden recursively. |
| `authorization` | object | Server decision: `allowed`, `reason`, `scopes`, `owner_gate`. |
| `provenance` | object | `source`, evidence references, confidence, and optional public signature. |
| `causation_id` | string | Direct cause. Public service commands use `command_id`. |
| `correlation_id` | string | End-to-end operation id. Public service commands use `command_id`. |
| `simulation` | boolean | Simulation taint; defaults to `false`. |

Clients submit intent through `UniverseService.execute(...)` or the equivalent
remote endpoint. They do not author the durable `authorization` or
`provenance` objects. An approval id, when required, is a transport-side proof
bound to the exact intent; it is not accepted inside `payload` and is not copied
into an event. Owner phrases are never command fields.

This concrete vector is parsed and model-validated by
`test_documented_json_vectors_are_model_valid_and_test_locked`.

<!-- test-vector:command-v1 -->
```json
{
  "actor_id": "ply_owner",
  "authorization": {
    "allowed": true,
    "owner_gate": "not_required",
    "reason": "local owner",
    "scopes": [
      "*"
    ]
  },
  "causation_id": "cmd_contract_0001",
  "command_id": "cmd_contract_0001",
  "command_type": "realm.create",
  "correlation_id": "cmd_contract_0001",
  "expected_version": 0,
  "payload": {
    "authority": "server",
    "id": "rlm_contract",
    "mode": "local",
    "owner_id": "ply_owner",
    "retention": "owner_controlled",
    "ruleset": "muse-universe-v1",
    "version_policy": "optimistic",
    "visibility": "private"
  },
  "provenance": {
    "confidence": 1.0,
    "evidence": [
      "command:cmd_contract_0001"
    ],
    "signature": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    "source": "universe_service"
  },
  "realm_id": "rlm_contract",
  "simulation": false,
  "stream_id": "rlm_contract",
  "stream_type": "realm"
}
```
<!-- /test-vector:command-v1 -->

## Event envelope

Every accepted command appends one immutable `UniverseEvent`; related writes
append all events in the same transaction. V1 events contain:

| Field | Type | Contract |
|---|---|---|
| `sequence` | integer | Database-wide monotonic cursor; gaps are valid in realm-filtered feeds. |
| `event_id` | string | Globally unique event identity. |
| `schema_version` | integer | `1` for this contract. Serialized events include it even though the model default makes it optional at validation. |
| `event_type` | string | Frozen event name from the naming table. |
| `realm_id` | string | Realm boundary copied from the authoritative command. |
| `actor_id` | string | Authoritative actor identity. |
| `stream_type` | string | Projection family. |
| `stream_id` | string | Projection identity. |
| `stream_version` | integer | Previous stream version plus one. |
| `authorization` | object | Persisted server decision, never a client claim. |
| `causation_id` | string | Immediate cause. |
| `correlation_id` | string | Operation correlation id. |
| `occurred_at` | string | UTC ISO-8601 timestamp. |
| `payload` | object | Validated, secret-free state delta. |
| `provenance` | object | Source and evidence metadata. |
| `simulation` | boolean | Taint propagated into the projection. |
| `rollback` | object | Exact projection immediately before this event, or `{}` for creation. |

The command result contains `event`, the resulting `entity`, and
`idempotent_replay` (default `false`). The latter is response metadata and does
not alter the stored event.

<!-- test-vector:event-v1 -->
```json
{
  "actor_id": "ply_owner",
  "authorization": {
    "allowed": true,
    "owner_gate": "not_required",
    "reason": "local owner",
    "scopes": [
      "*"
    ]
  },
  "causation_id": "cmd_contract_0001",
  "correlation_id": "cmd_contract_0001",
  "event_id": "00000000-0000-4000-8000-000000000001",
  "event_type": "realm.created",
  "occurred_at": "2026-07-12T00:00:00+00:00",
  "payload": {
    "authority": "server",
    "id": "rlm_contract",
    "mode": "local",
    "owner_id": "ply_owner",
    "retention": "owner_controlled",
    "ruleset": "muse-universe-v1",
    "version_policy": "optimistic",
    "visibility": "private"
  },
  "provenance": {
    "confidence": 1.0,
    "evidence": [
      "command:cmd_contract_0001"
    ],
    "signature": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    "source": "universe_service"
  },
  "realm_id": "rlm_contract",
  "rollback": {},
  "schema_version": 1,
  "sequence": 1,
  "simulation": false,
  "stream_id": "rlm_contract",
  "stream_type": "realm",
  "stream_version": 1
}
```
<!-- /test-vector:event-v1 -->

## Naming

Commands use `<domain>.<verb>` names. Events are past-tense facts and are not
instructions. Existing v1 mappings are frozen; adding a new mapping does not
change old mappings.

| Command | Stream | Event |
|---|---|---|
| `realm.create` | `realm` | `realm.created` |
| `player.create` | `player` | `player.created` |
| `civilization.create` | `civilization` | `civilization.created` |
| `membership.invite` | `membership` | `membership.invited` |
| `membership.accept` | `membership` | `membership.accepted` |
| `presence.update` | `presence` | `presence.updated` |
| `governance.propose` | `proposal` | `governance.proposed` |
| `governance.vote` | `proposal` | `governance.vote_recorded` |
| `governance.execute` | `proposal` | `governance.executed` |
| `civilization.diplomacy` | `treaty` | `diplomacy.updated` |
| `moderation.report` | `moderation_case` | `moderation.reported` |
| `moderation.block` | `block` | `moderation.blocked` |
| `station.create` | `station` | `station.created` |
| `world.create` | `world` | `world.created` |
| `world.region.freeze` | `world` | `world.region_frozen` |
| `world.region.regenerate` | `world` | `world.region_regenerated` |
| `building.place` | `building` | `building.placed` |
| `vessel.create` | `vessel` | `vessel.created` |
| `vessel.module.install` | `vessel` | `vessel.module_installed` |
| `vessel.cosmetics.update` | `vessel` | `vessel.cosmetics_updated` |
| `fleet.create` | `fleet` | `fleet.created` |
| `fleet.assign` | `fleet` | `fleet.member_assigned` |
| `mission.create` | `mission` | `mission.created` |
| `mission.transition` | `mission` | `mission.transitioned` |
| `campaign.create` | `campaign` | `campaign.created` |
| `expedition.create` | `expedition` | `expedition.created` |
| `blueprint.publish` | `blueprint` | `blueprint.published` |
| `exchange.listing.publish` | `exchange_listing` | `exchange.listing_published` |
| `exchange.listing.remove` | `exchange_listing` | `exchange.listing_removed` |
| `marketplace.refund` | `creator_ledger` | `marketplace.refunded` |
| `gallery.publish` | `gallery_item` | `gallery.published` |
| `asset.register` | `asset` | `asset.registered` |
| `operational_ledger.record` | `operational_ledger` | `operational.recorded` |
| `creator_ledger.record` | `creator_ledger` | `creator.recorded` |
| `creator_ledger.transfer` | `creator_ledger` | `creator.transferred` |
| `logistics.update` | `logistics` | `logistics.updated` |
| `workspace.lease` | `workspace_lease` | `workspace.leased` |
| `release.stage` | `release` | `release.staged` |
| `release.promote` | `release` | `release.promoted` |
| `cinematic_shot.create` | `cinematic_shot` | `cinematic_shot.created` |
| `cinematic_shot.qc` | `cinematic_shot` | `cinematic_shot.qc_recorded` |

Internal related events, such as `world.building_placed` and
`mission.achievement_evidence_recorded`, obey the same envelope and correlation
rules. Their command ids use the reserved `__muse_internal__:` namespace; public
callers cannot reserve or preempt that namespace.

## Optimistic concurrency

The authority compares `expected_version` with the current version of
`(realm_id, stream_type, stream_id)` inside the same write transaction that
appends the event and updates the projection.

- Creation expects version `0`; its event has `stream_version: 1`.
- A successful mutation increments by exactly one.
- A stale request fails with a conflict carrying both `expected_version` and
  `current_version`.
- The failed transaction writes no event, projection, or command result.
- Related events are atomic: all append and project, or all roll back.

Concurrency is an authority concern, not a client timing convention. Two
writers that both present version `0` cannot both create the same realm-scoped
stream.

## Idempotency

`command_id` is scoped by `realm_id`. The authority stores the accepted result
and an intent fingerprint in the same transaction as the event.

- An exact retry returns the original event id and entity with
  `idempotent_replay: true`; it does not append another event or consume another
  effect.
- Reusing the same realm/command id with different actor, command type, payload,
  expected version, simulation flag, stream, or event meaning is a command-id
  conflict.
- The approval credential is not durable command content. A sensitive retry is
  accepted only by retrieving the already stored exact result; it must not
  re-consume an approval.
- The same command id may be used independently in a different realm.

Idempotency records survive process restart and are part of realm migration.

## Cursors and reconnect

`sequence` is a database-wide monotonic cursor. Event reads are realm-filtered
and return events where `sequence > since`, ordered ascending.

- A reconnect client stores the highest sequence it has durably processed.
- Realm-filtered feeds may contain sequence gaps because other realms share the
  database sequence. Gaps are not data loss.
- A response cursor is the highest sequence returned, or the supplied cursor
  when no event is returned.
- Cursors never authorize cross-realm reads. The authority applies realm
  membership and visibility policy before returning network data.
- Clients must deduplicate by `event_id` and tolerate an exact event being
  delivered again after reconnect.

## Privacy and secret redaction

Secrets, owner phrases, raw credentials, bearer values, cookies, passwords,
private keys, provider keys, and API keys are forbidden recursively in command
payloads, event payloads, rollback metadata, projections, command results, and
errors. Key matching is case/separator normalized and includes token suffixes.
Errors may identify the rejected key path but must never echo its value.

Public signatures and public-key material are allowed when the field is
unambiguously public. An `approval_id` is accepted only as an out-of-band bound
proof and is not event payload data.

Presence is non-authoritative telemetry:

- It cannot carry inventory, capabilities, scopes, roles, currency, or rank.
- Private presence is visible only to the subject and realm owner; private
  position is discarded at write time.
- Crew presence is visible only within an active civilization and is reduced to
  `id`, `status`, `visibility`, and `mode` for other callers.
- Public presence is always reduced to that minimal shape.
- A caller identity is required for service-level presence snapshot/entity
  reads.

## Replay and projections

Events are the source of truth. Replay starts from an empty map, processes
events in sequence order, and reduces each `(stream_type, stream_id)`
independently within its realm.

For every event the reducer overlays the prior projection and payload, then
overwrites these canonical fields from the envelope:

`id`, `entity_type`, `realm_id`, `version`, `updated_at`, `simulation`.

Payload data therefore cannot forge canonical projection metadata. A
`*.deleted` event leaves a `deleted: true` tombstone; it does not erase event
history. Reopening the same database and replaying its events must produce the
same snapshot byte-for-byte at the JSON value level.

Realm isolation applies to streams, projections, command results, snapshots,
and event queries. Identical entity ids and command ids in different realms are
distinct. An unqualified entity lookup that matches multiple realms is
ambiguous and must fail rather than choose one.

## Rollback metadata

`rollback` is `{}` for stream creation. For every later event it is the complete
projection immediately before that event, including canonical metadata. It is
captured and secret-validated in the append transaction.

Rollback metadata is audit evidence, not an instruction to mutate state.
Restoring prior state requires a new authorized, concurrency-checked command so
the restoration itself is visible in history. Consumers must not overwrite a
projection directly from `rollback`.

## Migration and compatibility

V1 readers must accept:

- new optional envelope fields;
- new payload fields that do not weaken redaction or change existing semantics;
- new command/event families; and
- unknown event families that can be retained and skipped by a consumer that
  does not project them.

The following are breaking and require `schema_version: 2`, new checked-in
schemas, explicit up-conversion/dual-read logic, and a documented migration:

- removing or renaming an existing field;
- adding a required field to a v1 envelope;
- changing a field's type or established meaning;
- renaming or repurposing an existing command/event mapping;
- changing realm, stream-version, cursor, idempotency, rollback, or secret
  semantics; or
- allowing simulation state to mutate real/public authority.

Migrations never rewrite accepted event history in place. Projections may be
rebuilt from events. Command idempotency records, realm ids, sequence values,
event ids, and stream versions must be preserved when moving an authority.

## Evidence status

Static contract evidence in this change:

- The model and checked-in schema fields were inspected directly.
- The SQLite schema, transaction order, realm scoping, command fingerprinting,
  replay reducer, privacy filtering, secret validator, and service authorization
  paths were inspected directly.
- Executable specifications cover negative authorization, moderation state,
  privacy, recursive secret rejection, stale writes, two-writer races,
  double-spend prevention, restart replay, rollback chains, realm cursors,
  idempotency, and the frozen JSON vectors above.

Deferred execution evidence:

- Per assignment constraint, no tests, linters, type checkers, builds, quality
  gates, or development servers were run while authoring this contract.
- The focused and complete test suites remain coordinator/CI verification work.
- The remote/Supabase authority described here is a normative compatibility
  requirement; its runtime evidence is deferred until that adapter and its
  deployment environment are available and exercised.
