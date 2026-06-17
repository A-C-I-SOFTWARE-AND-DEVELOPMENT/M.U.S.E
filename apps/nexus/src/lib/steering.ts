import type {
  GlowState,
  InferenceParams,
  VertexDef,
  VertexKey,
  WeightVector,
} from './types';

// ============================================================================
// NEXUS steering math — pure, unit-tested. No DOM, no React.
// The octagon's central node position -> normalized weight vector -> glow state
// -> concrete inference params sent to M.U.S.E.'s model-routing layer.
// ============================================================================

export interface Point {
  x: number;
  y: number;
}

export interface WeightOptions {
  /** Falloff exponent for the inverse-distance curve. Higher = sharper. */
  falloff?: number;
  /**
   * Distance at which a vertex's contribution reaches zero. Node space is the
   * unit octagon (radius 1), so distances range 0..~2. maxReach is set > radius
   * so a dead-center node still gets equal NON-zero contributions from every
   * vertex (otherwise center would zero out). Tunable.
   */
  maxReach?: number;
}

export const NEUTRAL_8 = 1 / 8; // 0.125 — neutral weight for an 8-vertex octagon.

/** Geometry: vertex unit positions, clockwise from the top, for N vertices. */
export function vertexPositions(count: number, radius: number): Point[] {
  const pts: Point[] = [];
  for (let i = 0; i < count; i++) {
    // -90deg start (top), clockwise.
    const angle = (-Math.PI / 2) + (i * 2 * Math.PI) / count;
    pts.push({ x: Math.cos(angle) * radius, y: Math.sin(angle) * radius });
  }
  return pts;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/**
 * Map a central-node position to a normalized weight per vertex.
 *
 * weight_i = (1 - clamp(dist_i / maxReach, 0, 1)) ^ falloff, then normalized so
 * the full vector sums to 1.0. A node dead-center yields equal weights.
 */
export function positionToWeights(
  node: Point,
  vertices: VertexDef[],
  opts: WeightOptions = {},
): WeightVector {
  const falloff = opts.falloff ?? 3;
  const maxReach = opts.maxReach ?? 2;
  const positions = vertexPositions(vertices.length, 1);

  const raw = vertices.map((_, i) => {
    const dx = node.x - positions[i].x;
    const dy = node.y - positions[i].y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const proximity = 1 - clamp(dist / maxReach, 0, 1);
    return Math.pow(proximity, falloff);
  });

  const sum = raw.reduce((a, b) => a + b, 0) || 1;
  const out: WeightVector = {};
  vertices.forEach((v, i) => {
    out[v.key] = raw[i] / sum;
  });
  return out;
}

/** Equal-weight (balanced) vector for a given preset. */
export function balancedWeights(vertices: VertexDef[]): WeightVector {
  const w = 1 / vertices.length;
  const out: WeightVector = {};
  vertices.forEach((v) => (out[v.key] = w));
  return out;
}

/** The weighted centroid of the vertices — where the node sits for a vector. */
export function weightsToPosition(weights: WeightVector, vertices: VertexDef[]): Point {
  const positions = vertexPositions(vertices.length, 1);
  let x = 0;
  let y = 0;
  vertices.forEach((v, i) => {
    const w = weights[v.key] ?? 0;
    x += positions[i].x * w;
    y += positions[i].y * w;
  });
  return { x, y };
}

export interface RankedWeight {
  key: VertexKey;
  weight: number;
}

export function rankWeights(weights: WeightVector): RankedWeight[] {
  return Object.entries(weights)
    .map(([key, weight]) => ({ key: key as VertexKey, weight }))
    .sort((a, b) => b.weight - a.weight);
}

export function dominantVertex(weights: WeightVector, threshold = 0.45): VertexKey | null {
  const ranked = rankWeights(weights);
  if (ranked.length && ranked[0].weight > threshold) return ranked[0].key;
  return null;
}

// ---- Color blending in OKLCH for perceptually smooth two-vertex blends. ----

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '');
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255,
  ];
}

function srgbToLinear(c: number): number {
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}
function linearToSrgb(c: number): number {
  return c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
}

interface Oklab {
  L: number;
  a: number;
  b: number;
}

function hexToOklab(hex: string): Oklab {
  const [r, g, b] = hexToRgb(hex).map(srgbToLinear);
  const l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b;
  const m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b;
  const s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b;
  const l_ = Math.cbrt(l);
  const m_ = Math.cbrt(m);
  const s_ = Math.cbrt(s);
  return {
    L: 0.2104542553 * l_ + 0.793617785 * m_ - 0.0040720468 * s_,
    a: 1.9779984951 * l_ - 2.428592205 * m_ + 0.4505937099 * s_,
    b: 0.0259040371 * l_ + 0.7827717662 * m_ - 0.808675766 * s_,
  };
}

function oklabToHex(c: Oklab): string {
  const l_ = c.L + 0.3963377774 * c.a + 0.2158037573 * c.b;
  const m_ = c.L - 0.1055613458 * c.a - 0.0638541728 * c.b;
  const s_ = c.L - 0.0894841775 * c.a - 1.291485548 * c.b;
  const l = l_ * l_ * l_;
  const m = m_ * m_ * m_;
  const s = s_ * s_ * s_;
  const r = linearToSrgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s);
  const g = linearToSrgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s);
  const b = linearToSrgb(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s);
  const to255 = (v: number) =>
    Math.round(clamp(v, 0, 1) * 255)
      .toString(16)
      .padStart(2, '0');
  return `#${to255(r)}${to255(g)}${to255(b)}`;
}

