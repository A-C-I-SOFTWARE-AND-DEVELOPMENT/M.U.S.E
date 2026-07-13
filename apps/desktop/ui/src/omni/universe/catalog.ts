import type {
  DeckId,
  PlayerMode,
  RoomId,
  SceneKind,
  StationId,
  VesselClassId,
} from './types.ts';

export interface DeckDefinition {
  id: DeckId;
  label: string;
  purpose: string;
  sector: string;
}

export interface StationDefinition {
  id: Exclude<StationId, 'atlas-crown'>;
  backendId: string;
  label: string;
  deck: DeckId;
  room: RoomId;
  route: string;
  purpose: string;
  requiredScope: string | null;
}

export interface VesselClassDefinition {
  id: VesselClassId;
  label: string;
  silhouette: string;
  function: string;
}

export interface PlayerModeDefinition {
  id: PlayerMode;
  label: string;
  summary: string;
}

export interface UniverseRoute {
  path: string;
  label: string;
  deck: DeckId;
  station: StationId;
  room: RoomId;
  scene: SceneKind;
  capability: string;
  accessibleSummary: string;
  primary: boolean;
}

export const DECKS = [
  { id: 'crown', label: 'Crown Deck', purpose: 'Command, governance, and system integrity', sector: '01' },
  { id: 'flight', label: 'Flight Deck', purpose: 'Vessels, agents, fleets, and travel', sector: '02' },
  { id: 'foundry', label: 'Foundry Deck', purpose: 'Source, fabrication, games, cinema, and release', sector: '03' },
  { id: 'observatory', label: 'Observatory Deck', purpose: 'Knowledge, models, evidence, and memory', sector: '04' },
  { id: 'embassy', label: 'Embassy Deck', purpose: 'Players, civilizations, diplomacy, and exchange', sector: '05' },
] as const satisfies readonly DeckDefinition[];

export const STATIONS = [
  { id: 'neural-shipyard', backendId: 'neural_shipyard', label: 'Neural Shipyard', deck: 'flight', room: 'shipyard', route: '/shipyard', purpose: 'Configure truthful agent vessels and validated modules', requiredScope: 'vessel:configure' },
  { id: 'deep-observatory', backendId: 'deep_observatory', label: 'Deep Observatory', deck: 'observatory', room: 'sensor-laboratory', route: '/observatory', purpose: 'Inspect the live graph with provenance and semantic zoom', requiredScope: null },
  { id: 'fabrication-foundry', backendId: 'fabrication_foundry', label: 'Fabrication Foundry', deck: 'foundry', room: 'fabrication-bay', route: '/fabrication', purpose: 'Map visual elements to source and verify bounded edits', requiredScope: 'artifact:write' },
  { id: 'cinema-array', backendId: 'cinema_array', label: 'Cinema Array', deck: 'foundry', room: 'cinema-array', route: '/cinema', purpose: 'Author metric stereo shots and deterministic render evidence', requiredScope: 'cinema:write' },
  { id: 'game-foundry', backendId: 'game_foundry', label: 'AAA Game Foundry', deck: 'foundry', room: 'game-foundry', route: '/game-foundry', purpose: 'Coordinate source-complete game production and gates', requiredScope: 'artifact:write' },
  { id: 'memory-archive', backendId: 'memory_archive', label: 'Memory Archive', deck: 'observatory', room: 'memory-vault', route: '/second-brain', purpose: 'Inspect persistent knowledge and provenance', requiredScope: 'memory:read' },
  { id: 'quarantine-moon', backendId: 'quarantine_moon', label: 'Quarantine Moon', deck: 'crown', room: 'security-airlock', route: '/axiom', purpose: 'Review denied, contested, or unsafe operations', requiredScope: null },
  { id: 'relay-embassy', backendId: 'relay_embassy', label: 'Relay Embassy', deck: 'embassy', room: 'relay-embassy', route: '/civilizations', purpose: 'Coordinate civilizations while keeping federation identity separate', requiredScope: null },
  { id: 'academy-station', backendId: 'academy_station', label: 'Academy Station', deck: 'embassy', room: 'crew-observation', route: '/championship', purpose: 'Review measured capability and evidence-backed progression', requiredScope: null },
  { id: 'blueprint-exchange', backendId: 'blueprint_exchange', label: 'Blueprint Exchange', deck: 'embassy', room: 'production-command', route: '/repo', purpose: 'Inspect licensed, hashed, moderated blueprints and source', requiredScope: null },
  { id: 'release-dock', backendId: 'release_dock', label: 'Release Dock', deck: 'foundry', room: 'release-dock', route: '/release', purpose: 'Stage, approve, publish, and roll back durable releases', requiredScope: 'release:promote' },
] as const satisfies readonly StationDefinition[];

