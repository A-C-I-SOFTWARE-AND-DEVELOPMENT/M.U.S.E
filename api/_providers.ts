// ============================================================================
// Runtime-neutral per-provider request building + SSE normalization.
//
// Server-only (Edge/Node) helper for api/chat.ts. It maps a model id to the
// upstream provider, builds the upstream streaming request, and normalizes the
// upstream SSE into the OpenAI delta frame shape the NEXUS client already parses
// (src/lib/directProvider.ts -> readOpenAIStream / src/lib/chat.ts):
//
//   data: {"choices":[{"delta":{"content":"..."}}]}\n\n
//   ...
//   data: [DONE]\n\n
//
// NO browser-only imports (no config.ts, no securestore.ts). Secrets are read
// from process.env by the caller and passed in — never VITE_-prefixed, never
// shipped to the browser. The provider table below is a self-contained,
// server-side subset that mirrors src/lib/providers.ts shapes/baseUrls; it must
// not import that browser module (it pulls in config.ts/securestore.ts).
// ============================================================================

// Minimal ambient declaration for the server-only secret source. Avoids a hard
// dependency on @types/node while staying compatible with it (declaration
// merging: `process.env` is an optional string map). Secrets are read here and
// never exposed to the browser; never VITE_-prefixed.
declare const process: { env?: Record<string, string | undefined> } | undefined;

export type ProviderShape = 'openai' | 'anthropic' | 'gemini-openai';

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

interface ServerProvider {
  id: string;
  baseUrl: string;
  keyEnv: string;
  shape: ProviderShape;
  /** Vendor slug used when routing this model through OpenRouter. */
  openrouterPrefix?: string;
}

