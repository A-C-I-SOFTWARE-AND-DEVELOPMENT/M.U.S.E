// ============================================================================
// Browser-direct multi-provider transport — NO local gateway, NO terminal.
//
// Routes a model to the best available transport (providers.ts): provider-direct
// where CORS allows (OpenAI shape, Anthropic messages, Gemini OpenAI-compat),
// else OpenRouter, else the gateway. Keys come from the encrypted store.
// ============================================================================

import { getSecret } from './config';
import { resolveModelTransport, providerForModel, configuredProviders, type Transport } from './providers';
import type { ChatMessage } from './chat';

export function hasDirectKey(): boolean {
  // Any browser-direct provider configured, or an OpenRouter key (universal).
  return !!getSecret('OPENROUTER_API_KEY') || configuredProviders().some((p) => p.browserDirect);
}

export function anyProviderReady(): boolean {
  return configuredProviders().length > 0 || !!getSecret('OPENROUTER_API_KEY');
}

// Legacy export kept for callers that still pass a starter model id. 'auto' leads
// (no main provider — MUSE picks any model); the rest are an unranked spread, with
// no vendor privileged as a default.
export const DIRECT_MODELS = [
  'auto', 'openrouter/auto', 'anthropic/claude-3.7-sonnet', 'google/gemini-2.0-flash-001', 'deepseek/deepseek-chat',
];

function keyForDirect(t: Extract<Transport, { kind: 'direct' }>): string {
  return getSecret(t.provider.keyEnv);
}

// ---- OpenAI-shape streaming + completion --------------------------------------
async function streamOpenAI(base: string, key: string, model: string, messages: ChatMessage[], onToken: (d: string) => void, signal?: AbortSignal, extra: Record<string, string> = {}, temperature?: number): Promise<string> {
  const res = await fetch(`${base.replace(/\/$/, '')}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(key ? { Authorization: `Bearer ${key}` } : {}), ...extra },
    body: JSON.stringify({ model, messages, temperature, stream: true }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(await errText(res));
  return readOpenAIStream(res.body, onToken);
}

async function completeOpenAI(base: string, key: string, model: string, messages: ChatMessage[], extra: Record<string, string> = {}, temperature?: number): Promise<string> {
  const res = await fetch(`${base.replace(/\/$/, '')}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(key ? { Authorization: `Bearer ${key}` } : {}), ...extra },
    body: JSON.stringify({ model, messages, temperature, stream: false }),
  });
  const d = await res.json();
  if (!res.ok) throw new Error(d?.error?.message || `${res.status}`);
  return d?.choices?.[0]?.message?.content ?? '';
}

// ---- Anthropic-shape ----------------------------------------------------------
function splitSystem(messages: ChatMessage[]) {
  const system = messages.filter((m) => m.role === 'system').map((m) => m.content).join('\n');
  const conv = messages.filter((m) => m.role !== 'system').map((m) => ({ role: m.role, content: m.content }));
  return { system, conv };
}
function anthropicHeaders(key: string) {
  return { 'Content-Type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01', 'anthropic-dangerous-direct-browser-access': 'true' };
}
async function streamAnthropic(base: string, key: string, model: string, messages: ChatMessage[], onToken: (d: string) => void, signal?: AbortSignal, temperature?: number): Promise<string> {
  const { system, conv } = splitSystem(messages);
  const res = await fetch(`${base.replace(/\/$/, '')}/v1/messages`, {
    method: 'POST', headers: anthropicHeaders(key),
    body: JSON.stringify({ model, max_tokens: 2048, temperature, system: system || undefined, messages: conv, stream: true }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(await errText(res));
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '', full = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split('\n'); buf = lines.pop() || '';
    for (const line of lines) {
      if (!line.startsWith('data:')) continue;
      try { const ev = JSON.parse(line.slice(5).trim()); if (ev.type === 'content_block_delta' && ev.delta?.text) { full += ev.delta.text; onToken(ev.delta.text); } } catch { /* skip */ }
    }
  }
  return full;
}
async function completeAnthropic(base: string, key: string, model: string, messages: ChatMessage[], temperature?: number): Promise<string> {
  const { system, conv } = splitSystem(messages);
  const res = await fetch(`${base.replace(/\/$/, '')}/v1/messages`, {
    method: 'POST', headers: anthropicHeaders(key),
    body: JSON.stringify({ model, max_tokens: 2048, temperature, system: system || undefined, messages: conv }),
  });
  const d = await res.json();
  if (!res.ok) throw new Error(d?.error?.message || `${res.status}`);
  return (d.content || []).map((c: any) => c.text || '').join('');
}

// ---- shared SSE reader + error -------------------------------------------------
async function readOpenAIStream(body: ReadableStream<Uint8Array>, onToken: (d: string) => void): Promise<string> {
  const reader = body.getReader();
  const dec = new TextDecoder();
  let buf = '', full = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split('\n'); buf = lines.pop() || '';
    for (const line of lines) {
      const t = line.trim();
      if (!t.startsWith('data:')) continue;
      const payload = t.slice(5).trim();
      if (payload === '[DONE]') return full;
      try { const d = JSON.parse(payload)?.choices?.[0]?.delta?.content; if (d) { full += d; onToken(d); } } catch { /* skip */ }
    }
  }
  return full;
}
async function errText(res: Response): Promise<string> {
  try { return (await res.json())?.error?.message || `${res.status}`; } catch { return `${res.status}`; }
}

const OR_HEADERS = { 'HTTP-Referer': typeof location !== 'undefined' ? location.origin : 'https://nexus.local', 'X-Title': 'NEXUS' };

/** Stream a model via its resolved transport. Throws on 'unavailable'/'gateway'. */
export async function streamDirect(model: string, messages: ChatMessage[], onToken: (d: string) => void, signal?: AbortSignal): Promise<string> {
  const t = resolveModelTransport(model);
  if (t.kind === 'unavailable') throw new Error(t.reason);
  if (t.kind === 'gateway') throw new Error('gateway-transport'); // chat.ts handles the gateway path
  if (t.kind === 'openrouter') return streamOpenAI(t.baseUrl, getSecret('OPENROUTER_API_KEY'), t.model, messages, onToken, signal, OR_HEADERS);
  // direct
  const key = keyForDirect(t);
  if (t.provider.shape === 'anthropic') return streamAnthropic(t.baseUrl, key, t.model.split('/').pop()!, messages, onToken, signal);
  return streamOpenAI(t.baseUrl, key, t.model.replace(new RegExp(`^${t.provider.id}/`), ''), messages, onToken, signal);
}

/** Non-streaming single completion (used by the client-side fusion executor). */
export async function completeDirect(model: string, messages: ChatMessage[], opts: { temperature?: number; system?: string } = {}): Promise<string> {
  const msgs = opts.system ? [{ role: 'system' as const, content: opts.system }, ...messages] : messages;
  const t = resolveModelTransport(model);
  if (t.kind === 'unavailable') throw new Error(t.reason);
  if (t.kind === 'gateway') throw new Error('gateway-transport');
  if (t.kind === 'openrouter') return completeOpenAI(t.baseUrl, getSecret('OPENROUTER_API_KEY'), t.model, msgs, OR_HEADERS, opts.temperature);
  const key = keyForDirect(t);
  if (t.provider.shape === 'anthropic') return completeAnthropic(t.baseUrl, key, t.model.split('/').pop()!, msgs, opts.temperature);
  return completeOpenAI(t.baseUrl, key, t.model.replace(new RegExp(`^${t.provider.id}/`), ''), msgs, OR_HEADERS, opts.temperature);
}

export { providerForModel };
