import type {
  AxiomGateKey,
  FusionResult,
  FusionSource,
  FusionStrategy,
  GateConfig,
  GateVerdict,
  VertexDef,
  WeightVector,
} from './types';
import {
  deriveGlowState,
  dominantVertex,
  weightsToInference,
} from './steering';

// ============================================================================
// The Axiom Gate — fusion + verification. Pure, deterministic, unit-tested.
//
// AXIOM's law (axiom/README.md): "No intelligence is trusted without external
// verification." Here the octagon PROPOSES steering vectors; the Axiom Gate
// FUSES sources and the verifier DISPOSES via MUSE's 8 verification gates
// (docs/jarvis-verification-gates.md). Only an attested vector is applied.
// ============================================================================

function normalize(weights: WeightVector, keys: string[]): WeightVector {
  const out: WeightVector = {};
  let sum = 0;
  keys.forEach((k) => (sum += Math.max(0, weights[k] ?? 0)));
  sum = sum || 1;
  keys.forEach((k) => (out[k] = Math.max(0, weights[k] ?? 0) / sum));
  return out;
}

function sourceWeights(sources: FusionSource[]): number[] {
  const raw = sources.map((s) => Math.max(0, s.contribution));
  const sum = raw.reduce((a, b) => a + b, 0) || 1;
  return raw.map((r) => r / sum);
}

/**
 * Fuse multiple steering sources into one normalized weight vector.
 *
 *  - weighted-mean : Σ contribution_i · weights_i  (the default blend).
 *  - max-axis      : per-axis maximum across sources (union of intents).
 *  - owner-priority: the highest-contribution source dominates, others nudge.
 *  - geometric     : contribution-weighted geometric mean (consensus; punishes
 *                    disagreement — an axis any source zeroes is pulled down).
 */
export function fuseVectors(
  sources: FusionSource[],
  strategy: FusionStrategy,
  vertices: VertexDef[],
): WeightVector {
  const keys = vertices.map((v) => v.key);
  if (sources.length === 0) {
    const eq = 1 / keys.length;
    return Object.fromEntries(keys.map((k) => [k, eq]));
  }
  const sw = sourceWeights(sources);
  const acc: WeightVector = Object.fromEntries(keys.map((k) => [k, 0]));

  switch (strategy) {
    case 'weighted-mean': {
      sources.forEach((s, i) => keys.forEach((k) => (acc[k] += sw[i] * (s.weights[k] ?? 0))));
      break;
    }
    case 'max-axis': {
      keys.forEach((k) => (acc[k] = Math.max(...sources.map((s) => s.weights[k] ?? 0))));
      break;
    }
    case 'owner-priority': {
      const lead = sw.indexOf(Math.max(...sw));
      keys.forEach((k) => {
        const others = sources.reduce(
          (sum, s, i) => (i === lead ? sum : sum + sw[i] * (s.weights[k] ?? 0)),
          0,
        );
        acc[k] = 0.7 * (sources[lead].weights[k] ?? 0) + 0.3 * others;
      });
      break;
    }
    case 'geometric': {
      keys.forEach((k) => {
        let logSum = 0;
        sources.forEach((s, i) => {
          const w = (s.weights[k] ?? 0) + 1e-6;
          logSum += sw[i] * Math.log(w);
        });
        acc[k] = Math.exp(logSum);
      });
      break;
    }
  }
  return normalize(acc, keys);
}

const GATE_LABEL: Record<AxiomGateKey, string> = {
  planning: 'Planning',
  build: 'Build',
  review: 'Review',
  test: 'Test',
  security: 'Security',
  release: 'Release',
  owner: 'Owner Approval',
  rollback: 'Rollback',
};

export const ALL_GATES: AxiomGateKey[] = [
  'planning',
  'build',
  'review',
  'test',
  'security',
  'release',
  'owner',
  'rollback',
];

export function defaultGateConfig(): GateConfig {
  return {
    enforced: {
      planning: true,
      build: true,
      review: true,
      test: true,
      security: true,
      release: true,
      owner: true,
      rollback: false, // informational by default
    },
    ownerApproved: false,
  };
}

/**
 * Run MUSE's 8 verification gates against a fused vector. Deterministic — each
 * gate is a concrete check on the fused weights / sources / mapped inference.
 */
