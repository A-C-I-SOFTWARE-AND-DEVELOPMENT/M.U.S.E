import type { FusionDef, FusionLeg, FusionMode } from './fusionTypes';
import matrix from './capabilityMatrix.json';

// ============================================================================
// Recommendation engine — pure & testable. Classify a task, then build 2–4
// candidate fusions from the capability matrix. Classification here is a local
// keyword heuristic (so it works offline and is deterministic); a gateway model
// can refine it, but the matching is pure.
// ============================================================================

export type TaskType = 'code' | 'reasoning' | 'creative' | 'vision' | 'long-context' | 'tools' | 'general';

export interface TaskProfile {
  task_type: TaskType;
  difficulty: 'low' | 'medium' | 'high';
  needs: string[];
  latency_sensitivity: 'low' | 'medium' | 'high';
  budget_sensitivity: 'low' | 'medium' | 'high';
}

export interface FusionRecommendation {
  preset: FusionDef;
  rationale: string;
  estCostUsd: number;
  estLatencyMs: number;
  confidence: number;
}

export type CapabilityMatrix = typeof matrix;
export const DEFAULT_MATRIX: CapabilityMatrix = matrix;

const KEYWORDS: Record<TaskType, string[]> = {
  code: ['code', 'function', 'bug', 'refactor', 'compile', 'typescript', 'python', 'c++', 'api', 'implement'],
  reasoning: ['prove', 'reason', 'analy', 'why', 'strategy', 'plan', 'math', 'logic', 'decide', 'trade-off'],
  creative: ['write', 'story', 'poem', 'creative', 'brainstorm', 'name', 'slogan', 'imagine'],
  vision: ['image', 'photo', 'screenshot', 'diagram', 'picture', 'ocr', 'chart'],
  'long-context': ['summarize', 'document', 'transcript', 'long', 'book', 'whole', 'entire'],
  tools: ['call', 'tool', 'function-call', 'api call', 'execute', 'browse', 'search the'],
  general: [],
};

/** Deterministic local classifier (heuristic — refine with a model if desired). */
export function classifyTask(text: string): TaskProfile {
  const t = text.toLowerCase();
  let best: TaskType = 'general';
  let bestScore = 0;
  (Object.keys(KEYWORDS) as TaskType[]).forEach((k) => {
    const score = KEYWORDS[k].reduce((n, kw) => n + (t.includes(kw) ? 1 : 0), 0);
    if (score > bestScore) {
      bestScore = score;
      best = k;
    }
  });
  const wordCount = t.split(/\s+/).length;
  const difficulty = /\b(complex|hard|rigorous|optimi|architecture|prove)\b/.test(t) || wordCount > 60 ? 'high' : wordCount > 20 ? 'medium' : 'low';
  const latency_sensitivity = /\b(quick|fast|asap|now|draft)\b/.test(t) ? 'high' : 'medium';
  const budget_sensitivity = /\b(cheap|bulk|free|budget)\b/.test(t) ? 'high' : 'medium';
  return { task_type: best, difficulty, needs: best === 'general' ? [] : [best], latency_sensitivity, budget_sensitivity };
}

const COST: Record<string, number> = {
  'claude-opus-4-1': 0.015,
  'claude-sonnet-4-5': 0.003,
  'gpt-4o': 0.005,
  'gemini-2.0-flash': 0.0004,
  'openrouter/auto': 0.002,
  'openrouter/auto:floor': 0.0005,
  'openrouter/auto:exacto': 0.004,
  'openrouter/qwen/qwen-2.5-coder-32b-instruct': 0.0009,
};
const costOf = (m: string) => COST[m] ?? 0.003;

function mkDef(name: string, mode: FusionMode, proposers: string[], aggregator: string | null, attest: boolean): FusionDef {
  const legs: FusionLeg[] = proposers.map((m) => ({ model: m, role: 'proposer' }));
  return {
    id: `rec-${name.toLowerCase().replace(/\s+/g, '-')}-${Math.random().toString(36).slice(2, 6)}`,
    name,
    mode,
    layers: mode === 'pipeline'
      ? legs.map((l, i) => ({ legs: [l], passPreviousOutputs: i > 0 }))
      : [{ legs, passPreviousOutputs: false }],
    aggregator: aggregator ? { model: aggregator, role: 'aggregator' } : null,
    displayMode: 'transparent',
    attest,
    createdAt: Date.now(),
  };
}

/** Build 2–4 ranked fusion recommendations for a task profile. */
export function recommendFusions(task: TaskProfile, m: CapabilityMatrix = DEFAULT_MATRIX): FusionRecommendation[] {
  const entry = m.tasks[task.task_type] ?? m.tasks.general;
  const ranked = entry.rankedModels;
  const recs: FusionRecommendation[] = [];

  // 1) Always offer a fast/cheap route.
  const cheap = task.budget_sensitivity === 'high' ? 'openrouter/auto:floor' : ranked[0];
  recs.push({
    preset: mkDef('Fast Route', 'route', [cheap], null, false),
    rationale: `Single best model for ${task.task_type}; lowest latency/cost.`,
    estCostUsd: costOf(cheap),
    estLatencyMs: 1500,
    confidence: task.difficulty === 'low' ? 0.9 : 0.6,
  });

  // 2) Quality ensemble for medium/high difficulty.
  if (task.difficulty !== 'low' && ranked.length >= 2 && entry.aggregator) {
    const proposers = ranked.slice(0, 3);
    recs.push({
      preset: mkDef('Quality Council', 'ensemble', proposers, entry.aggregator, true),
      rationale: `${proposers.length} proposers synthesized by ${entry.aggregator} — MoA wisdom for a hard ${task.task_type} task.`,
      estCostUsd: proposers.reduce((s, p) => s + costOf(p), 0) + costOf(entry.aggregator),
      estLatencyMs: 4000,
      confidence: 0.85,
    });
  }

  // 3) Pipeline for the hardest reasoning (draft -> critique -> finalize).
  if (task.difficulty === 'high' && (task.task_type === 'reasoning' || task.task_type === 'code')) {
    const finalizer = entry.aggregator ?? ranked[0];
    recs.push({
      preset: mkDef('Refine Pipeline', 'pipeline', [ranked[0], ranked[1] ?? ranked[0], finalizer], null, true),
      rationale: 'Draft → critique → finalize. Multi-pass refinement for maximum rigor.',
      estCostUsd: (costOf(ranked[0]) + costOf(ranked[1] ?? ranked[0]) + costOf(finalizer)),
      estLatencyMs: 6000,
      confidence: 0.8,
    });
  }

  return recs.slice(0, 4);
}
