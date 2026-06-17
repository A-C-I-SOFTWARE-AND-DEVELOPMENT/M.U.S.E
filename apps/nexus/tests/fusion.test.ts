import { describe, it, expect } from 'vitest';
import {
  fuseVectors,
  runAxiomGates,
  runFusion,
  attestationHash,
  defaultGateConfig,
  ALL_GATES,
} from '../src/lib/fusion';
import { balancedWeights } from '../src/lib/steering';
import { DEFAULT_PRESET } from '../src/lib/vertices';
import type { FusionSource, WeightVector } from '../src/lib/types';

const V = DEFAULT_PRESET;

function vec(overrides: Partial<Record<string, number>>): WeightVector {
  const w: WeightVector = {};
  V.forEach((v) => (w[v.key] = overrides[v.key] ?? 0.02));
  // normalize
  const sum = Object.values(w).reduce((a, b) => a + b, 0);
  V.forEach((v) => (w[v.key] = w[v.key] / sum));
  return w;
}

function source(id: string, weights: WeightVector, contribution: number): FusionSource {
  return { id, label: id, kind: 'profile', weights, contribution };
}

describe('fuseVectors', () => {
  it('weighted-mean of identical sources is that vector (normalized)', () => {
    const w = balancedWeights(V);
    const fused = fuseVectors([source('a', w, 1), source('b', w, 1)], 'weighted-mean', V);
    expect(Object.values(fused).reduce((a, b) => a + b, 0)).toBeCloseTo(1, 5);
    V.forEach((v) => expect(fused[v.key]).toBeCloseTo(w[v.key], 4));
  });

  it('always returns a normalized vector for every strategy', () => {
    const s = [source('a', vec({ coding: 0.7 }), 0.6), source('b', vec({ empathy: 0.7 }), 0.4)];
    for (const strat of ['weighted-mean', 'max-axis', 'owner-priority', 'geometric'] as const) {
      const fused = fuseVectors(s, strat, V);
      const sum = Object.values(fused).reduce((a, b) => a + b, 0);
      expect(sum, strat).toBeCloseTo(1, 4);
      Object.values(fused).forEach((x) => expect(x).toBeGreaterThanOrEqual(0));
    }
  });

  it('contribution weighting biases the fused result', () => {
    const codey = vec({ coding: 0.8 });
    const warm = vec({ empathy: 0.8 });
    const codeHeavy = fuseVectors([source('a', codey, 0.9), source('b', warm, 0.1)], 'weighted-mean', V);
    const warmHeavy = fuseVectors([source('a', codey, 0.1), source('b', warm, 0.9)], 'weighted-mean', V);
    expect(codeHeavy.coding).toBeGreaterThan(warmHeavy.coding);
    expect(warmHeavy.empathy).toBeGreaterThan(codeHeavy.empathy);
  });

  it('empty sources returns an equal vector', () => {
    const fused = fuseVectors([], 'weighted-mean', V);
    V.forEach((v) => expect(fused[v.key]).toBeCloseTo(1 / V.length, 6));
  });
});

describe('runAxiomGates', () => {
  it('a balanced fusion passes all gates', () => {
    const w = balancedWeights(V);
    const gates = runAxiomGates(w, [source('a', w, 1)], V, defaultGateConfig());
    expect(gates).toHaveLength(8);
    expect(gates.every((g) => g.status === 'pass')).toBe(true);
    expect(gates.map((g) => g.key)).toEqual(ALL_GATES);
  });

  it('owner gate warns on a high-risk (very hot) vector', () => {
    const hot = vec({ creativity: 0.85 });
    const gates = runAxiomGates(hot, [source('a', hot, 1)], V, defaultGateConfig());
    const owner = gates.find((g) => g.key === 'owner')!;
    expect(owner.status).toBe('warn');
  });

  it('owner gate passes once owner approval is on record', () => {
    const hot = vec({ creativity: 0.85 });
    const cfg = { ...defaultGateConfig(), ownerApproved: true };
    const gates = runAxiomGates(hot, [source('a', hot, 1)], V, cfg);
    expect(gates.find((g) => g.key === 'owner')!.status).toBe('pass');
  });

  it('disabling enforcement downgrades a fail to a warn (non-blocking)', () => {
    const cfg = defaultGateConfig();
    cfg.enforced.planning = false;
    const gates = runAxiomGates(balancedWeights(V), [], V, cfg);
    const planning = gates.find((g) => g.key === 'planning')!;
    expect(planning.enforced).toBe(false);
    expect(planning.status).toBe('warn'); // would be 'fail' if enforced
  });
});

describe('runFusion pipeline', () => {
  it('attests a clean balanced fusion and emits a stable hash', () => {
    const w = balancedWeights(V);
    const r = runFusion([source('a', w, 1)], 'weighted-mean', V, defaultGateConfig());
    expect(r.verdict).toBe('attested');
    expect(r.attestation).toMatch(/^[0-9a-f]{16}$/);
    // deterministic
    expect(r.attestation).toBe(attestationHash(r.fused, V));
  });

  it('marks pending-owner for a high-risk (but secure) vector without approval', () => {
    // maxW > 0.7 triggers the owner gate; contemplation-heavy keeps Security green.
    const deep = vec({ contemplation: 0.85 });
    const r = runFusion([source('a', deep, 1)], 'weighted-mean', V, defaultGateConfig());
    expect(r.verdict).toBe('pending-owner');
    expect(r.attestation).toBeNull();
  });

  it('attests the same high-risk vector once owner-approved', () => {
    const deep = vec({ contemplation: 0.85 });
    const cfg = { ...defaultGateConfig(), ownerApproved: true };
    const r = runFusion([source('a', deep, 1)], 'weighted-mean', V, cfg);
    expect(r.verdict).toBe('attested');
    expect(r.attestation).not.toBeNull();
  });

  it('blocks when an enforced gate fails', () => {
    const cfg = defaultGateConfig();
    const r = runFusion([], 'weighted-mean', V, cfg); // planning fails (no sources)
    expect(r.verdict).toBe('blocked');
    expect(r.attestation).toBeNull();
  });

  it('attestation hash changes when the fused vector changes', () => {
    const a = attestationHash(balancedWeights(V), V);
    const b = attestationHash(vec({ coding: 0.6 }), V);
    expect(a).not.toBe(b);
  });
});
