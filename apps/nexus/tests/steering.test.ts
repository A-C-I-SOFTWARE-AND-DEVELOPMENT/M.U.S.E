import { describe, it, expect } from 'vitest';
import {
  positionToWeights,
  balancedWeights,
  deriveGlowState,
  weightsToInference,
  dominantVertex,
  weightsToPosition,
  vertexPositions,
  blendOklch,
  BALANCED_GREEN,
  CONTEMPLATION_GLOW,
  NEUTRAL_8,
} from '../src/lib/steering';
import { DEFAULT_PRESET } from '../src/lib/vertices';
import type { WeightVector } from '../src/lib/types';

const V = DEFAULT_PRESET;

function maxedAt(key: string, value = 0.8): WeightVector {
  const rest = (1 - value) / (V.length - 1);
  const w: WeightVector = {};
  V.forEach((v) => (w[v.key] = v.key === key ? value : rest));
  return w;
}

describe('weight math', () => {
  it('center node yields ~equal, normalized weights', () => {
    const w = positionToWeights({ x: 0, y: 0 }, V);
    const sum = Object.values(w).reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(1, 5);
    Object.values(w).forEach((val) => expect(val).toBeCloseTo(NEUTRAL_8, 2));
  });

  it('normalizes to 1.0 for an off-center node', () => {
    const top = vertexPositions(V.length, 1)[0]; // reasoning vertex (top)
    const w = positionToWeights({ x: top.x * 0.9, y: top.y * 0.9 }, V);
    const sum = Object.values(w).reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(1, 5);
  });

  it('dragging toward a vertex makes it dominant', () => {
    const codingIdx = V.findIndex((v) => v.key === 'coding');
    const p = vertexPositions(V.length, 1)[codingIdx];
    const w = positionToWeights({ x: p.x * 0.95, y: p.y * 0.95 }, V);
    expect(dominantVertex(w)).toBe('coding');
  });

  it('balancedWeights sum to 1 and are all equal', () => {
    const w = balancedWeights(V);
    expect(Object.values(w).reduce((a, b) => a + b, 0)).toBeCloseTo(1, 6);
    expect(new Set(Object.values(w).map((v) => v.toFixed(6))).size).toBe(1);
  });

  it('weightsToPosition of balanced vector is the center', () => {
    const p = weightsToPosition(balancedWeights(V), V);
    expect(p.x).toBeCloseTo(0, 6);
    expect(p.y).toBeCloseTo(0, 6);
  });
});

describe('deriveGlowState', () => {
  it('balanced vector glows harmony green, no pulse', () => {
    const g = deriveGlowState(balancedWeights(V), V);
    expect(g.color.toLowerCase()).toBe(BALANCED_GREEN.toLowerCase());
    expect(g.pulse).toBe(false);
    expect(g.label).toBe('Balanced');
  });

  it('maxing contemplation glows warm orange (explicit requirement)', () => {
    const g = deriveGlowState(maxedAt('contemplation', 0.6), V);
    expect(g.color.toLowerCase()).toBe(CONTEMPLATION_GLOW.toLowerCase());
    expect(g.label).toBe('Contemplation-dominant');
  });

  it('single dominant vertex uses its accent color', () => {
    const g = deriveGlowState(maxedAt('coding', 0.6), V);
    const codingAccent = V.find((v) => v.key === 'coding')!.accent;
    expect(g.color.toLowerCase()).toBe(codingAccent.toLowerCase());
  });

  it('any weight > 0.7 sets pulse', () => {
    const g = deriveGlowState(maxedAt('coding', 0.75), V);
    expect(g.pulse).toBe(true);
  });

  it('two close leaders produce a blended label', () => {
    const w: WeightVector = {};
    V.forEach((v) => (w[v.key] = 0.02));
    w.coding = 0.4;
    w.reasoning = 0.38;
    const g = deriveGlowState(w, V);
    expect(g.label).toMatch(/Coding \+ Reasoning|Reasoning \+ Coding/);
  });
});

describe('weightsToInference', () => {
  it('creativity raises temperature above coding-heavy baseline', () => {
    const creative = weightsToInference(maxedAt('creativity', 0.7));
    const codey = weightsToInference(maxedAt('coding', 0.7));
    expect(creative.temperature).toBeGreaterThan(codey.temperature);
  });

  it('temperature stays clamped within 0..2', () => {
    const t = weightsToInference(maxedAt('creativity', 1)).temperature;
    expect(t).toBeGreaterThanOrEqual(0);
    expect(t).toBeLessThanOrEqual(2);
  });

  it('contemplation buys more thinking tokens', () => {
    const deep = weightsToInference(maxedAt('contemplation', 0.8));
    const shallow = weightsToInference(balancedWeights(V));
    expect(deep.maxThinkingTokens).toBeGreaterThan(shallow.maxThinkingTokens);
  });

  it('factuality raises grounding strength (0..1)', () => {
    const g = weightsToInference(maxedAt('factuality', 0.8)).groundingStrength;
    expect(g).toBeGreaterThan(0.5);
    expect(g).toBeLessThanOrEqual(1);
  });

  it('empathy shifts the system style hint to warm', () => {
    const hint = weightsToInference(maxedAt('empathy', 0.5)).systemStyleHint;
    expect(hint).toContain('empathetic');
  });
});

describe('blendOklch', () => {
  it('t=0 and t=1 return the endpoints', () => {
    expect(blendOklch('#3DD68C', '#FFB020', 0).toLowerCase()).toBe('#3dd68c');
    expect(blendOklch('#3DD68C', '#FFB020', 1).toLowerCase()).toBe('#ffb020');
  });

  it('midpoint is a valid distinct hex', () => {
    const mid = blendOklch('#3DD68C', '#FFB020', 0.5);
    expect(mid).toMatch(/^#[0-9a-f]{6}$/i);
    expect(mid.toLowerCase()).not.toBe('#3dd68c');
  });
});
