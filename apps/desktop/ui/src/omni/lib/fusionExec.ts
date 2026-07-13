import type { FusionDef, LegResult } from './fusionTypes';
import type { ChatMessage } from './chat';
import { completeDirect } from './directProvider';
import type { FusionStreamResult } from './fusionClient';

// Client-side Mixture-of-Agents executor for DIRECT mode (browser → OpenRouter,
// no gateway). Mirrors server/fusion-executor.mjs: parallel proposers per layer,
// optional aggregator that synthesizes, optional attestation.

const AGG_SYSTEM =
  'You are an expert aggregator. You have the user task and several candidate ' +
  'responses. Synthesize a single, superior answer: combine the strongest correct ' +
  'elements, resolve contradictions, fix errors; do not merely pick one. Respond only with the final answer.';

function labeled(legs: LegResult[]): string {
  return legs.map((r, i) => `[Response ${i + 1}${r.error ? ' (failed)' : ''}]\n${r.error ? '(no output)' : r.content}`).join('\n\n');
}

function hash(obj: unknown): string {
  const s = JSON.stringify(obj);
  let h1 = 0x811c9dc5, h2 = 0xcbf29ce4;
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 0x01000193) >>> 0;
    h2 = Math.imul(h2 ^ ((c << 1) | 1), 0x01000193) >>> 0;
  }
  return h1.toString(16).padStart(8, '0') + h2.toString(16).padStart(8, '0');
}

export async function runFusionDirect(
  fusion: FusionDef,
  messages: ChatMessage[],
  onLeg: (leg: LegResult) => void,
  onAggregate: (delta: string) => void,
): Promise<FusionStreamResult> {
  const allLegs: LegResult[] = [];
  let prior: LegResult[] = [];

  for (let li = 0; li < fusion.layers.length; li++) {
    const layer = fusion.layers[li];
    const ctx: ChatMessage[] = layer.passPreviousOutputs && prior.length
      ? [{ role: 'user', content: `Prior candidate responses to build on / critique:\n\n${labeled(prior)}` }]
      : [];
    const results = await Promise.all(
      layer.legs.map(async (leg): Promise<LegResult> => {
        const started = Date.now();
        try {
          const content = await completeDirect(leg.model, [...messages, ...ctx], { temperature: leg.temperature, system: leg.systemHint });
          const r: LegResult = { model: leg.model, role: leg.role || 'proposer', layer: li, content, latencyMs: Date.now() - started };
          if (fusion.displayMode === 'transparent') onLeg(r);
          return r;
        } catch (e) {
          const r: LegResult = { model: leg.model, role: leg.role || 'proposer', layer: li, content: '', error: String((e as Error).message ?? e), latencyMs: Date.now() - started };
          if (fusion.displayMode === 'transparent') onLeg(r);
          return r;
        }
      }),
    );
    allLegs.push(...results);
    prior = results;
  }

  let output: string;
  if (fusion.aggregator) {
    output = await completeDirect(
      fusion.aggregator.model,
      [...messages, { role: 'user', content: `Candidate responses:\n\n${labeled(prior)}` }],
      { temperature: fusion.aggregator.temperature ?? 0.3, system: fusion.aggregator.systemHint || AGG_SYSTEM },
    );
    allLegs.push({ model: fusion.aggregator.model, role: 'aggregator', layer: fusion.layers.length, content: output });
  } else {
    output = prior.map((r) => r.content).filter(Boolean).join('\n\n');
  }

  // Stream the (already-computed) final answer in word chunks for UX parity.
  for (const w of output.split(/(\s+)/)) onAggregate(w);

  const attestation = fusion.attest
    ? `fusion:${hash({ name: fusion.name, mode: fusion.mode, models: allLegs.map((l) => l.model), out: output })}`
    : null;

  return {
    output,
    meta: {
      fusion_id: fusion.id,
      fusion_name: fusion.name,
      mode: fusion.mode,
      attestation,
      legs: allLegs.map((l) => ({ model: l.model, role: l.role, layer: l.layer, error: l.error, content: fusion.displayMode === 'transparent' ? l.content : undefined })),
    },
  };
}
