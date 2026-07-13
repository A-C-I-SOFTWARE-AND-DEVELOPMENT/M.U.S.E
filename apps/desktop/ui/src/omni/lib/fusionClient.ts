import type { FusionDef, LegResult } from './fusionTypes';
import type { ChatMessage } from './chat';
import { getChatConfig, effectiveTransport } from './chat';

// Streaming client for the fusion-graph executor (/v1/fusion/completions).
// Plain SSE over the local gateway — provider-agnostic, your keys server-side.

export interface FusionMeta {
  fusion_id: string;
  fusion_name: string;
  mode: string;
  attestation: string | null;
  legs: { model: string; role: string; layer: number; error?: string; content?: string }[];
}

export interface FusionStreamResult {
  output: string;
  meta: FusionMeta | null;
}

/** Run a fusion. onLeg fires per proposer (transparent mode), onAggregate per
 *  final-answer token, returns the full output + provenance meta. */
export async function streamFusion(
  fusion: FusionDef,
  messages: ChatMessage[],
  onLeg: (leg: LegResult) => void,
  onAggregate: (delta: string) => void,
  signal?: AbortSignal,
): Promise<FusionStreamResult> {
  // Direct mode (browser → OpenRouter): run the MoA client-side, no gateway.
  if (effectiveTransport() === 'direct') {
    const { runFusionDirect } = await import('./fusionExec');
    return runFusionDirect(fusion, messages, onLeg, onAggregate);
  }
  const base = getChatConfig().baseUrl.replace(/\/$/, '');
  const res = await fetch(`${base}/fusion/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fusion, messages, stream: true }),
    signal,
  });
  if (!res.ok || !res.body) {
    let detail = '';
    try {
      detail = (await res.json())?.error ?? '';
    } catch {
      /* ignore */
    }
    throw new Error(detail || `gateway ${res.status}`);
  }

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  let output = '';
  let meta: FusionMeta | null = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop() || '';
    for (const line of lines) {
      const t = line.trim();
      if (!t.startsWith('data:')) continue;
      const payload = t.slice(5).trim();
      if (payload === '[DONE]') return { output, meta };
      try {
        const ev = JSON.parse(payload);
        if (ev.object === 'fusion.leg' && ev.leg) {
          onLeg({ model: ev.leg.model, role: ev.leg.role, layer: ev.leg.layer, content: ev.leg.content ?? '', error: ev.leg.error });
        } else if (ev.object === 'chat.completion.chunk') {
          const delta = ev.choices?.[0]?.delta?.content;
          if (delta) {
            output += delta;
            onAggregate(delta);
          }
        } else if (ev.object === 'fusion.done') {
          meta = ev.fusion;
        }
      } catch {
        /* skip partial */
      }
    }
  }
  return { output, meta };
}
