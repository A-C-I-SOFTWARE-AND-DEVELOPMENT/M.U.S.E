// Chat client. Three honest transports, no terminal required:
//   • server  — the hosted app's own /api/chat edge function (keys live in
//               process.env on the server, never in the browser). The public
//               default on a hosted https origin when no browser key is set.
//   • direct  — straight from the browser via the user's own provider key /
//               OpenRouter (no server, no terminal).
//   • gateway — the optional local provider gateway (apps/nexus/server).

import { streamDirect, anyProviderReady } from './directProvider';
import { resolveModelTransport, configuredProviders, bestAvailableModel } from './providers';

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

const LS = 'nexus.chat.v1';

export type ChatTransport = 'auto' | 'server' | 'direct' | 'gateway';

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

/** True when the page is served from a hosted https origin (not a local file://
 *  or http://localhost dev/Termux origin). Only there does the app's own
 *  /api/chat edge function exist to serve chat with server-held keys. */
function hostedHttpsOrigin(): boolean {
  if (typeof window === 'undefined') return false;
  return window.location.protocol === 'https:';
}

/** The transport that will actually serve this config's model. 'server' POSTs to
 *  the app's own /api/chat (keys in process.env); 'gateway' takes the gateway
 *  fetch path; everything else (direct/openrouter/unavailable) goes through
 *  streamDirect (which surfaces an honest error if unavailable).
 *
 *  Public default: on a hosted https origin with NO browser-direct provider key,
 *  route to 'server' so a freshly-loaded hosted app can chat (the edge function
 *  honestly returns 501 if the server has no key either). An explicit mode, a
 *  configured browser key, or a non-https origin keeps the prior direct/gateway
 *  selection unchanged. */
export function effectiveTransport(cfg: ChatConfig = getChatConfig()): 'server' | 'direct' | 'gateway' {
  if (cfg.mode === 'server') return 'server';
  if (cfg.mode === 'gateway') return 'gateway';
  if (cfg.mode === 'direct') return 'direct';
  // 'auto': prefer the hosted server only when the browser has no key of its own.
  if (hostedHttpsOrigin() && !anyProviderReady()) return 'server';
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
  const transport = effectiveTransport(cfg);

  // Direct (browser → the user's own provider / OpenRouter): no server, no terminal.
  if (transport === 'direct') {
    return streamDirect(cfg.model, messages, onToken, signal);
  }

  let res: Response;
  if (transport === 'server') {
    // Hosted server chat: POST to the app's own /api/chat edge function. Keys
    // live in process.env on the server and never reach the browser. The model
    // id is passed through ('auto' is resolved server-side).
    res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: cfg.model, messages }),
      signal,
    });
    if (res.status === 501) {
      // The server has no provider key — honest disconnected state, not a fake
      // reply. The empty-state / status dot reads this as "server not configured".
      throw new Error('server chat not configured');
    }
  } else {
    // Gateway (local MUSE provider gateway). Resolve neutral 'auto' first.
    const gwModel = cfg.model === 'auto' ? bestAvailableModel() : cfg.model;
    res = await fetch(`${cfg.baseUrl.replace(/\/$/, '')}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: gwModel, messages, stream: true }),
      signal,
    });
  }
  if (!res.ok || !res.body) {
    let detail = '';
    try {
      detail = (await res.json())?.error ?? '';
    } catch {
      /* ignore */
    }
    throw new Error(detail || `${transport} ${res.status}`);
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
