import { describe, it, expect } from 'vitest';
import { classifyTask, recommendFusions } from '../src/lib/recommend';
import { shapeOf } from '../src/lib/fusionTypes';

describe('classifyTask', () => {
  it('detects code tasks', () => {
    expect(classifyTask('refactor this C++ function and fix the bug').task_type).toBe('code');
  });
  it('detects reasoning tasks', () => {
    expect(classifyTask('rigorously prove this strategy is optimal').task_type).toBe('reasoning');
  });
  it('flags high difficulty for complex prompts', () => {
    expect(classifyTask('design a complex thread-safe architecture').difficulty).toBe('high');
  });
  it('flags budget sensitivity', () => {
    expect(classifyTask('cheap bulk summarize these').budget_sensitivity).toBe('high');
  });
});

describe('recommendFusions', () => {
  it('always returns at least one (a route) and at most four', () => {
    const recs = recommendFusions(classifyTask('hello'));
    expect(recs.length).toBeGreaterThanOrEqual(1);
    expect(recs.length).toBeLessThanOrEqual(4);
    expect(shapeOf(recs[0].preset)).toBe('route');
  });
  it('offers an ensemble for a hard code task', () => {
    const recs = recommendFusions(classifyTask('implement a complex rigorous C++ architecture module'));
    expect(recs.some((r) => shapeOf(r.preset) === 'ensemble')).toBe(true);
  });
  it('offers a pipeline for the hardest reasoning', () => {
    const recs = recommendFusions(classifyTask('rigorously prove this complex hard theorem with full reasoning'));
    expect(recs.some((r) => shapeOf(r.preset) === 'pipeline')).toBe(true);
  });
  it('every recommendation has a positive cost + latency estimate', () => {
    for (const r of recommendFusions(classifyTask('design a complex system'))) {
      expect(r.estCostUsd).toBeGreaterThan(0);
      expect(r.estLatencyMs).toBeGreaterThan(0);
      expect(r.confidence).toBeGreaterThan(0);
    }
  });
});
