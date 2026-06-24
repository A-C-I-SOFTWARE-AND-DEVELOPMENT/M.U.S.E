// muse cockpit — API core.
//
// The single transport layer the cockpit talks to the live Python gateway
// through. Owns the bearer token, the fetch wrapper, the SSE/NDJSON stream
// parsers, and the owner-phrase prompt/retry flow. View modules MUST go through
// this module; they never call fetch() directly.

export const TOKEN_KEY = "muse.cockpit.token";

// ---- Token (localStorage, key "muse.cockpit.token") -----------------------
export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) || ""; } catch (e) { return ""; }
}
export function setToken(value) {
  const v = (value || "").trim();
  try {
    if (v) localStorage.setItem(TOKEN_KEY, v);
    else localStorage.removeItem(TOKEN_KEY);
  } catch (e) { /* private mode — token lives in memory for this session */ }
  return v;
}

// ---- Headers / fetch wrapper ---------------------------------------------
// Merge the bearer token into a header object (if a token exists).
export function authHeaders(extra) {
  const h = Object.assign({}, extra || {});
  const t = getToken();
  if (t) h["Authorization"] = "Bearer " + t;
  return h;
}

// The base fetch wrapper. Always attaches auth headers. `path` is absolute
// (e.g. "/v1/cockpit/jobs"); `opts` is a standard fetch init.
export function api(path, opts) {
  const o = Object.assign({}, opts || {});
  o.headers = authHeaders(o.headers);
  return fetch(path, o);
}

// GET + parse JSON. Throws on a non-2xx response (err.status carries the code).
export async function getJSON(path, opts) {
  const r = await api(path, opts);
  if (!r.ok) { const e = new Error("GET " + path + " → " + r.status); e.status = r.status; throw e; }
  return r.json();
}

// POST a JSON body + parse the JSON response. Throws on non-2xx
// (err.status carries the code; err.body carries any parsed error payload).
export async function postJSON(path, body, opts) {
  const o = Object.assign({ method: "POST" }, opts || {});
  o.headers = Object.assign({ "Content-Type": "application/json" }, o.headers || {});
  o.body = body == null ? "{}" : JSON.stringify(body);
  const r = await api(path, o);
  if (!r.ok) {
    const e = new Error("POST " + path + " → " + r.status);
    e.status = r.status;
    e.body = await r.json().catch(() => ({}));
    throw e;
  }
  return r.json().catch(() => ({}));
}

// ---- Health --------------------------------------------------------------
// GET /v1/health — unauthenticated liveness probe for the header status dot.
// Resolves to a boolean (true = online). Never throws.
export async function health() {
  try { const r = await fetch("/v1/health"); return r.ok; } catch (e) { return false; }
}

// ---- SSE over fetch (bearer token rides in the Authorization header) ------
// streamSSE(path, { onEvent, signal }): subscribe to a text/event-stream body
// via fetch + ReadableStream (NOT EventSource — the bearer token must ride in
// the Authorization header). onEvent(event, data) fires per parsed frame
// (event defaults to "message"; data is the joined data: lines). Resolves when
// the stream ends or the signal aborts; rejects on a network error. The caller
// owns reconnect/backoff (see the jobs view).
export async function streamSSE(path, { onEvent, signal } = {}) {
  const r = await fetch(path, { headers: authHeaders({ Accept: "text/event-stream" }), signal });
  if (!r.ok || !r.body) { const e = new Error("SSE " + path + " → " + r.status); e.status = r.status; throw e; }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    // Normalize CRLF → LF so frame splitting is line-ending agnostic.
    buf += dec.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let sep;
    while ((sep = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      let event = "message";
      const dataLines = [];
      for (const raw of frame.split("\n")) {
        if (raw.startsWith("event:")) event = raw.slice(6).trim();
        else if (raw.startsWith("data:")) dataLines.push(raw.slice(5).replace(/^ /, ""));
      }
      if (onEvent) onEvent(event, dataLines.join("\n"));
    }
  }
}

// ---- NDJSON over fetch ---------------------------------------------------
// streamNDJSON(path, body, { onLine, signal }): POST a JSON body, then read the
// response as newline-delimited JSON, firing onLine(obj) per parsed line.
// Used by the chat stream (POST /v1/jarvis/chat → {role, content, error}).
// Resolves when the stream ends; rejects on a network error or non-2xx open.
export async function streamNDJSON(path, body, { onLine, signal } = {}) {
  const r = await api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
    signal,
  });
  if (!r.ok || !r.body) { const e = new Error("NDJSON " + path + " → " + r.status); e.status = r.status; throw e; }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let nl;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      let obj; try { obj = JSON.parse(line); } catch (e) { continue; }
      if (onLine) onLine(obj);
    }
  }
  // Flush a trailing line with no terminating newline.
  const tail = buf.trim();
  if (tail) { try { if (onLine) onLine(JSON.parse(tail)); } catch (e) { /* ignore partial */ } }
}

// ---- Owner gating --------------------------------------------------------
// Prompt for the exact owner phrase at action time. NEVER stored. Returns the
// trimmed phrase, or null if cancelled.
export function promptOwnerPhrase(action) {
  const v = window.prompt(
    "Owner-gated: " + action + "\n\nEnter the exact owner authorization phrase to proceed."
  );
  if (v == null) return null;
  return v.trim();
}

// ownerPost(path, body): POST an owner-gated action. Prompts for the phrase,
// attaches it as body.authorization, and on HTTP 403 re-prompts ONCE and
// retries. Returns the parsed JSON response. Throws on cancel (err.cancelled)
// or a non-2xx final response (err.status / err.body). `action` is the
// human-readable label shown in the prompt (defaults to the path).
export async function ownerPost(path, body, action) {
  const label = action || path;
  const phrase = promptOwnerPhrase(label);
  if (phrase == null) { const e = new Error("cancelled"); e.cancelled = true; throw e; }
  const send = (auth) => postJSON(path, Object.assign({}, body || {}, { authorization: auth }));
  try {
    return await send(phrase);
  } catch (e) {
    if (e.status !== 403) throw e;
    const retry = promptOwnerPhrase("Authorization required — re-enter the exact phrase for: " + label);
    if (retry == null) { const c = new Error("cancelled"); c.cancelled = true; throw c; }
    return await send(retry);
  }
}
