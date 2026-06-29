// ============================================================================
// Edge streaming chat proxy.
//
// POST /api/chat  { model, messages }  ->  Server-Sent Events stream in the
// OpenAI delta frame shape the NEXUS client already parses
// (src/lib/directProvider.ts -> readOpenAIStream / src/lib/chat.ts):
//
//   data: {"choices":[{"delta":{"content":"..."}}]}\n\n
//   ...
//   data: [DONE]\n\n
//
// Provider keys are read from process.env (server-only; NEVER VITE_-prefixed,
// never sent to the browser). When no server key is configured the function
// returns HTTP 501 JSON { error: 'server chat not configured' } so the UI shows
// an honest disconnected state instead of fabricating output.
//
// Runs on the Vercel Edge runtime. _providers.ts holds the runtime-neutral
// request building + SSE normalization (no browser-only imports).
// ============================================================================

import { buildUpstream, normalizeStream, hasServerKey, type ChatMessage } from './_providers';
import { rateLimit } from './_ratelimit';

export const config = { runtime: 'edge' };

interface ChatRequest {
  model?: string;
  messages?: ChatMessage[];
}

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export default async function handler(req: Request): Promise<Response> {
  if (req.method !== 'POST') {
    return json({ error: 'method not allowed' }, 405);
  }

  // Per-IP rate limit BEFORE any provider work — the public endpoint spends the
  // server-held key with no auth, so a single abuser must not be able to drain
  // it. 429 + Retry-After when a window is exceeded.
  const rl = await rateLimit(req);
  if (!rl.ok) {
    return new Response(
      JSON.stringify({ error: 'rate limit exceeded', scope: rl.scope }),
      {
        status: 429,
        headers: {
          'Content-Type': 'application/json',
          'Retry-After': String(rl.retryAfter),
        },
      },
    );
  }

  // BYOK: a visitor can supply their own provider key from the page (stored only
  // in their browser, sent per-request over HTTPS, never persisted or logged
  // here). When present it satisfies "configured" without a server key.
  const clientKey = req.headers.get('x-provider-key') || '';
  const clientProvider = req.headers.get('x-provider-id') || '';

  // No server key AND no client key -> honest "not configured" so the UI shows
  // a disconnected state rather than inventing a response.
  if (!hasServerKey() && !clientKey) {
    return json({ error: 'server chat not configured' }, 501);
  }

  let payload: ChatRequest;
  try {
    payload = (await req.json()) as ChatRequest;
  } catch {
    return json({ error: 'invalid JSON body' }, 400);
  }

  const messages = payload.messages;
  if (!Array.isArray(messages) || messages.length === 0) {
    return json({ error: 'messages required' }, 400);
  }
  const model = typeof payload.model === 'string' ? payload.model : 'auto';

  const resolved = buildUpstream(model, messages, { clientKey, clientProvider });
  if (!resolved.ok) {
    // No key for this model and no OpenRouter fallback configured.
    return json({ error: 'server chat not configured' }, 501);
  }

  let upstream: Response;
  try {
    upstream = await fetch(resolved.plan.url, resolved.plan.init);
  } catch (e) {
    return json({ error: `upstream fetch failed: ${(e as Error).message}` }, 502);
  }

  if (!upstream.ok || !upstream.body) {
    let detail = '';
    try {
      const d = await upstream.json();
      detail = d?.error?.message || d?.error || '';
    } catch {
      /* ignore non-JSON upstream error */
    }
    return json({ error: detail || `upstream ${upstream.status}` }, 502);
  }

  const stream = normalizeStream(upstream.body, resolved.plan.shape);
  return new Response(stream, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
    },
  });
}
