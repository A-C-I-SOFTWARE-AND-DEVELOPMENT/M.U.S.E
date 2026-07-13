// ============================================================================
// Fusion-graph types. Route / Ensemble / Pipeline / Graph are four SHAPES of a
// single Mixture-of-Agents structure: layers of proposers run in parallel, an
// optional aggregator synthesizes (MoA, arXiv 2406.04692). Build the executor
// once; the modes are presets. Provider-agnostic: a leg is just an
// OpenAI-compatible { model } over the gateway's per-leg transport.
// ============================================================================

export type ModelRef = string; // "claude-sonnet-4-5", "openrouter/auto:nitro", "local/cpp-arch"

export type LegRole = 'proposer' | 'critic' | 'aggregator';

export interface FusionLeg {
  model: ModelRef;
  role?: LegRole;
  weight?: number; // weighted voting / judging
  systemHint?: string; // per-leg persona
  temperature?: number;
}

export interface FusionLayer {
  legs: FusionLeg[]; // legs run in PARALLEL within a layer
  passPreviousOutputs: boolean; // MoA: feed prior layer outputs as labeled context
}

export type FusionMode = 'route' | 'ensemble' | 'pipeline' | 'graph';
export type DisplayMode = 'transparent' | 'unified';
export type LegTransport = 'direct' | 'openrouter' | 'litellm';

export interface FusionDef {
  id: string;
  name: string;
  mode: FusionMode;
  layers: FusionLayer[];
  aggregator: FusionLeg | null; // final synthesizer (null for pure route)
  displayMode: DisplayMode;
  attest: boolean; // run the result through AXIOM gates
  transport?: LegTransport; // per-deployment transport (default 'direct')
  budgetUsd?: number;
  createdAt: number;
  favorite?: boolean;
  readonly?: boolean; // curated presets
}

export interface LegResult {
  model: ModelRef;
  role: LegRole;
  layer: number;
  content: string;
  latencyMs?: number;
  costUsd?: number;
  error?: string;
}

export interface FusionRun {
  id: string;
  fusionId: string;
  fusionName: string;
  prompt: string;
  legs: LegResult[]; // every proposer/critic output (full provenance)
  output: string; // the final (aggregated) answer
  attestation: string | null;
  costUsd: number;
  latencyMs: number;
  timestamp: number;
}

// ---- Mode <-> shape helpers (pure; the executor and tests share these) ------

export function legCount(def: FusionDef): number {
  return def.layers.reduce((n, l) => n + l.legs.length, 0) + (def.aggregator ? 1 : 0);
}

/** Derive the mode a definition's shape represents (for validation / labels). */
export function shapeOf(def: FusionDef): FusionMode {
  const layers = def.layers.length;
  const maxLegs = Math.max(0, ...def.layers.map((l) => l.legs.length));
  if (layers <= 1 && maxLegs <= 1 && !def.aggregator) return 'route';
  if (layers <= 1 && def.aggregator) return 'ensemble';
  if (layers > 1 && maxLegs <= 1) return 'pipeline';
  return 'graph';
}

/** All distinct models a run will touch (for cost estimation / display). */
export function modelsOf(def: FusionDef): ModelRef[] {
  const set = new Set<ModelRef>();
  def.layers.forEach((l) => l.legs.forEach((leg) => set.add(leg.model)));
  if (def.aggregator) set.add(def.aggregator.model);
  return [...set];
}
