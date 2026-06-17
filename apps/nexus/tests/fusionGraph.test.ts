import { describe, it, expect } from 'vitest';
import { shapeOf, modelsOf, legCount, type FusionDef } from '../src/lib/fusionTypes';
import { PRESETS, clonePreset } from '../src/lib/presets';

const base = (over: Partial<FusionDef>): FusionDef => ({
  id: 'x', name: 'x', mode: 'route', layers: [], aggregator: null,
  displayMode: 'transparent', attest: false, createdAt: 0, ...over,
});

describe('fusion shape derivation', () => {
  it('route = 1 layer, 1 leg, no aggregator', () => {
    const d = base({ layers: [{ legs: [{ model: 'a' }], passPreviousOutputs: false }], aggregator: null });
    expect(shapeOf(d)).toBe('route');
  });
  it('ensemble = 1 layer, N proposers + aggregator', () => {
    const d = base({ layers: [{ legs: [{ model: 'a' }, { model: 'b' }, { model: 'c' }], passPreviousOutputs: false }], aggregator: { model: 'agg', role: 'aggregator' } });
    expect(shapeOf(d)).toBe('ensemble');
  });
  it('pipeline = K layers, 1 leg each', () => {
    const d = base({ layers: [{ legs: [{ model: 'a' }], passPreviousOutputs: false }, { legs: [{ model: 'b' }], passPreviousOutputs: true }], aggregator: null });
    expect(shapeOf(d)).toBe('pipeline');
  });
  it('graph = K layers, N proposers + aggregator', () => {
    const d = base({ layers: [{ legs: [{ model: 'a' }, { model: 'b' }], passPreviousOutputs: false }, { legs: [{ model: 'c' }, { model: 'd' }], passPreviousOutputs: true }], aggregator: { model: 'agg', role: 'aggregator' } });
    expect(shapeOf(d)).toBe('graph');
  });
});

describe('model + leg accounting', () => {
  it('modelsOf is the distinct set incl. aggregator', () => {
    const d = base({ layers: [{ legs: [{ model: 'a' }, { model: 'a' }, { model: 'b' }], passPreviousOutputs: false }], aggregator: { model: 'c', role: 'aggregator' } });
    expect(new Set(modelsOf(d))).toEqual(new Set(['a', 'b', 'c']));
  });
  it('legCount counts every leg + aggregator', () => {
    const d = base({ layers: [{ legs: [{ model: 'a' }, { model: 'b' }], passPreviousOutputs: false }], aggregator: { model: 'c', role: 'aggregator' } });
    expect(legCount(d)).toBe(3);
  });
});

describe('presets', () => {
  it('every preset is readonly with a valid shape matching its mode', () => {
    expect(PRESETS.length).toBeGreaterThanOrEqual(6);
    for (const p of PRESETS) {
      expect(p.readonly).toBe(true);
      // declared mode should match the derived shape for the curated set
      expect(['route', 'ensemble', 'pipeline', 'graph']).toContain(shapeOf(p));
    }
  });
  it('Code Triad is an attested ensemble with an aggregator', () => {
    const triad = PRESETS.find((p) => p.name === 'Code Triad')!;
    expect(shapeOf(triad)).toBe('ensemble');
    expect(triad.aggregator).not.toBeNull();
    expect(triad.attest).toBe(true);
  });
  it('clonePreset yields a fresh editable copy (new id, not readonly)', () => {
    const c = clonePreset(PRESETS[1]);
    expect(c.id).not.toBe(PRESETS[1].id);
    expect(c.readonly).toBe(false);
    expect(c.layers).toEqual(PRESETS[1].layers);
  });
});