// Server-side provider table. Mirrors the browserDirect/key conventions of
// src/lib/providers.ts but stays import-free so it can run in the Edge runtime.
// Only OpenAI-shape, Anthropic-shape, and Gemini-OpenAI-shape HTTP providers are
// listed (OAuth/IAM/gateway-only providers are intentionally omitted server-side).
const SERVER_PROVIDERS: ServerProvider[] = [
  { id: 'openrouter', baseUrl: 'https://openrouter.ai/api/v1', keyEnv: 'OPENROUTER_API_KEY', shape: 'openai' },
  { id: 'anthropic', baseUrl: 'https://api.anthropic.com', keyEnv: 'ANTHROPIC_API_KEY', shape: 'anthropic', openrouterPrefix: 'anthropic' },
  { id: 'openai', baseUrl: 'https://api.openai.com/v1', keyEnv: 'OPENAI_API_KEY', shape: 'openai', openrouterPrefix: 'openai' },
  { id: 'google', baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai', keyEnv: 'GEMINI_API_KEY', shape: 'gemini-openai', openrouterPrefix: 'google' },
  { id: 'groq', baseUrl: 'https://api.groq.com/openai/v1', keyEnv: 'GROQ_API_KEY', shape: 'openai' },
  { id: 'mistral', baseUrl: 'https://api.mistral.ai/v1', keyEnv: 'MISTRAL_API_KEY', shape: 'openai', openrouterPrefix: 'mistralai' },
  { id: 'deepseek', baseUrl: 'https://api.deepseek.com', keyEnv: 'DEEPSEEK_API_KEY', shape: 'openai', openrouterPrefix: 'deepseek' },
  { id: 'xai', baseUrl: 'https://api.x.ai/v1', keyEnv: 'XAI_API_KEY', shape: 'openai', openrouterPrefix: 'x-ai' },
  { id: 'together', baseUrl: 'https://api.together.xyz/v1', keyEnv: 'TOGETHER_API_KEY', shape: 'openai' },
  { id: 'perplexity', baseUrl: 'https://api.perplexity.ai', keyEnv: 'PERPLEXITY_API_KEY', shape: 'openai' },
];

const BY_ID = Object.fromEntries(SERVER_PROVIDERS.map((p) => [p.id, p]));
const OPENROUTER = BY_ID.openrouter;

/** Resolve which server provider a model id belongs to (mirrors providerForModel). */
function providerForModel(model: string): ServerProvider {
  if (model.includes('/')) {
    const head = model.split('/')[0];
    if (BY_ID[head]) return BY_ID[head];
    // vendor slugs (anthropic/, openai/, google/) -> OpenRouter
    return OPENROUTER;
  }
  if (model.startsWith('claude')) return BY_ID.anthropic;
  if (model.startsWith('gpt') || model.startsWith('o1') || model.startsWith('o3') || model.startsWith('o4')) return BY_ID.openai;
  if (model.startsWith('gemini')) return BY_ID.google;
  if (model.startsWith('grok')) return BY_ID.xai;
  if (model.startsWith('deepseek')) return BY_ID.deepseek;
  if (model.startsWith('mistral') || model.startsWith('codestral')) return BY_ID.mistral;
  return OPENROUTER;
}

function envKey(name: string): string {
  // process.env is the only secret source; never VITE_-prefixed.
  return (typeof process !== 'undefined' && process.env && process.env[name]) || '';
}

export interface UpstreamPlan {
  /** Fully-built upstream request (URL + RequestInit) ready to fetch(). */
  url: string;
  init: RequestInit;
  /** Upstream SSE shape, so the caller knows how to normalize the stream. */
  shape: ProviderShape;
}

export type ResolveResult =
  | { ok: true; plan: UpstreamPlan }
  | { ok: false; reason: string };

/**
 * Build the upstream streaming request for a model using only process.env keys.
 *
 * Routing: a provider key for the model's own provider wins; otherwise, if an
 * OpenRouter key is configured and the model has an OR vendor slug, route via
 * OpenRouter. If neither key exists, returns { ok:false } so the caller can
 * answer HTTP 501 (honest "server chat not configured" — never fabricated).
 */
export function buildUpstream(model: string, messages: ChatMessage[]): ResolveResult {
  if (!model || model === 'auto') {
    // No vendor-privileged default. Server picks the first provider it has a key
    // for, OpenRouter-first (spans every vendor); else honest "not configured".
    model = pickServerModel();
    if (!model) return { ok: false, reason: 'server chat not configured' };
  }

  const p = providerForModel(model);
  const directKey = envKey(p.keyEnv);

  // Direct upstream when we hold this provider's own key.
  if (directKey) {
    if (p.shape === 'anthropic') {
      return { ok: true, plan: buildAnthropic(p, directKey, model, messages) };
    }
    return { ok: true, plan: buildOpenAIShape(p, directKey, stripProviderPrefix(p.id, model), messages) };
  }

  // Fallback: OpenRouter, if a key exists and the model has an OR vendor slug.
  const orKey = envKey(OPENROUTER.keyEnv);
  if (orKey && (p.id === 'openrouter' || p.openrouterPrefix)) {
    const orModel = p.id === 'openrouter'
      ? model.replace(/^openrouter\//, '')
      : `${p.openrouterPrefix}/${model.split('/').pop()}`;
    return { ok: true, plan: buildOpenAIShape(OPENROUTER, orKey, orModel, messages) };
  }

  return { ok: false, reason: 'server chat not configured' };
}

/** True when at least one supported provider key is present in process.env. */
export function hasServerKey(): boolean {
  return SERVER_PROVIDERS.some((p) => !!envKey(p.keyEnv));
}

/** Vendor-neutral server pick: OpenRouter-first, else first keyed provider. */
function pickServerModel(): string {
  if (envKey(OPENROUTER.keyEnv)) return 'openrouter/auto';
  for (const p of SERVER_PROVIDERS) {
    if (p.id === 'openrouter') continue;
    if (envKey(p.keyEnv)) {
      // Use a bare provider-id prefix so providerForModel routes it back here.
      return `${p.id}/auto`;
    }
  }
  return '';
}

function stripProviderPrefix(id: string, model: string): string {
  return model.replace(new RegExp(`^${id}/`), '');
}

// ---- request builders ---------------------------------------------------------

function buildOpenAIShape(p: ServerProvider, key: string, model: string, messages: ChatMessage[]): UpstreamPlan {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${key}`,
  };
  if (p.id === 'openrouter') {
    headers['HTTP-Referer'] = 'https://nexus.local';
    headers['X-Title'] = 'NEXUS';
  }
  return {
    url: `${p.baseUrl.replace(/\/$/, '')}/chat/completions`,
    init: {
      method: 'POST',
      headers,
      body: JSON.stringify({ model, messages, stream: true }),
    },
    shape: 'openai',
  };
}

function buildAnthropic(p: ServerProvider, key: string, model: string, messages: ChatMessage[]): UpstreamPlan {
  const system = messages.filter((m) => m.role === 'system').map((m) => m.content).join('\n');
  const conv = messages.filter((m) => m.role !== 'system').map((m) => ({ role: m.role, content: m.content }));
  return {
    url: `${p.baseUrl.replace(/\/$/, '')}/v1/messages`,
    init: {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': key,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: model.split('/').pop(),
        max_tokens: 2048,
        system: system || undefined,
        messages: conv,
        stream: true,
      }),
    },
    shape: 'anthropic',
  };
}

// ---- SSE normalization --------------------------------------------------------

const enc = new TextEncoder();

/** Emit one OpenAI delta frame from a text chunk. */
function deltaFrame(text: string): Uint8Array {
  return enc.encode(`data: ${JSON.stringify({ choices: [{ delta: { content: text } }] })}\n\n`);
}

const DONE = enc.encode('data: [DONE]\n\n');

/**
 * Wrap an upstream SSE body in a ReadableStream that emits the OpenAI delta frame
 * shape the client parses. OpenAI/OpenRouter/Gemini-OpenAI frames pass through
 * (re-emitted from their parsed delta so framing is canonical); Anthropic's
 * content_block_delta events are normalized to the OpenAI delta shape. A trailing
 * `data: [DONE]` is always emitted so the client loop terminates cleanly.
 */
export function normalizeStream(upstream: ReadableStream<Uint8Array>, shape: ProviderShape): ReadableStream<Uint8Array> {
  const reader = upstream.getReader();
  const dec = new TextDecoder();
  let buf = '';
  let doneSent = false;

  return new ReadableStream<Uint8Array>({
    async pull(controller) {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) {
          // flush any trailing buffered line
          const line = buf.trim();
          if (line) emit(controller, line, shape);
          if (!doneSent) {
            controller.enqueue(DONE);
            doneSent = true;
          }
          controller.close();
          return;
        }
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() || '';
        let emitted = false;
        for (const raw of lines) {
          const line = raw.trim();
          if (!line) continue;
          const terminate = emit(controller, line, shape);
          emitted = true;
          if (terminate) {
            doneSent = true;
            controller.close();
            return;
          }
        }
        if (emitted) return; // yield back to the consumer between chunks
      }
    },
    cancel() {
      reader.cancel().catch(() => {});
    },
  });
}

/**
 * Parse one upstream SSE line and enqueue a normalized OpenAI delta frame.
 * Returns true when the stream is terminated (a `[DONE]` sentinel was seen),
 * in which case the caller emits/closes.
 */
function emit(
  controller: ReadableStreamDefaultController<Uint8Array>,
  line: string,
  shape: ProviderShape,
): boolean {
  if (!line.startsWith('data:')) return false;
  const payload = line.slice(5).trim();
  if (!payload) return false;
  if (payload === '[DONE]') {
    controller.enqueue(DONE);
    return true;
  }
  let ev: unknown;
  try {
    ev = JSON.parse(payload);
  } catch {
    return false; // skip partial / non-JSON frame
  }
  if (shape === 'anthropic') {
    const a = ev as { type?: string; delta?: { text?: string } };
    if (a.type === 'content_block_delta' && a.delta?.text) {
      controller.enqueue(deltaFrame(a.delta.text));
    }
    // message_stop / other events carry no text -> nothing to emit
    return false;
  }
  // openai / gemini-openai: re-emit the parsed text delta in canonical shape
  const o = ev as { choices?: Array<{ delta?: { content?: string } }> };
  const text = o.choices?.[0]?.delta?.content;
  if (text) controller.enqueue(deltaFrame(text));
  return false;
}
