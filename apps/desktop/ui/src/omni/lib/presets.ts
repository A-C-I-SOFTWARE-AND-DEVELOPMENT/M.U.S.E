import type { FusionDef, FusionLeg } from './fusionTypes';

// Curated, read-only fusion presets. Cloneable into saved fusions. Each is a
// shape of the one MoA executor — see fusionTypes.ts.

const leg = (model: string, extra: Partial<FusionLeg> = {}): FusionLeg => ({ model, role: 'proposer', ...extra });

let seq = 0;
const def = (d: Omit<FusionDef, 'id' | 'createdAt' | 'readonly'>): FusionDef => ({
  ...d,
  id: `preset-${++seq}`,
  createdAt: 0,
  readonly: true,
});

export const PRESETS: FusionDef[] = [
  def({
    name: 'Fast Draft',
    mode: 'route',
    layers: [{ legs: [leg('openrouter/auto:floor')], passPreviousOutputs: false }],
    aggregator: null,
    displayMode: 'unified',
    attest: false,
  }),
  def({
    name: 'Code Triad',
    mode: 'ensemble',
    layers: [
      {
        legs: [
          leg('claude-sonnet-4-5', { systemHint: 'Senior systems engineer — correctness first.' }),
          leg('gpt-4o', { systemHint: 'Pragmatic full-stack engineer.' }),
          leg('openrouter/qwen/qwen-2.5-coder-32b-instruct', { systemHint: 'Specialist coder.' }),
        ],
        passPreviousOutputs: false,
      },
    ],
    aggregator: { model: 'claude-opus-4-1', role: 'aggregator', systemHint: 'Synthesize the strongest, correct, compiling solution from the proposals.' },
    displayMode: 'transparent',
    attest: true,
  }),
  def({
    name: 'Deep Reasoning Council',
    mode: 'graph',
    layers: [
      { legs: [leg('claude-sonnet-4-5'), leg('gpt-4o'), leg('gemini-2.0-flash')], passPreviousOutputs: false },
      { legs: [leg('claude-sonnet-4-5', { role: 'critic' }), leg('gpt-4o', { role: 'critic' })], passPreviousOutputs: true },
    ],
    aggregator: { model: 'claude-opus-4-1', role: 'aggregator', systemHint: 'Weigh the proposals and critiques; produce the most rigorous answer.' },
    displayMode: 'transparent',
    attest: true,
  }),
  def({
    name: 'Creative Bloom',
    mode: 'ensemble',
    layers: [
      {
        legs: [
          leg('claude-sonnet-4-5', { temperature: 1.1 }),
          leg('gpt-4o', { temperature: 1.2 }),
          leg('gemini-2.0-flash', { temperature: 1.1 }),
        ],
        passPreviousOutputs: false,
      },
    ],
    aggregator: { model: 'claude-sonnet-4-5', role: 'aggregator', systemHint: 'Blend the most original ideas into one vivid, coherent piece.' },
    displayMode: 'transparent',
    attest: false,
  }),
  def({
    name: 'Vision + Reason',
    mode: 'route',
    layers: [{ legs: [leg('gemini-2.0-flash')], passPreviousOutputs: false }],
    aggregator: null,
    displayMode: 'unified',
    attest: false,
  }),
  def({
    name: 'Cheap Bulk',
    mode: 'route',
    layers: [{ legs: [leg('openrouter/auto:floor', { temperature: 0.3 })], passPreviousOutputs: false }],
    aggregator: null,
    displayMode: 'unified',
    attest: false,
  }),
  def({
    name: 'Draft → Critique → Finalize',
    mode: 'pipeline',
    layers: [
      { legs: [leg('gpt-4o', { systemHint: 'Draft a complete first answer.' })], passPreviousOutputs: false },
      { legs: [leg('claude-sonnet-4-5', { role: 'critic', systemHint: 'Critique the draft: find gaps, errors, omissions.' })], passPreviousOutputs: true },
      { legs: [leg('claude-opus-4-1', { role: 'aggregator', systemHint: 'Produce the final answer incorporating the critique.' })], passPreviousOutputs: true },
    ],
    aggregator: null,
    displayMode: 'transparent',
    attest: true,
  }),
];

export function clonePreset(p: FusionDef, name?: string): FusionDef {
  return {
    ...structuredClone(p),
    id: `fusion-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
    name: name ?? `${p.name} (copy)`,
    createdAt: Date.now(),
    readonly: false,
    favorite: false,
  };
}
