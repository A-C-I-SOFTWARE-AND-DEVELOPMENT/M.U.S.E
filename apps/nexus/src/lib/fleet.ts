// ============================================================================
// Fleet — massive 1-minute siloed fan-out. The unit is a SiloedTask: a bounded
// contract + isolated context + a verifier gate + an AXIOM block. The same
// envelope that runs thousands in parallel is the one that makes a specialist.
// Pure planning/budget/reduce logic here; the server (Hatchet behind an
// Orchestrator interface) executes via /v1/cockpit/orchestrate + /jobs.
// ============================================================================

export type Verifier = 'schema' | 'judge' | 'none';

export interface SiloedTask {
  id: string;
  instruction: string;
  timeoutSec: number; // ~60 — the "one minute" discipline
  knowledgePackId?: string;
  personaId?: string;
  adapterId?: string;
  fusionId?: string;
  verifier: Verifier;
}

export interface FanoutPlan {
  goal: string;
  tasks: SiloedTask[];
  concurrency: number; // slot cap
  estCostUsd: number;
  estWallclockSec: number; // with the concurrency cap
}

export interface BudgetGuard {
  capUsd: number;
  projectedUsd: number;
  allowed: boolean;
  reason?: string;
}

/** Pure: project cost + wall-clock for a fan-out, given a per-task cost/latency. */
export function planFanout(
  goal: string,
  tasks: SiloedTask[],
  opts: { concurrency?: number; perTaskUsd?: number; perTaskSec?: number } = {},
): FanoutPlan {
  const concurrency = Math.max(1, opts.concurrency ?? 256);
  const perTaskUsd = opts.perTaskUsd ?? 0.002;
  const perTaskSec = opts.perTaskSec ?? 20;
  const waves = Math.ceil(tasks.length / concurrency);
  return {
    goal,
    tasks,
    concurrency,
    estCostUsd: tasks.length * perTaskUsd,
    estWallclockSec: waves * perTaskSec,
  };
}

/** Pure: enforce a hard budget cap before launch (the cost-runaway guard). */
export function checkBudget(projectedUsd: number, capUsd: number): BudgetGuard {
  const allowed = projectedUsd <= capUsd;
  return {
    capUsd,
    projectedUsd,
    allowed,
    reason: allowed ? undefined : `projected $${projectedUsd.toFixed(2)} exceeds cap $${capUsd.toFixed(2)}`,
  };
}

/**
 * Pure: hierarchical reduce plan. Never dump N raw outputs into one context;
 * reduce in tiers (e.g. 1000 -> 100 -> 10 -> 1). Returns the tier sizes.
 */
export function reduceTiers(n: number, fanIn = 10): number[] {
  if (n <= 1) return [n];
  const tiers = [n];
  let cur = n;
  while (cur > 1) {
    cur = Math.ceil(cur / fanIn);
    tiers.push(cur);
  }
  return tiers;
}

/** The honest local-vs-cloud concurrency ceiling, surfaced in the UI. */
export function concurrencyCeiling(mode: 'local' | 'cloud' | 'hybrid'): { max: number; note: string } {
  switch (mode) {
    case 'local':
      return { max: 32, note: 'One consumer GPU: tens of concurrent small-model tasks (vLLM continuous batching). Not thousands.' };
    case 'cloud':
      return { max: 4096, note: 'Cloud/API fan-out with rate-limit management + budget caps. Thousands achievable.' };
    case 'hybrid':
      return { max: 4096, note: 'Cheap subtasks local, the rest burst to cloud. The practical answer for true scale.' };
  }
}
