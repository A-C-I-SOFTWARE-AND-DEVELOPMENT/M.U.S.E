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
  /** Primary env var name (Hermes-canonical when possible). */
  keyEnv: string;
  /**
   * Extra env aliases accepted for the same credential (deploy-doc / Vercel
   * drift). Hermes core and this Edge table must accept the same names so a
   * key that works locally also lights public /api/chat.
   */
  keyEnvAliases?: string[];
  shape: ProviderShape;
  /** Real default model used when the request asks for 'auto' on this provider. */
  defaultModel: string;
  /**
   * Provider whose API has a $0 free tier (free key → free public chat). The
   * server prefers a keyed free provider over a paid one, so the deployment can
   * run at no cost. NOT exclusive to OpenRouter — any of these flips chat live.
   */
  free?: boolean;
  /** Vendor slug used when routing this model through OpenRouter. */
  openrouterPrefix?: string;
}

// Server-side provider table. Mirrors the baseUrl/key conventions of
// src/lib/providers.ts but stays import-free so it can run in the Edge runtime.
// Only OpenAI-shape, Anthropic-shape, and Gemini-OpenAI-shape HTTP providers with
// a public base URL + bearer key are listed (OAuth/IAM/local/gateway-only
// providers are intentionally omitted server-side). ANY one of these keys, set on
// the server, flips the public chat live — OpenRouter is not required. Providers
// with a genuine $0 free tier are flagged `free` and win the pick order, so the
// hosted chat can run at no cost (Groq, Google Gemini, Cerebras, NVIDIA NIM,
// Hugging Face, GitHub Models, GLM Flash).
const SERVER_PROVIDERS: ServerProvider[] = [
  // --- $0 free-tier providers (preferred so the public chat costs nothing) ---
  { id: 'groq', baseUrl: 'https://api.groq.com/openai/v1', keyEnv: 'GROQ_API_KEY', shape: 'openai', free: true, defaultModel: 'llama-3.3-70b-versatile' },
  { id: 'google', baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai', keyEnv: 'GEMINI_API_KEY', shape: 'gemini-openai', free: true, openrouterPrefix: 'google', defaultModel: 'gemini-2.0-flash' },
  { id: 'cerebras', baseUrl: 'https://api.cerebras.ai/v1', keyEnv: 'CEREBRAS_API_KEY', shape: 'openai', free: true, defaultModel: 'llama-3.3-70b' },
  {
    id: 'nim',
    baseUrl: 'https://integrate.api.nvidia.com/v1',
    keyEnv: 'NVIDIA_API_KEY',
    keyEnvAliases: ['NIM_API_KEY', 'NVIDIA_NIM_API_KEY'],
    shape: 'openai',
    free: true,
    defaultModel: 'meta/llama-3.3-70b-instruct',
  },
  { id: 'huggingface', baseUrl: 'https://router.huggingface.co/v1', keyEnv: 'HF_TOKEN', shape: 'openai', free: true, defaultModel: 'meta-llama/Llama-3.3-70B-Instruct' },
  { id: 'github-models', baseUrl: 'https://models.inference.ai.azure.com', keyEnv: 'GITHUB_TOKEN', shape: 'openai', free: true, openrouterPrefix: 'openai', defaultModel: 'gpt-4o-mini' },
  {
    id: 'zhipu',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    keyEnv: 'GLM_API_KEY',
    keyEnvAliases: ['ZHIPU_API_KEY', 'ZAI_API_KEY', 'Z_AI_API_KEY'],
    shape: 'openai',
    free: true,
    defaultModel: 'glm-4-flash',
  },
  // --- universal router (300+ models behind one key; auto = omni) ---
  { id: 'openrouter', baseUrl: 'https://openrouter.ai/api/v1', keyEnv: 'OPENROUTER_API_KEY', shape: 'openai', defaultModel: 'openrouter/auto' },
  // --- paid (or paid-after-trial) direct providers ---
  { id: 'anthropic', baseUrl: 'https://api.anthropic.com', keyEnv: 'ANTHROPIC_API_KEY', shape: 'anthropic', openrouterPrefix: 'anthropic', defaultModel: 'claude-3-5-haiku-latest' },
  { id: 'openai', baseUrl: 'https://api.openai.com/v1', keyEnv: 'OPENAI_API_KEY', shape: 'openai', openrouterPrefix: 'openai', defaultModel: 'gpt-4o-mini' },
  { id: 'mistral', baseUrl: 'https://api.mistral.ai/v1', keyEnv: 'MISTRAL_API_KEY', shape: 'openai', openrouterPrefix: 'mistralai', defaultModel: 'mistral-small-latest' },
  { id: 'deepseek', baseUrl: 'https://api.deepseek.com', keyEnv: 'DEEPSEEK_API_KEY', shape: 'openai', openrouterPrefix: 'deepseek', defaultModel: 'deepseek-chat' },
  { id: 'xai', baseUrl: 'https://api.x.ai/v1', keyEnv: 'XAI_API_KEY', shape: 'openai', openrouterPrefix: 'x-ai', defaultModel: 'grok-2-latest' },
  { id: 'together', baseUrl: 'https://api.together.xyz/v1', keyEnv: 'TOGETHER_API_KEY', shape: 'openai', defaultModel: 'meta-llama/Llama-3.3-70B-Instruct-Turbo' },
  { id: 'novita', baseUrl: 'https://api.novita.ai/v3/openai', keyEnv: 'NOVITA_API_KEY', shape: 'openai', defaultModel: 'meta-llama/llama-3.3-70b-instruct' },
  { id: 'dashscope', baseUrl: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', keyEnv: 'DASHSCOPE_API_KEY', shape: 'openai', openrouterPrefix: 'qwen', defaultModel: 'qwen-max' },
  {
    id: 'moonshot',
    baseUrl: 'https://api.moonshot.ai/v1',
    keyEnv: 'KIMI_API_KEY',
    keyEnvAliases: ['MOONSHOT_API_KEY', 'KIMI_CODING_API_KEY'],
    shape: 'openai',
    defaultModel: 'kimi-latest',
  },
  { id: 'fireworks', baseUrl: 'https://api.fireworks.ai/inference/v1', keyEnv: 'FIREWORKS_API_KEY', shape: 'openai', defaultModel: 'accounts/fireworks/models/llama-v3p3-70b-instruct' },
  { id: 'perplexity', baseUrl: 'https://api.perplexity.ai', keyEnv: 'PERPLEXITY_API_KEY', shape: 'openai', defaultModel: 'sonar' },
];

const BY_ID = Object.fromEntries(SERVER_PROVIDERS.map((p) => [p.id, p]));
const OPENROUTER = BY_ID.openrouter;

// Omni fallback chain. When the omni/auto route is used, the request threads
// through this ordered set of models so a single model or provider outage never
// stops the chat — OpenRouter tries the next candidate automatically.
// 'openrouter/auto' is the primary (a meta-router over 300+ models); these are
// the explicit cross-vendor safety net beneath it, deliberately all `:free`
// slugs so the fallback path costs nothing ("free tier, all free models").
const OMNI_FALLBACKS = [
  'deepseek/deepseek-chat-v3-0324:free',
  'meta-llama/llama-3.3-70b-instruct:free',
  'google/gemini-2.0-flash-exp:free',
  'qwen/qwen-2.5-72b-instruct:free',
  'mistralai/mistral-small-3.1-24b-instruct:free',
  'nvidia/llama-3.1-nemotron-70b-instruct:free',
];

/**
 * OpenRouter request extras that make the omni/auto route resilient: an ordered
 * fallback chain plus provider-level fallbacks sorted by throughput, so a single
 * model/provider outage transparently threads to the next candidate — the chat
 * "never stops" and can fuse across every model. Applied ONLY to the omni (auto)
 * route; an explicit model pick is left untouched so the user gets exactly the
 * model they chose.
 */
function omniRouting(): Record<string, unknown> {
  return {
    models: OMNI_FALLBACKS,
    route: 'fallback',
    provider: { allow_fallbacks: true, sort: 'throughput' },
  };
}

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

/** First non-empty env value among a provider's primary key + aliases. */
function providerEnvKey(p: ServerProvider): string {
  const primary = envKey(p.keyEnv);
  if (primary) return primary;
  for (const alias of p.keyEnvAliases || []) {
    const v = envKey(alias);
    if (v) return v;
  }
  return '';
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

export interface UpstreamOpts {
  /** Client-supplied (BYOK) provider key — used per-request, never stored. */
  clientKey?: string;
  /** Explicit provider id for the client key; inferred from the model if absent. */
  clientProvider?: string;
}

/**
 * Build the upstream streaming request for a model using only process.env keys.
 *
 * Routing: a provider key for the model's own provider wins; otherwise, if an
 * OpenRouter key is configured and the model has an OR vendor slug, route via
 * OpenRouter. If neither key exists, returns { ok:false } so the caller can
 * answer HTTP 501 (honest "server chat not configured" — never fabricated).
 */
export function buildUpstream(
  model: string,
  messages: ChatMessage[],
  opts: UpstreamOpts = {},
): ResolveResult {
  // BYOK (bring-your-own-key): a client-supplied key routes through the user's
  // OWN key, never consulting env. The provider is the explicit clientProvider
  // (when known) else inferred from the model. Used per-request, never stored or
  // logged. This is how a visitor turns chat on from the public page.
  const clientKey = (opts.clientKey || '').trim();
  if (clientKey) {
    const p =
      opts.clientProvider && BY_ID[opts.clientProvider]
        ? BY_ID[opts.clientProvider]
        : providerForModel(model);
    return { ok: true, plan: buildForProvider(p, clientKey, model, messages) };
  }

  if (!model || model === 'auto') {
    // No vendor-privileged default. Server picks the first provider it has a key
    // for, free-tier first (so the public chat can run at $0); else honest
    // "not configured".
    model = pickServerModel();
    if (!model) return { ok: false, reason: 'server chat not configured' };
  }

  const p = providerForModel(model);
  const directKey = providerEnvKey(p);

  // Direct upstream when we hold this provider's own key.
  if (directKey) {
    if (p.shape === 'anthropic') {
      return { ok: true, plan: buildAnthropic(p, directKey, model, messages) };
    }
    // OpenRouter wants the full vendor/model slug (e.g. 'openrouter/auto',
    // 'anthropic/claude-3.7-sonnet') as-is; every other provider wants its own
    // bare model id, so strip the provider-id prefix.
    const m = p.id === 'openrouter' ? openrouterModelId(model) : stripProviderPrefix(p.id, model);
    // Omni resilience when the user holds the OpenRouter key directly.
    const extra = p.id === 'openrouter' && m === 'openrouter/auto' ? omniRouting() : undefined;
    return { ok: true, plan: buildOpenAIShape(p, directKey, m, messages, extra) };
  }

  // Fallback: OpenRouter, if a key exists and the model has an OR vendor slug.
  const orKey = providerEnvKey(OPENROUTER);
  if (orKey && (p.id === 'openrouter' || p.openrouterPrefix)) {
    const orModel = p.id === 'openrouter'
      ? openrouterModelId(model)
      : `${p.openrouterPrefix}/${model.split('/').pop()}`;
    // Thread through every model on the omni/auto route; never stop on one outage.
    const extra = orModel === 'openrouter/auto' ? omniRouting() : undefined;
    return { ok: true, plan: buildOpenAIShape(OPENROUTER, orKey, orModel, messages, extra) };
  }

  // The requested model's provider has no key and OpenRouter can't cover it.
  // Rather than 501, fall back to whatever the server CAN serve (free-first), so
  // any single provider key keeps the public chat alive regardless of which
  // model the client asked for. Terminates after one hop: the fallback model's
  // provider always holds a key, so it resolves on the direct path above.
  const serverModel = pickServerModel();
  if (serverModel && serverModel !== model) {
    return buildUpstream(serverModel, messages);
  }

  return { ok: false, reason: 'server chat not configured' };
}

/** True when at least one supported provider key is present in process.env. */
export function hasServerKey(): boolean {
  return SERVER_PROVIDERS.some((p) => !!providerEnvKey(p));
}

/**
 * Vendor-neutral server pick. Free-first: a keyed $0 provider wins so the public
 * chat can run at no cost, then OpenRouter's omni router, then any other keyed
 * provider. OpenRouter is NOT privileged — a free direct key flips chat live on
 * its own. Returns a real default model (prefixed with the provider id so
 * providerForModel routes it back here), never the literal 'auto' for a provider
 * that has no such model.
 */
function pickServerModel(): string {
  // Stable sort (V8) by free-tier first; preserves table order within each group.
  const ordered = [...SERVER_PROVIDERS].sort((a, b) => Number(!!b.free) - Number(!!a.free));
  for (const p of ordered) {
    if (!providerEnvKey(p)) continue;
    // OpenRouter's own 'auto' is a real meta-model; others get a real default.
    return p.id === 'openrouter' ? 'openrouter/auto' : `${p.id}/${p.defaultModel}`;
  }
  return '';
}

function stripProviderPrefix(id: string, model: string): string {
  return model.replace(new RegExp(`^${id}/`), '');
}

/**
 * Build an upstream plan for a provider using a specific key (BYOK or env). 'auto'
 * resolves to the provider's real default model (OpenRouter's omni router, or each
 * provider's defaultModel), and the OpenRouter omni route gets its fallback chain.
 */
function buildForProvider(
  p: ServerProvider,
  key: string,
  model: string,
  messages: ChatMessage[],
): UpstreamPlan {
  let m = model;
  if (!m || m === 'auto') m = p.id === 'openrouter' ? 'openrouter/auto' : p.defaultModel;
  if (p.shape === 'anthropic') return buildAnthropic(p, key, m, messages);
  const mm = p.id === 'openrouter' ? openrouterModelId(m) : stripProviderPrefix(p.id, m);
  const extra = p.id === 'openrouter' && mm === 'openrouter/auto' ? omniRouting() : undefined;
  return buildOpenAIShape(p, key, mm, messages, extra);
}

/**
 * Normalize a model id to the slug OpenRouter expects: its auto router is
 * 'openrouter/auto' (NOT bare 'auto'), so map both to the full slug. Every other
 * OpenRouter slug (e.g. 'anthropic/claude-3.7-sonnet') passes through unchanged.
 */
function openrouterModelId(model: string): string {
  return model === 'auto' || model === 'openrouter/auto' ? 'openrouter/auto' : model;
}

// ---- request builders ---------------------------------------------------------

function buildOpenAIShape(
  p: ServerProvider,
  key: string,
  model: string,
  messages: ChatMessage[],
  extra?: Record<string, unknown>,
): UpstreamPlan {
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
      body: JSON.stringify({ model, messages, stream: true, ...(extra || {}) }),
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
