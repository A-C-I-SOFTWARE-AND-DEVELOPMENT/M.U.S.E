#!/usr/bin/env node
// ============================================================================
// NEXUS unified provider gateway — a local, OpenAI-compatible proxy that routes
// to the providers' OFFICIAL APIs using YOUR OWN API KEYS. One endpoint, many
// providers; the supported, ToS-compliant way to use Claude / GPT / Gemini /
// OpenRouter (and local OSS) as a unified backend.
//
//   POST /v1/chat/completions   (OpenAI schema, streaming + non-streaming)
//   GET  /v1/models
//   GET  /health
//
// Routing by model name:
//   claude-*            -> Anthropic Messages API   (ANTHROPIC_API_KEY)
//   gpt-*, o1*, o3*     -> OpenAI Chat Completions   (OPENAI_API_KEY)
//   gemini-*            -> Google Gemini API         (GEMINI_API_KEY / GOOGLE_API_KEY)
//   openrouter/<model>  -> OpenRouter                (OPENROUTER_API_KEY)
//   <anything>          -> a local OpenAI-compatible server (LOCAL_BASE_URL,
//                          e.g. llama.cpp / Ollama / vLLM) if configured
//
// No dependencies — Node 18+ (built-in fetch + http). Reads keys from env
// (the .env the NEXUS credentials manager exports).
// ============================================================================

import http from 'node:http';

const PORT = Number(process.env.GATEWAY_PORT || 8782);
const KEYS = {
  anthropic: process.env.ANTHROPIC_API_KEY || '',
  openai: process.env.OPENAI_API_KEY || '',
  gemini: process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY || '',
  openrouter: process.env.OPENROUTER_API_KEY || '',
};
const LOCAL_BASE_URL = process.env.LOCAL_BASE_URL || ''; // e.g. http://127.0.0.1:11434/v1

function route(model = '') {
  const m = model.toLowerCase();
  if (m.startsWith('openrouter/')) return 'openrouter';
  if (m.startsWith('claude')) return 'anthropic';
  if (m.startsWith('gpt') || m.startsWith('o1') || m.startsWith('o3') || m.startsWith('o4')) return 'openai';
  if (m.startsWith('gemini')) return 'gemini';
  if (LOCAL_BASE_URL) return 'local';
  return 'openrouter'; // sensible default aggregator
}

const json = (res, code, obj) => {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': '*',
    'Access-Control-Allow-Methods': '*',
  });
  res.end(body);
};

function sseHeaders(res) {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
    'Access-Control-Allow-Origin': '*',
  });
}

// ---- Provider adapters: convert OpenAI request -> provider, stream back as
// OpenAI-shaped SSE chunks. Each uses the OFFICIAL documented endpoint. --------

