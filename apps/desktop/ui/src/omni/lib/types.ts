// Shared NEXUS types.

export type VertexKey =
  | 'reasoning'
  | 'creativity'
  | 'logic'
  | 'contemplation'
  | 'coding'
  | 'synthesis'
  | 'empathy'
  | 'factuality'
  // OPS preset extras (kept in the union so presets are swappable without casts):
  | 'safety'
  | 'speed'
  | 'tone';

export interface VertexDef {
  key: VertexKey;
  label: string;
  description: string;
  accent: string;
}

export type WeightVector = Record<string, number>; // keyed by VertexKey, sums to 1.0

export interface GlowState {
  color: string;
  pulse: boolean;
  label: string;
}

export interface InferenceParams {
  temperature: number;
  topP: number;
  maxThinkingTokens: number;
  groundingStrength: number; // 0..1
  systemStyleHint: string;
}

export interface SteeringVector {
  profileId: string;
  weights: WeightVector;
  dominant: VertexKey | null;
  glowState: GlowState;
  inference: InferenceParams;
  timestamp: number;
}

// ---- Agent surface adapter contract (Antigravity / AI Studio / M.U.S.E.) ----

export type SurfaceKind = 'muse' | 'antigravity' | 'aistudio';
export type AgentRunState = 'idle' | 'running' | 'error' | 'needs-auth' | 'unknown';

export interface AgentSummary {
  id: string;
  name: string;
  surface: SurfaceKind;
  role?: string;
  state: AgentRunState;
}

export interface AgentStatus {
  id: string;
  state: AgentRunState;
  detail?: string;
  updatedAt: number;
}

export interface AgentSurface {
  id: string;
  kind: SurfaceKind;
  canEmbed: boolean; // true only for muse
  listAgents(): Promise<AgentSummary[]>;
  getStatus(agentId: string): Promise<AgentStatus>;
  openExternal?(agentId: string): void; // link-out surfaces
  applySteering?(agentId: string, v: SteeringVector): Promise<void>; // muse only for now
}

// ---- Axiom Gate (fusion + verification) -----------------------------------
// "Intelligence proposes; the verifier disposes." Multiple steering sources are
// FUSED into one vector, then run through MUSE's verification gates. Only an
// attested (all-enforced-gates-pass) vector reaches the model router.

export type FusionStrategy =
  | 'weighted-mean'
  | 'max-axis'
  | 'owner-priority'
  | 'geometric';

export type FusionSourceKind = 'profile' | 'agent' | 'baseline' | 'manual';

export interface FusionSource {
  id: string;
  label: string;
  kind: FusionSourceKind;
  weights: WeightVector;
  /** Relative contribution to the fusion, 0..1 (normalized across sources). */
  contribution: number;
}

export type AxiomGateKey =
  | 'planning'
  | 'build'
  | 'review'
  | 'test'
  | 'security'
  | 'release'
  | 'owner'
  | 'rollback';

export type GateStatus = 'pass' | 'fail' | 'warn' | 'skipped';

export interface GateVerdict {
  key: AxiomGateKey;
  label: string;
  status: GateStatus;
  detail: string;
  enforced: boolean;
}

export interface FusionResult {
  fused: WeightVector;
  dominant: VertexKey | null;
  glowState: GlowState;
  inference: InferenceParams;
  gates: GateVerdict[];
  verdict: 'attested' | 'blocked' | 'pending-owner';
  /** Content-address of the canonical fused form (null until attested). */
  attestation: string | null;
  timestamp: number;
}

export interface GateConfig {
  enforced: Record<AxiomGateKey, boolean>;
  ownerApproved: boolean;
}

// ---- Neural Observatory (the live "mirror" dashboard) ----------------------
// Mirrors the gateway's read-only /v1/observatory/* contract
// (docs/synapse/design/10-observatory-spec.md). Render-only: every number
// arrives fully formed from the gateway. Honesty rule: when the graph is
// unavailable, render the dormant dressing — NEVER fabricate activity.

export interface ObsCluster {
  id: string;
  label: string;
  type_mix: Record<string, number>;
  members: number;
  pos: [number, number, number];
  radius: number;
  heat: number | null; // null below the n>=5 confidence gate
}

export interface ObsClusterEdge {
  a: string;
  b: string;
  weight: number;
  heat: number | null;
}

export interface ObsActiveJob {
  job_id: string;
  task_class: string;
  stage: 'queued' | 'navigator' | 'worker' | 'gate' | 'ledger' | 'done' | 'failed';
  stage_entered_at: string;
  queue_pos: number | null;
}

export interface ObsLadderTier {
  tier: 'local' | 'hosted' | 'paired';
  model: string;
  share_1h: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
}

export interface ObsSnapshot {
  v: number;
  generated_at: string;
  graph: {
    available: boolean;
    graph_version: string;
    node_count: number;
    edge_count: number;
    clusters: ObsCluster[];
    cluster_edges: ObsClusterEdge[];
    layout_algo?: string;
  };
  stations: { nodes: string[]; active_jobs: ObsActiveJob[]; queue_depth: number };
  ladder: { tiers: ObsLadderTier[] };
}

export type ObsStreamEvent =
  | { type: 'job.stage'; job_id: string; task_class: string; stage: ObsActiveJob['stage']; queue_depth: number; ts: string }
  | { type: 'gate.verdict'; job_id: string; gate: AxiomGateKey; verdict: 'pass' | 'fail' | 'override'; attempt: number; ts: string }
  | { type: 'node.activate'; cluster_id: string; node_id: string | null; kind: 'query' | 'write' | 'promote'; weight: number; ts: string }
  | { type: 'route.decision'; turn_id: string; tier: ObsLadderTier['tier']; model: string; reason: string; latency_ms: number; ts: string }
  | { type: 'resync'; reason: 'gap' | 'graph_rebuilt'; ts: string };

export interface ActivityEvent {
  id: string;
  surface: SurfaceKind;
  agentId?: string;
  kind: 'run-started' | 'run-completed' | 'error' | 'pr-opened' | 'idle' | 'needs-auth';
  message: string;
  timestamp: number;
}
