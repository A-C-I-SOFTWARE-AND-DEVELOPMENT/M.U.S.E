import { describe, it, expect } from 'vitest';
import { assembleAgentContext, scopePack, cppTrioSeed } from '../src/lib/forge';
import { planFanout, checkBudget, reduceTiers, concurrencyCeiling, type SiloedTask } from '../src/lib/fleet';

describe('forge — agent context assembly', () => {
  const seed = cppTrioSeed();
  it('seeds the C++ specialist trio (3 agents, packs, personas, adapters)', () => {
    expect(seed.agents).toHaveLength(3);
    expect(seed.adapters.every((a) => a.baseModel === 'qwen2.5-coder-14b')).toBe(true);
  });
  it('assembles a scoped, domain-locked context', () => {
    const arch = seed.agents.find((a) => a.name === 'C++ Architect')!;
    const ctx = assembleAgentContext(arch, seed.packs, seed.personas, seed.adapters);
    expect(ctx.scoped).toBe(true);
    expect(ctx.systemPrompt).toMatch(/out of scope/i);
    expect(ctx.systemPrompt).toMatch(/knowledge pack/i);
    expect(ctx.retrievalNamespace).toMatch(/^ns-/);
  });
  it('uses the adapter model only once it is ready', () => {
    const a = seed.agents[0];
    const notReady = assembleAgentContext(a, seed.packs, seed.personas, seed.adapters);
    expect(notReady.model).not.toMatch(/^local\/cpp-/); // adapter status 'none'
    const ready = seed.adapters.map((x) => (x.id === a.adapterId ? { ...x, status: 'ready' as const } : x));
    expect(assembleAgentContext(a, seed.packs, seed.personas, ready).model).toBe(`local/${a.adapterId}`);
  });
  it('scopePack erases all but the allowed docs', () => {
    const pack = { id: 'p', name: 'p', namespace: 'ns', docs: [
      { id: 'd1', name: 'a', bytes: 1, status: 'embedded' as const },
      { id: 'd2', name: 'b', bytes: 1, status: 'embedded' as const },
    ] };
    expect(scopePack(pack, ['d1']).docs.map((d) => d.id)).toEqual(['d1']);
  });
});

describe('fleet — fan-out planning + budget', () => {
  const tasks = (n: number): SiloedTask[] => Array.from({ length: n }, (_, i) => ({ id: `t${i}`, instruction: 'x', timeoutSec: 60, verifier: 'schema' }));

  it('projects cost and wall-clock with the concurrency cap', () => {
    const plan = planFanout('goal', tasks(1000), { concurrency: 250, perTaskUsd: 0.002, perTaskSec: 20 });
    expect(plan.estCostUsd).toBeCloseTo(2.0, 5);
    expect(plan.estWallclockSec).toBe(4 * 20); // 1000/250 = 4 waves
  });
  it('budget guard blocks an over-cap fan-out', () => {
    expect(checkBudget(5.0, 2.0).allowed).toBe(false);
    expect(checkBudget(1.0, 2.0).allowed).toBe(true);
  });
  it('reduceTiers reduces hierarchically toward 1', () => {
    const tiers = reduceTiers(1000, 10);
    expect(tiers[0]).toBe(1000);
    expect(tiers[tiers.length - 1]).toBe(1);
    // monotonically decreasing
    for (let i = 1; i < tiers.length; i++) expect(tiers[i]).toBeLessThan(tiers[i - 1]);
  });
  it('honest concurrency ceiling: local << cloud', () => {
    expect(concurrencyCeiling('local').max).toBeLessThan(concurrencyCeiling('cloud').max);
    expect(concurrencyCeiling('local').note).toMatch(/not thousands/i);
  });
});
