// Chat client. Two transports, no terminal required:
//   • direct  — straight from the browser via OpenRouter (just paste one key)
//   • gateway — the optional local provider gateway (apps/nexus/server)
// 'auto' picks direct when an OpenRouter key is present, else gateway.

import { streamDirect } from './directProvider';
import { resolveModelTransport, configuredProviders, bestAvailableModel } from './providers';

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

const LS = 'nexus.chat.v1';

export type ChatTransport = 'auto' | 'direct' | 'gateway';

export interface ChatConfig {
  baseUrl: string;
  model: string;
  mode: ChatTransport;
}

// 'auto' is the default model id on purpose: MUSE is provider-agnostic with NO
// main/default vendor. It resolves at call time to whatever the owner can use
// (see bestAvailableModel) so any model can be used at any time.
export function getChatConfig(): ChatConfig {
  try {
    const s = JSON.parse(localStorage.getItem(LS) ?? '{}');
    return {
      baseUrl: s.baseUrl || 'http://127.0.0.1:8782/v1',
      model: s.model || 'auto',
      mode: (s.mode as ChatTransport) || 'auto',
    };
  } catch {
    return { baseUrl: 'http://127.0.0.1:8782/v1', model: 'auto', mode: 'auto' };
  }
}

export function setChatConfig(c: Partial<ChatConfig>): void {
  localStorage.setItem(LS, JSON.stringify({ ...getChatConfig(), ...c }));
}

/** The transport that will actually serve this config's model. 'gateway' takes
 *  the gateway fetch path; everything else (direct/openrouter/unavailable) goes
 *  through streamDirect (which surfaces an honest error if unavailable). */
export function effectiveTransport(cfg: ChatConfig = getChatConfig()): 'direct' | 'gateway' {
  if (cfg.mode === 'gateway') return 'gateway';
  if (cfg.mode === 'direct') return 'direct';
  return resolveModelTransport(cfg.model).kind === 'gateway' ? 'gateway' : 'direct';
}

/** A quick sync model list for the dropdown: curated models of configured
 *  providers (+ openrouter/auto). The Models tab has the full async catalog. */
export function modelsFor(_cfg: ChatConfig = getChatConfig()): string[] {
  // 'auto' (no main provider — pick any model) leads; then every configured
  // provider's models, no vendor privileged.
  const out = new Set<string>(['auto', 'openrouter/auto']);
  for (const p of configuredProviders()) {
    for (const m of p.curated ?? []) out.add(m.includes('/') || p.id === 'openrouter' ? m : `${p.id}/${m}`);
  }
  return [...out];
}

/**
 * Stream a completion. Calls onToken with each text delta; resolves with the
 * full text. Throws on transport / API error.
 */
export async function streamChat(
  cfg: ChatConfig,
  messages: ChatMessage[],
  onToken: (delta: string) => void,
  signal?: AbortSignal,
): Promise<string> {
  // Direct (browser → OpenRouter): no local gateway, no terminal.
  if (effectiveTransport(cfg) === 'direct') {
    return streamDirect(cfg.model, messages, onToken, signal);
  }
  // Resolve the neutral 'auto' to a concrete model for the gateway router.
  const gwModel = cfg.model === 'auto' ? bestAvailableModel() : cfg.model;
  const res = await fetch(`${cfg.baseUrl.replace(/\/$/, '')}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: gwModel, messages, stream: true }),
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
        if (delta) {
          full += delta;
          onToken(delta);
        }
      } catch {
        /* skip partial frame */
      }
    }
  }
  return full;
}

export async function gatewayHealth(baseUrl: string): Promise<Record<string, boolean> | null> {
  try {
    const res = await fetch(`${baseUrl.replace(/\/v1$/, '')}/health`);
    if (!res.ok) return null;
    return (await res.json())?.providers ?? null;
  } catch {
    return null;
  }
}