async function callOpenAICompatible(base, key, body, res, extraHeaders = {}) {
  const upstream = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}`, ...extraHeaders },
    body: JSON.stringify(body),
  });
  if (!body.stream) {
    const data = await upstream.json();
    return json(res, upstream.status, data);
  }
  sseHeaders(res);
  for await (const chunk of upstream.body) res.write(chunk);
  res.end();
}

async function callAnthropic(body, res) {
  // OpenAI messages -> Anthropic Messages API.
  const system = body.messages.filter((m) => m.role === 'system').map((m) => m.content).join('\n');
  const messages = body.messages.filter((m) => m.role !== 'system').map((m) => ({ role: m.role, content: m.content }));
  const payload = {
    model: body.model,
    max_tokens: body.max_tokens || 1024,
    temperature: body.temperature,
    top_p: body.top_p,
    system: system || undefined,
    messages,
    stream: !!body.stream,
  };
  const upstream = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': KEYS.anthropic,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify(payload),
  });
  const id = `chatcmpl-${Date.now()}`;
  if (!body.stream) {
    const d = await upstream.json();
    if (upstream.status >= 400) return json(res, upstream.status, d);
    const text = (d.content || []).map((c) => c.text || '').join('');
    return json(res, 200, {
      id, object: 'chat.completion', model: body.model,
      choices: [{ index: 0, message: { role: 'assistant', content: text }, finish_reason: d.stop_reason || 'stop' }],
      usage: d.usage,
    });
  }
  sseHeaders(res);
  const dec = new TextDecoder();
  let buf = '';
  for await (const chunk of upstream.body) {
    buf += dec.decode(chunk, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop() || '';
    for (const line of lines) {
      if (!line.startsWith('data:')) continue;
      try {
        const ev = JSON.parse(line.slice(5).trim());
        if (ev.type === 'content_block_delta' && ev.delta?.text) {
          res.write(`data: ${JSON.stringify({ id, object: 'chat.completion.chunk', model: body.model, choices: [{ index: 0, delta: { content: ev.delta.text } }] })}\n\n`);
        }
      } catch { /* skip partial */ }
    }
  }
  res.write('data: [DONE]\n\n');
  res.end();
}

async function callGemini(body, res) {
  // OpenAI messages -> Gemini generateContent (Google exposes an OpenAI-compat
  // endpoint too; we use it to keep this thin and official).
  return callOpenAICompatible(
    'https://generativelanguage.googleapis.com/v1beta/openai',
    KEYS.gemini, body, res,
  );
}

async function handleChat(req, res, body) {
  const provider = route(body.model);
  try {
    switch (provider) {
      case 'anthropic':
        if (!KEYS.anthropic) return json(res, 400, { error: 'ANTHROPIC_API_KEY not set' });
        return await callAnthropic(body, res);
      case 'openai':
        if (!KEYS.openai) return json(res, 400, { error: 'OPENAI_API_KEY not set' });
        return await callOpenAICompatible('https://api.openai.com/v1', KEYS.openai, body, res);
      case 'gemini':
        if (!KEYS.gemini) return json(res, 400, { error: 'GEMINI_API_KEY not set' });
        return await callGemini(body, res);
      case 'openrouter':
        if (!KEYS.openrouter) return json(res, 400, { error: 'OPENROUTER_API_KEY not set' });
        return await callOpenAICompatible('https://openrouter.ai/api/v1', KEYS.openrouter,
          { ...body, model: body.model.replace(/^openrouter\//, '') }, res,
          { 'HTTP-Referer': 'https://nexus.local', 'X-Title': 'NEXUS' });
      case 'local':
        return await callOpenAICompatible(LOCAL_BASE_URL, process.env.LOCAL_API_KEY || 'local', body, res);
      default:
        return json(res, 400, { error: `no provider for model ${body.model}` });
    }
  } catch (e) {
    // Log the detail server-side only; return a generic message so internal
    // details / stack traces are never exposed to the client.
    console.error('[gateway] upstream error:', e);
    return json(res, 502, { error: 'upstream request failed' });
  }
}

const MODELS = [
  { id: 'claude-opus-4-1', owned_by: 'anthropic' },
  { id: 'claude-sonnet-4-5', owned_by: 'anthropic' },
  { id: 'gpt-4o', owned_by: 'openai' },
  { id: 'gpt-4o-mini', owned_by: 'openai' },
  { id: 'gemini-2.0-flash', owned_by: 'google' },
  { id: 'openrouter/auto', owned_by: 'openrouter' },
];

const server = http.createServer((req, res) => {
  if (req.method === 'OPTIONS') return json(res, 204, {});
  if (req.url === '/health') return json(res, 200, { ok: true, providers: Object.fromEntries(Object.entries(KEYS).map(([k, v]) => [k, !!v])) });
  if (req.url === '/v1/models') return json(res, 200, { object: 'list', data: MODELS.map((m) => ({ ...m, object: 'model' })) });
  if (req.url === '/v1/chat/completions' && req.method === 'POST') {
    let raw = '';
    req.on('data', (c) => (raw += c));
    req.on('end', () => {
      let body;
      try { body = JSON.parse(raw); } catch { return json(res, 400, { error: 'invalid JSON' }); }
      if (!body.model || !Array.isArray(body.messages)) return json(res, 400, { error: 'model and messages required' });
      handleChat(req, res, body);
    });
    return;
  }
  return json(res, 404, { error: 'not found' });
});

server.listen(PORT, '127.0.0.1', () => {
  const on = Object.entries(KEYS).filter(([, v]) => v).map(([k]) => k);
  console.log(`▸ NEXUS provider gateway → http://127.0.0.1:${PORT}/v1`);
  console.log(`  providers with keys: ${on.length ? on.join(', ') : '(none yet — set them in NEXUS Credentials and export the .env)'}`);
  if (LOCAL_BASE_URL) console.log(`  local fallback: ${LOCAL_BASE_URL}`);
});