export const VESSEL_CLASSES = [
  { id: 'scout', label: 'Scout', silhouette: 'needle', function: 'Fast local reconnaissance' },
  { id: 'surveyor', label: 'Surveyor', silhouette: 'twin-boom', function: 'Research and evidence collection' },
  { id: 'forge', label: 'Forge', silhouette: 'industrial-spine', function: 'Source and artifact production' },
  { id: 'director', label: 'Director', silhouette: 'camera-wing', function: 'Cinematic direction and review' },
  { id: 'carrier', label: 'Carrier', silhouette: 'split-hangar', function: 'Large fleet coordination' },
  { id: 'diplomat', label: 'Diplomat', silhouette: 'balanced-ring', function: 'Civilization and federation work' },
  { id: 'sentinel', label: 'Sentinel', silhouette: 'armored-delta', function: 'Security and policy enforcement' },
  { id: 'courier', label: 'Courier', silhouette: 'compact-lifting-body', function: 'Bounded transfer and relay work' },
  { id: 'flagship', label: 'Flagship', silhouette: 'crowned-keel', function: 'Owner-led multi-domain command' },
] as const satisfies readonly VesselClassDefinition[];

export const PLAYER_MODES = [
  { id: 'walk', label: 'Walk', summary: 'Accessible waypoints through consistent rooms and airlocks' },
  { id: 'pilot', label: 'Pilot', summary: 'Manual, assisted, autopilot, and docking navigation' },
  { id: 'fleet', label: 'Fleet', summary: 'Formations, dependencies, missions, and intervention controls' },
  { id: 'director', label: 'Director', summary: 'Free camera, shot metadata, stereo constraints, and replay' },
] as const satisfies readonly PlayerModeDefinition[];

const route = (
  path: string,
  label: string,
  deck: DeckId,
  station: StationId,
  room: RoomId,
  scene: SceneKind,
  capability: string,
  accessibleSummary: string,
  primary = false,
): UniverseRoute => ({ path, label, deck, station, room, scene, capability, accessibleSummary, primary });

