// Chat client. Two transports, no terminal required:
//   • direct  — straight from the browser via OpenRouter (just paste one key)
//   • gateway — the optional local provider gateway (apps/nexus/server)
// 'auto' picks direct when an OpenRouter key is present, else gateway.

import { hasDirectKey, streamDirect, DIRECT_MODELS } from './directProvider';

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

export function getChatConfig(): ChatConfig {
  try {
    const s = JSON.parse(localStorage.getItem(LS) ?? '{}');
    return {
      baseUrl: s.baseUrl || 'http://127.0.0.1:8782/v1',
      model: s.model || 'openrouter/auto',
      mode: (s.mode as ChatTransport) || 'auto',
    };
  } catch {
    return { baseUrl: 'http://127.0.0.1:8782/v1', model: 'openrouter/auto', mode: 'auto' };
  }
}

export function setChatConfig(c: Partial<ChatConfig>): void {
  localStorage.setItem(LS, JSON.stringify({ ...getChatConfig(), ...c }));
}

/** Resolve 'auto' → 'direct' when a key exists (no gateway needed), else 'gateway'. */
export function effectiveTransport(cfg: ChatConfig = getChatConfig()): 'direct' | 'gateway' {
  if (cfg.mode === 'direct') return 'direct';
  if (cfg.mode === 'gateway') return 'gateway';
  return hasDirectKey() ? 'direct' : 'gateway';
}

export const CHAT_MODELS = [
  'claude-sonnet-4-5',
  'claude-opus-4-1',
  'gpt-4o',
  'gpt-4o-mini',
  'gemini-2.0-flash',
  'openrouter/auto',
];

/** Model list appropriate to the active transport. */
export function modelsFor(cfg: ChatConfig = getChatConfig()): string[] {
  return effectiveTransport(cfg) === 'direct' ? DIRECT_MODELS : CHAT_MODELS;
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
  const res = await fetch(`${cfg.baseUrl.replace(/\/$/, '')}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: cfg.model, messages, stream: true }),
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
