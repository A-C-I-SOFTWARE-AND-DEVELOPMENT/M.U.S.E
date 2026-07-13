export type DeckId = 'crown' | 'flight' | 'foundry' | 'observatory' | 'embassy';

export type StationId =
  | 'atlas-crown'
  | 'neural-shipyard'
  | 'deep-observatory'
  | 'fabrication-foundry'
  | 'cinema-array'
  | 'game-foundry'
  | 'memory-archive'
  | 'quarantine-moon'
  | 'relay-embassy'
  | 'academy-station'
  | 'blueprint-exchange'
  | 'release-dock';

export type RoomId =
  | 'command-bridge'
  | 'neural-chamber'
  | 'sensor-laboratory'
  | 'fabrication-bay'
  | 'memory-vault'
  | 'drone-hangar'
  | 'engineering'
  | 'security-airlock'
  | 'governance-chamber'
  | 'cinema-array'
  | 'game-foundry'
  | 'release-dock'
  | 'shipyard'
  | 'relay-embassy'
  | 'production-command'
  | 'crew-observation';

export type SceneKind =
  | 'atlas-crown'
  | 'neural-core'
  | 'station-room'
  | 'vessel-exterior'
  | 'vessel-interior'
  | 'celestial-map';

export type VesselClassId =
  | 'scout'
  | 'surveyor'
  | 'forge'
  | 'director'
  | 'carrier'
  | 'diplomat'
  | 'sentinel'
  | 'courier'
  | 'flagship';

export type PlayerMode = 'walk' | 'pilot' | 'fleet' | 'director';

export interface AuthorizationDecision {
  allowed: boolean;
  reason: string;
  scopes: string[];
  owner_gate: string;
}

export interface ProvenanceRecord {
  source: string;
  evidence: string[];
  confidence: number;
  signature: string | null;
}

export interface UniverseCommand {
  command_id: string;
  command_type: string;
  realm_id: string;
  actor_id: string;
  stream_type: string;
  stream_id: string;
  expected_version: number;
  payload: Record<string, unknown>;
  authorization: AuthorizationDecision;
  provenance: ProvenanceRecord;
  causation_id: string;
  correlation_id: string;
  simulation: boolean;
  approval_id?: string;
}

export interface UniverseEvent {
  sequence: number;
  event_id: string;
  schema_version: number;
  event_type: string;
  realm_id: string;
  actor_id: string;
  stream_type: string;
  stream_id: string;
  stream_version: number;
  authorization: AuthorizationDecision;
  causation_id: string;
  correlation_id: string;
  occurred_at: string;
  payload: Record<string, unknown>;
  provenance: ProvenanceRecord;
  simulation: boolean;
  rollback: Record<string, unknown>;
}

export interface UniverseEntity {
  id: string;
  entity_type: string;
  realm_id: string;
  version: number;
  updated_at: string;
  simulation: boolean;
  deleted?: boolean;
  status?: string;
  name?: string;
  [key: string]: unknown;
}

export interface AgentBinding {
  agent_id?: string;
  model_routing?: unknown;
  capabilities?: string[];
  permission_scopes?: string[];
  audit_ref?: string;
  state?: string;
}

export interface Vessel extends UniverseEntity {
  entity_type: 'vessel';
  class?: VesselClassId;
  vessel_class?: VesselClassId;
  owner_id?: string;
  rooms?: string[];
  installed_modules?: string[];
  cosmetics?: { paint?: string; name?: string; markings?: string };
  agent_binding?: AgentBinding;
  path_reachable?: boolean;
  degraded_fields?: string[];
}

export interface Civilization extends UniverseEntity {
  entity_type: 'civilization';
  charter?: string;
  governance?: Record<string, unknown>;
  owner_id?: string;
}

export interface Mission extends UniverseEntity {
  entity_type: 'mission';
  state?: 'draft' | 'planned' | 'active' | 'completed' | 'failed' | 'cancelled';
  source_type?: string;
  source_id?: string;
  mode?: 'real' | 'simulation';
  evidence?: string[];
}

export interface WorkspaceLease extends UniverseEntity {
  entity_type: 'workspace_lease';
  project_id?: string;
  revision?: string;
  expires_at?: string;
  preview_url?: string;
  verification?: Record<string, unknown>;
}

export interface CinematicShot extends UniverseEntity {
  entity_type: 'cinematic_shot';
  scene_id?: string;
  camera_ids?: string[];
  interaxial_m?: number;
  convergence_m?: number;
  zero_parallax_m?: number;
  focal_length_mm?: number;
  qc?: Record<string, unknown>;
}

export interface ReleaseRecord extends UniverseEntity {
  entity_type: 'release';
  project_id?: string;
  state?:
    | 'draft'
    | 'verified'
    | 'staged'
    | 'awaiting_owner'
    | 'publishing'
    | 'live'
    | 'failed'
    | 'rolled_back';
  visibility?: string;
  gates?: Record<string, unknown>;
  deployment_id?: string;
  public_url?: string;
  previous_version?: string;
  approval_id?: string;
}

export interface UniverseViewer {
  actor_id: string;
  display_name?: string;
  scopes: string[];
  realm_role?: string;
}

export interface UniverseSnapshot {
  realm_id?: string;
  realm_version?: number;
  cursor?: number;
  generated_at?: string;
  viewer?: UniverseViewer;
  realms?: UniverseEntity[];
  players?: UniverseEntity[];
  civilizations?: Civilization[];
  memberships?: UniverseEntity[];
  presences?: UniverseEntity[];
  proposals?: UniverseEntity[];
  treaties?: UniverseEntity[];
  stations?: UniverseEntity[];
  vessels?: Vessel[];
  fleets?: UniverseEntity[];
  missions?: Mission[];
  assets?: UniverseEntity[];
  workspace_leases?: WorkspaceLease[];
  fabrication_sessions?: UniverseEntity[];
  game_productions?: UniverseEntity[];
  cinematic_shots?: CinematicShot[];
  releases?: ReleaseRecord[];
  [collection: string]: unknown;
}

export interface UniverseCatalogSnapshot {
  atlas_crown?: Record<string, unknown>;
  stations: Array<{ id: string; [key: string]: unknown }>;
  vessel_classes: string[];
  player_modes: string[];
  coop_roles: string[];
  required_rooms: string[];
  modules: Record<string, UniverseModule>;
}

export interface UniverseModule {
  id: string;
  type: string;
  attachment_types: string[];
  requires: string[];
  conflicts: string[];
  capabilities: string[];
  power: number;
  heat: number;
  compute: number;
  context: number;
  cost_class: string;
  trust_exposure: string;
  license?: string;
}

export interface CommandResult {
  event: UniverseEvent;
  entity: UniverseEntity;
  idempotent_replay: boolean;
}

export interface UniverseEventPage {
  events: UniverseEvent[];
  cursor: number;
  realm_version: number;
}

export type ApiProblemKind =
  | 'unauthenticated'
  | 'denied'
  | 'conflict'
  | 'rate-limited'
  | 'server'
  | 'network'
  | 'invalid-response'
  | 'unavailable';

export interface ApiProblem {
  kind: ApiProblemKind;
  status: number | null;
  message: string;
  correlationId: string | null;
  currentVersion: number | null;
  retryAfterMs: number | null;
  occurredAt: string;
}

export function snapshotEntities<T extends UniverseEntity>(
  snapshot: UniverseSnapshot | null,
  collection: string,
): T[] {
  const value = snapshot?.[collection];
  return Array.isArray(value) ? (value as T[]) : [];
}