export const UNIVERSE_ROUTES = [
  route('/', 'Neural Conversation', 'crown', 'atlas-crown', 'neural-chamber', 'atlas-crown', 'chat', 'Primary M.U.S.E. conversation surface.'),
  route('/chat', 'Neural Conversation', 'crown', 'atlas-crown', 'neural-chamber', 'atlas-crown', 'chat', 'Primary M.U.S.E. conversation surface.'),
  route('/atlas', 'Atlas Crown', 'crown', 'atlas-crown', 'command-bridge', 'atlas-crown', 'universe:read', 'Home landmark, deck navigator, connection evidence, and 2D route controls.', true),
  route('/stations', 'Stations', 'flight', 'atlas-crown', 'command-bridge', 'celestial-map', 'station:read', 'Searchable station network with service, permission, and navigation evidence.', true),
  route('/stations/:stationId', 'Station Interior', 'flight', 'atlas-crown', 'command-bridge', 'station-room', 'station:read', 'Selected station interior with direct accessible controls.'),
  route('/shipyard', 'Neural Shipyard', 'flight', 'neural-shipyard', 'shipyard', 'station-room', 'vessel:configure', 'Validated vessel module drafts, diagnostics, test flight, apply, and rollback.', true),
  route('/fleet', 'Agent Fleet', 'flight', 'neural-shipyard', 'command-bridge', 'vessel-exterior', 'fleet:read', 'Authoritative vessels, missions, formations, and fan-out operations.', true),
  route('/agents', 'Agents', 'flight', 'neural-shipyard', 'neural-chamber', 'vessel-interior', 'agent:read', 'Agent bindings represented as boardable vessels without embedded duplicate consoles.', true),
  route('/civilizations', 'Civilizations', 'embassy', 'relay-embassy', 'relay-embassy', 'station-room', 'civilization:read', 'Players, memberships, roles, governance, diplomacy, ledgers, and moderation.', true),
  route('/fabrication', 'Fabrication', 'foundry', 'fabrication-foundry', 'fabrication-bay', 'station-room', 'artifact:write', 'Source mapping, bounded edits, preview, diff, verification, checkpoint, apply, and rollback.', true),
  route('/game-foundry', 'AAA Game Foundry', 'foundry', 'game-foundry', 'game-foundry', 'station-room', 'artifact:write', 'Complete game production lanes with engine, test, package, rights, and release evidence.', true),
  route('/cinema', 'Cinema Stage', 'foundry', 'cinema-array', 'cinema-array', 'station-room', 'cinema:read', 'Metric stereo production, render manifests, quality control, and deliverables.', true),
  route('/release', 'Release Dock', 'foundry', 'release-dock', 'release-dock', 'station-room', 'release:read', 'Private preview, staged gates, owner approval, durable publish, prior version, and rollback.', true),
  route('/console', 'Mission Control', 'crown', 'atlas-crown', 'command-bridge', 'station-room', 'runtime:read', 'Live command and control evidence.'),
  route('/signin', 'Identity Airlock', 'crown', 'quarantine-moon', 'security-airlock', 'station-room', 'identity:read', 'Authentication and identity boundary.'),
  route('/steer', 'Steering Core', 'crown', 'atlas-crown', 'neural-chamber', 'station-room', 'steering:write', 'Agent steering controls and attestation state.'),
  route('/axiom', 'Axiom Gate', 'crown', 'quarantine-moon', 'security-airlock', 'station-room', 'approval:read', 'Verification gates, owner decisions, and blocked evidence.'),
  route('/observatory', 'Neural Observatory', 'observatory', 'deep-observatory', 'sensor-laboratory', 'neural-core', 'observatory:read', 'Live graph, semantic zoom, provenance, and accessible tree inspection.', true),
  route('/fusion', 'Fusion Chamber', 'crown', 'atlas-crown', 'neural-chamber', 'station-room', 'fusion:read', 'Fusion evidence and source contributions.'),
  route('/forge', 'Creation Forge', 'foundry', 'fabrication-foundry', 'fabrication-bay', 'station-room', 'artifact:write', 'Existing creation planning and bounded execution.'),
  route('/models', 'Model Arsenal', 'observatory', 'deep-observatory', 'sensor-laboratory', 'station-room', 'model:read', 'Configured model and routing evidence.'),
  route('/second-brain', 'Second Brain', 'observatory', 'memory-archive', 'memory-vault', 'station-room', 'memory:read', 'Persistent memory with provenance and contradictions.'),
  route('/championship', 'Academy Station', 'embassy', 'academy-station', 'crew-observation', 'station-room', 'achievement:read', 'Evidence-backed capability progression.'),
  route('/federation', 'Federation Relay', 'embassy', 'relay-embassy', 'relay-embassy', 'station-room', 'federation:read', 'Read-only sovereign node and peer identity.'),
  route('/council', 'Governance Chamber', 'crown', 'atlas-crown', 'governance-chamber', 'station-room', 'governance:read', 'Structured multi-agent deliberation and owner gates.'),
  route('/repo', 'Blueprint Exchange', 'embassy', 'blueprint-exchange', 'production-command', 'station-room', 'repo:read', 'Repository, provenance, and blueprint source inspection.'),
  route('/share', 'Signal Broadcast', 'embassy', 'relay-embassy', 'relay-embassy', 'station-room', 'communications:send', 'External sharing with visible trust boundaries.'),
  route('/activity', 'Activity Pulse', 'observatory', 'deep-observatory', 'sensor-laboratory', 'station-room', 'activity:read', 'Auditable operational event stream.'),
  route('/settings', 'Systems Engineering', 'crown', 'atlas-crown', 'engineering', 'station-room', 'settings:read', 'Connections, comfort, fidelity, diagnostics, and secure configuration.'),
  route('/studio', 'Production Command', 'foundry', 'fabrication-foundry', 'production-command', 'station-room', 'studio:read', 'Real project slate and direct production-stage navigation.'),
] as const satisfies readonly UniverseRoute[];

export function routeForPath(pathname: string): UniverseRoute {
  const direct = UNIVERSE_ROUTES.find((entry) => entry.path === pathname);
  if (direct) return direct;
  if (pathname.startsWith('/stations/')) {
    const template = UNIVERSE_ROUTES.find((entry) => entry.path === '/stations/:stationId') ?? UNIVERSE_ROUTES[0];
    const station = stationById(pathname.slice('/stations/'.length));
    return station
      ? {
          ...template,
          label: station.label,
          deck: station.deck,
          station: station.id,
          room: station.room,
          capability: station.requiredScope ?? 'station:read',
          accessibleSummary: station.purpose,
        }
      : template;
  }
  return UNIVERSE_ROUTES[0];
}

export function stationById(id: string | undefined): StationDefinition | undefined {
  if (!id) return undefined;
  const normalized = id.replaceAll('_', '-');
  return STATIONS.find((station) => station.id === normalized || station.backendId === id);
}
