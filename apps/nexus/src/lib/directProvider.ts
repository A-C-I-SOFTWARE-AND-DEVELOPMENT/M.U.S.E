// ============================================================================
// Browser-direct provider transport — NO local gateway, NO terminal required.
//
// OpenRouter is an OpenAI-compatible endpoint that (unlike OpenAI/Anthropic
// direct) permits cross-origin browser calls. With one OpenRouter key (entered
// in Settings → Credentials, encrypted at rest) NEXUS reaches Claude / GPT /
// Gemini / 300+ models straight from the PWA. Install → paste key → it works.
// ============================================================================

import { getSecret } from './config';
import type { ChatMessage } from './chat';

const OR_BASE = 'https://openrouter.ai/api/v1';

export function hasDirectKey(): boolean {
  return !!getSecret('OPENROUTER_API_KEY');
}

// Map NEXUS's friendly model ids to OpenRouter ids; pass through anything that
// already looks like an OpenRouter id ("vendor/model" or "openrouter/...").
const MODEL_MAP: Record<string, string> = {
  'claude-sonnet-4-5': 'anthropic/claude-3.7-sonnet',
  'claude-opus-4-1': 'anthropic/claude-3.7-sonnet',
  'gpt-4o': 'openai/gpt-4o',
  'gpt-4o-mini': 'openai/gpt-4o-mini',
  'gemini-2.0-flash': 'google/gemini-2.0-flash-001',
  'openrouter/auto': 'openrouter/auto',
};

export function toOpenRouterModel(model: string): string {
  if (MODEL_MAP[model]) return MODEL_MAP[model];
  if (model.startsWith('openrouter/')) return model.replace(/^openrouter\//, '');
  if (model.includes('/')) return model; // already vendor/model
  return model;
}

export const DIRECT_MODELS = [
  'openrouter/auto',
  'anthropic/claude-3.7-sonnet',
  'openai/gpt-4o',
  'openai/gpt-4o-mini',
  'google/gemini-2.0-flash-001',
  'meta-llama/llama-3.3-70b-instruct',
  'qwen/qwen-2.5-coder-32b-instruct',
];

function headers(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${getSecret('OPENROUTER_API_KEY')}`,
    'HTTP-Referer': typeof location !== 'undefined' ? location.origin : 'https://nexus.local',
    'X-Title': 'NEXUS',
  };
}

/** Streaming completion straight from the browser via OpenRouter. */
export async function streamDirect(
  model: string,
  messages: ChatMessage[],
  onToken: (delta: string) => void,
  signal?: AbortSignal,
): Promise<string> {
  if (!hasDirectKey()) throw new Error('No OpenRouter key — add it in Settings → Credentials');
  const res = await fetch(`${OR_BASE}/chat/completions`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ model: toOpenRouterModel(model), messages, stream: true }),
    signal,
  });
  if (!res.ok || !res.body) {
    let detail = '';
    try { detail = (await res.json())?.error?.message ?? ''; } catch { /* ignore */ }
    throw new Error(detail || `OpenRouter ${res.status}`);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  let full = '';
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
      if (payload === '[DONE]') return full;
      try {
        const delta = JSON.parse(payload)?.choices?.[0]?.delta?.content;
        if (delta) { full += delta; onToken(delta); }
      } catch { /* skip partial */ }
    }
  }
  return full;
}

/** Non-streaming single completion (used by the client-side fusion executor). */
export async function completeDirect(model: string, messages: ChatMessage[], opts: { temperature?: number; system?: string } = {}): Promise<string> {
  if (!hasDirectKey()) throw new Error('No OpenRouter key');
  const msgs = opts.system ? [{ role: 'system' as const, content: opts.system }, ...messages] : messages;
  const res = await fetch(`${OR_BASE}/chat/completions`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ model: toOpenRouterModel(model), messages: msgs, temperature: opts.temperature, stream: false }),
  });
  const d = await res.json();
  if (!res.ok) throw new Error(d?.error?.message || `OpenRouter ${res.status}`);
  return d?.choices?.[0]?.message?.content ?? '';
}