/** Perceptual blend of two hex colors at t in [0,1] (OKLAB/OKLCH space). */
export function blendOklch(a: string, b: string, t: number): string {
  const ca = hexToOklab(a);
  const cb = hexToOklab(b);
  return oklabToHex({
    L: ca.L + (cb.L - ca.L) * t,
    a: ca.a + (cb.a - ca.a) * t,
    b: ca.b + (cb.b - ca.b) * t,
  });
}

// Balanced "harmony" green, and the explicit contemplation-dominant warm orange
// the user asked for (warmer than contemplation's periwinkle vertex dot).
export const BALANCED_GREEN = '#3DD68C';
export const CONTEMPLATION_GLOW = '#FF8A3D';

const TITLE: Record<string, string> = {
  reasoning: 'Reasoning',
  creativity: 'Creativity',
  logic: 'Logic',
  contemplation: 'Contemplation',
  coding: 'Coding',
  synthesis: 'Synthesis',
  empathy: 'Empathy',
  factuality: 'Factuality',
  safety: 'Safety',
  speed: 'Speed',
  tone: 'Tone',
};

/**
 * deriveGlowState — pure mapping from a weight vector to the octagon glow.
 *
 *  - Balanced  : no vertex exceeds neutral*1.4 -> harmony green.
 *  - Dominant  : one weight > 0.45 -> that vertex's accent (contemplation -> warm orange).
 *  - Blend     : top two within 0.1 of each other and both > 0.3 -> OKLCH blend.
 *  - Extreme   : any weight > 0.7 -> pulse.
 */
export function deriveGlowState(
  weights: WeightVector,
  vertices: VertexDef[],
): GlowState {
  const neutral = 1 / vertices.length;
  const ranked = rankWeights(weights);
  const accentOf = (key: VertexKey) =>
    vertices.find((v) => v.key === key)?.accent ?? BALANCED_GREEN;

  const max = ranked[0]?.weight ?? 0;
  const pulse = max > 0.7;

  // Balanced.
  if (max <= neutral * 1.4) {
    return { color: BALANCED_GREEN, pulse: false, label: 'Balanced' };
  }

  const [first, second] = ranked;

  // Two-vertex blend.
  if (
    second &&
    Math.abs(first.weight - second.weight) <= 0.1 &&
    first.weight > 0.3 &&
    second.weight > 0.3
  ) {
    const a = first.key === 'contemplation' ? CONTEMPLATION_GLOW : accentOf(first.key);
    const b = second.key === 'contemplation' ? CONTEMPLATION_GLOW : accentOf(second.key);
    return {
      color: blendOklch(a, b, 0.5),
      pulse,
      label: `${TITLE[first.key]} + ${TITLE[second.key]}`,
    };
  }

  // Single-vertex dominant.
  if (first.weight > 0.45) {
    const color =
      first.key === 'contemplation' ? CONTEMPLATION_GLOW : accentOf(first.key);
    return { color, pulse, label: `${TITLE[first.key]}-dominant` };
  }

  // Leaning but not dominant — tint toward the leader, no pulse.
  return {
    color: blendOklch(BALANCED_GREEN, accentOf(first.key), 0.5),
    pulse: false,
    label: `${TITLE[first.key]}-leaning`,
  };
}

// ---- Weights -> concrete inference params. -------------------------------
// These curves are TUNABLE STARTING POINTS, not ground truth. They translate
// the abstract steering vector into knobs M.U.S.E.'s router understands.
export function weightsToInference(weights: WeightVector): InferenceParams {
  const w = (k: VertexKey) => weights[k] ?? 0;

  // Creativity raises temperature; coding/logic pull it down. Clamp 0..2.
  const temperature = clamp(
    0.2 + w('creativity') * 1.1 + w('tone') * 0.3 - w('coding') * 0.3 - w('logic') * 0.25,
    0,
    2,
  );

  // Creativity widens nucleus sampling; factuality narrows it.
  const topP = clamp(0.7 + w('creativity') * 0.29 - w('factuality') * 0.2, 0.1, 1);

  // Contemplation (and reasoning) buy internal thinking budget.
  const maxThinkingTokens = Math.round(
    512 + w('contemplation') * 16000 + w('reasoning') * 8000 - w('speed') * 400,
  );

  // Factuality drives grounding/retrieval reliance, 0..1.
  const groundingStrength = clamp(w('factuality') * 1.2 + w('synthesis') * 0.3, 0, 1);

  // Persona/style hint derived from empathy/tone vs. cold technical leanings.
  const warmth = w('empathy') + w('tone');
  let systemStyleHint: string;
  if (warmth > 0.3) systemStyleHint = 'warm, empathetic, conversational';
  else if (w('coding') > 0.35 || w('logic') > 0.35)
    systemStyleHint = 'precise, technical, terse';
  else systemStyleHint = 'neutral, professional';

  return { temperature, topP, maxThinkingTokens, groundingStrength, systemStyleHint };
}

/** Convenience: full SteeringVector from a node position + preset. */
export function buildSteeringVector(
  profileId: string,
  node: Point,
  vertices: VertexDef[],
  opts: WeightOptions = {},
): import('./types').SteeringVector {
  const weights = positionToWeights(node, vertices, opts);
  const glowState = deriveGlowState(weights, vertices);
  return {
    profileId,
    weights,
    dominant: dominantVertex(weights),
    glowState,
    inference: weightsToInference(weights),
    timestamp: Date.now(),
  };
}