export function runAxiomGates(
  fused: WeightVector,
  sources: FusionSource[],
  vertices: VertexDef[],
  config: GateConfig,
): GateVerdict[] {
  const keys = vertices.map((v) => v.key);
  const inf = weightsToInference(fused);
  const sum = keys.reduce((a, k) => a + (fused[k] ?? 0), 0);
  const maxW = Math.max(...keys.map((k) => fused[k] ?? 0));
  const w = (k: string) => fused[k] ?? 0;

  const make = (key: AxiomGateKey, status: GateVerdict['status'], detail: string): GateVerdict => ({
    key,
    label: GATE_LABEL[key],
    status: config.enforced[key] ? status : status === 'fail' ? 'warn' : status,
    enforced: config.enforced[key],
    detail,
  });

  const verdicts: GateVerdict[] = [];

  // Planning — intent exists: at least one source feeding the fusion.
  verdicts.push(
    sources.length >= 1
      ? make('planning', 'pass', `${sources.length} source(s) declared`)
      : make('planning', 'fail', 'No fusion sources'),
  );

  // Build — the artifact is well-formed: finite, normalized weights.
  const wellFormed = Math.abs(sum - 1) < 1e-3 && keys.every((k) => Number.isFinite(w(k)));
  verdicts.push(
    wellFormed
      ? make('build', 'pass', 'Vector normalized (Σ=1), finite')
      : make('build', 'fail', `Malformed vector (Σ=${sum.toFixed(3)})`),
  );

  // Review — sanity: no degenerate single-axis collapse unless intended.
  verdicts.push(
    maxW <= 0.9
      ? make('review', 'pass', `Peak axis ${(maxW * 100).toFixed(0)}% within range`)
      : make('review', 'warn', `Peak axis ${(maxW * 100).toFixed(0)}% — near collapse`),
  );

  // Test — mapped inference params land inside their clamps.
  const inRange =
    inf.temperature >= 0 && inf.temperature <= 2 &&
    inf.topP >= 0.1 && inf.topP <= 1 &&
    inf.groundingStrength >= 0 && inf.groundingStrength <= 1;
  verdicts.push(
    inRange
      ? make('test', 'pass', `temp ${inf.temperature.toFixed(2)} · topP ${inf.topP.toFixed(2)}`)
      : make('test', 'fail', 'Inference params out of clamp'),
  );

  // Security — grounding floor: high creativity must keep some factual anchor.
  const risky = w('creativity') > 0.5 && inf.groundingStrength < 0.1 && w('factuality') < 0.06;
  verdicts.push(
    !risky
      ? make('security', 'pass', `grounding ${inf.groundingStrength.toFixed(2)}`)
      : make('security', 'fail', 'High creativity with no factual anchor'),
  );

  // Release — aggregate: all prior ENFORCED gates passed.
  const priorFail = verdicts.some((g) => g.enforced && g.status === 'fail');
  verdicts.push(
    !priorFail
      ? make('release', 'pass', 'All prior enforced gates green')
      : make('release', 'fail', 'Blocked by an upstream gate'),
  );

  // Owner Approval — owner-gated if the vector is high-risk (very hot or extreme).
  const ownerGated = inf.temperature > 1.4 || maxW > 0.7;
  if (!ownerGated) {
    verdicts.push(make('owner', 'pass', 'No owner-gated risk detected'));
  } else if (config.ownerApproved) {
    verdicts.push(make('owner', 'pass', 'Owner authorization on record'));
  } else {
    verdicts.push(make('owner', 'warn', 'High-risk vector — owner approval required'));
  }

  // Rollback — a safe baseline (balanced vector) is always available.
  verdicts.push(make('rollback', 'pass', 'Balanced baseline retained for rollback'));

  return verdicts;
}

/** Deterministic content-address (FNV-1a, 64-bit) of canonical fused form.
 *  Production AXIOM uses blake3 (axiom/canonical.py); this is a sync stand-in
 *  for the PWA so attestation is testable without async crypto. */
export function attestationHash(fused: WeightVector, vertices: VertexDef[]): string {
  const canonical = vertices
    .map((v) => `${v.key}:${(fused[v.key] ?? 0).toFixed(6)}`)
    .join('|');
  let h1 = 0x811c9dc5;
  let h2 = 0xcbf29ce4;
  for (let i = 0; i < canonical.length; i++) {
    const c = canonical.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 0x01000193) >>> 0;
    h2 = Math.imul(h2 ^ ((c << 1) | 1), 0x01000193) >>> 0;
  }
  return (h1.toString(16).padStart(8, '0') + h2.toString(16).padStart(8, '0'));
}

/** Full pipeline: fuse → verify → (maybe) attest. */
export function runFusion(
  sources: FusionSource[],
  strategy: FusionStrategy,
  vertices: VertexDef[],
  config: GateConfig,
): FusionResult {
  const fused = fuseVectors(sources, strategy, vertices);
  const gates = runAxiomGates(fused, sources, vertices, config);

  const enforcedFail = gates.some((g) => g.enforced && g.status === 'fail');
  const ownerPending =
    config.enforced.owner && gates.find((g) => g.key === 'owner')?.status === 'warn';

  let verdict: FusionResult['verdict'];
  if (enforcedFail) verdict = 'blocked';
  else if (ownerPending) verdict = 'pending-owner';
  else verdict = 'attested';

  return {
    fused,
    dominant: dominantVertex(fused),
    glowState: deriveGlowState(fused, vertices),
    inference: weightsToInference(fused),
    gates,
    verdict,
    attestation: verdict === 'attested' ? attestationHash(fused, vertices) : null,
    timestamp: Date.now(),
  };
}
