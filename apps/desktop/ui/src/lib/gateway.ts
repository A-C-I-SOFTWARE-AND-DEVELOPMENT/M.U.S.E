/**
 * M.U.S.E. gateway client.
 *
 * A small, dependency-free typed wrapper over the cockpit gateway API. It
 * mirrors the live browser cockpit (gateway/cockpit/static/index.html) so the
 * desktop app speaks exactly the same protocol:
 *
 *   - bearer token in the `Authorization` header (stored in localStorage under
 *     `muse.cockpit.token`);
 *   - pairing via POST /v1/cockpit/pair/start → POST /v1/cockpit/pair/confirm;
 *   - the jobs stream over GET /v1/cockpit/jobs/stream as Server-Sent Events,
 *     consumed with fetch() + a ReadableStream reader (NOT EventSource, because
 *     EventSource cannot attach the bearer header);
 *   - chat over POST /v1/jarvis/chat as newline-delimited JSON (NDJSON);
 *   - health over GET /v1/health.
 *
 * The gateway base URL is configurable (default http://127.0.0.1:8765). In the
 * Tauri shell it can be overridden; in a plain browser it defaults to the
 * page origin so the cockpit's same-origin paths keep working.
 */

export const TOKEN_KEY = "muse.cockpit.token";
const BASE_KEY = "muse.gateway.base";
export const DEFAULT_GATEWAY_BASE = "http://127.0.0.1:8765";

/** Resolve the configured gateway base URL (no trailing slash). */
export function getGatewayBase(): string {
  const stored = safeLocalStorageGet(BASE_KEY);
  if (stored) return stripTrailingSlash(stored);
  // A Vite build-time default lets packagers point at a different gateway.
  const env = (import.meta.env.VITE_GATEWAY_BASE as string | undefined) || "";
  if (env) return stripTrailingSlash(env);
  return DEFAULT_GATEWAY_BASE;
}

export function setGatewayBase(base: string): void {
  safeLocalStorageSet(BASE_KEY, stripTrailingSlash(base.trim()));
}

export function getToken(): string {
  return safeLocalStorageGet(TOKEN_KEY) || "";
}

export function setToken(token: string): void {
  safeLocalStorageSet(TOKEN_KEY, token.trim());
}

function stripTrailingSlash(s: string): string {
  return s.replace(/\/+$/, "");
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { ...(extra || {}) };
  const token = getToken();
  if (token) h["Authorization"] = "Bearer " + token;
  return h;
}

/** A single authenticated fetch against the gateway. */
export async function api(path: string, opts?: RequestInit): Promise<Response> {
  const o: RequestInit = { ...(opts || {}) };
  o.headers = authHeaders(o.headers as Record<string, string> | undefined);
  return fetch(getGatewayBase() + path, o);
}

// ---- health ---------------------------------------------------------------

/** Ping GET /v1/health. Resolves true iff the gateway answers ok. */
export async function pingHealth(): Promise<boolean> {
  try {
    const r = await fetch(getGatewayBase() + "/v1/health");
    return r.ok;
  } catch {
    return false;
  }
}

// ---- pairing --------------------------------------------------------------

export type PairStartResult = {
  ok: boolean;
  pairingCode?: string;
  error?: string;
  hint?: string;
};

/**
 * POST /v1/cockpit/pair/start. Unauthenticated by design (a new device has no
 * token yet). Returns a short-lived pairing code on success.
 */
export async function pairStart(deviceName?: string): Promise<PairStartResult> {
  try {
    const r = await fetch(getGatewayBase() + "/v1/cockpit/pair/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_name: (deviceName || "").trim() }),
    });
    const d = await r.json().catch(() => ({}) as Record<string, unknown>);
    if (!r.ok) {
      return {
        ok: false,
        error: String(d.error ?? r.status),
        hint: d.hint ? String(d.hint) : undefined,
      };
    }
    return { ok: true, pairingCode: String(d.pairing_code ?? "") };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

export type PairConfirmResult = {
  ok: boolean;
  token?: string;
  forbidden?: boolean;
  error?: string;
};

/**
 * POST /v1/cockpit/pair/confirm with the pairing code + owner authorization
 * phrase. On success, mints and returns a per-device token (also persisted).
 * A 403 means the owner authorization was wrong/required.
 */
export async function pairConfirm(
  pairingCode: string,
  authorization: string,
): Promise<PairConfirmResult> {
  try {
    const r = await fetch(getGatewayBase() + "/v1/cockpit/pair/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pairing_code: pairingCode, authorization }),
    });
    const d = await r.json().catch(() => ({}) as Record<string, unknown>);
    if (r.status === 403) return { ok: false, forbidden: true };
    if (!r.ok || !d.token) {
      return { ok: false, error: String(d.error ?? r.status) };
    }
    const token = String(d.token);
    setToken(token);
    return { ok: true, token };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

// ---- chat (NDJSON) --------------------------------------------------------

export type ChatTurn = { role: string; content: string };

export type ChatCallbacks = {
  /** Called with the accumulated assistant text as it streams. */
  onDelta?: (accumulated: string) => void;
  onError?: (message: string) => void;
};

/**
 * POST /v1/jarvis/chat (NDJSON). Streams the assistant reply line-by-line and
 * returns the final accumulated text. Mirrors the cockpit's NDJSON parser:
 * each line is a JSON object; assistant content is concatenated.
 */
export async function chat(
  prompt: string,
  history: ChatTurn[],
  cb?: ChatCallbacks,
): Promise<string> {
  const r = await api("/v1/jarvis/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, history }),
  });
  if (!r.ok || !r.body) {
    const msg = "error: " + r.status + (r.status === 401 ? " — pair this device" : "");
    cb?.onError?.(msg);
    return "";
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let acc = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let nl: number;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      try {
        const obj = JSON.parse(line) as Record<string, unknown>;
        if (obj.error) {
          acc += "\n[error] " + String(obj.error);
        } else if (obj.role === "assistant" && obj.content != null) {
          acc += String(obj.content);
        } else if (
          obj.content != null &&
          obj.role !== "user" &&
          obj.role !== "system"
        ) {
          acc += String(obj.content);
        }
      } catch {
        /* ignore partial / non-JSON lines */
      }
      cb?.onDelta?.(acc);
    }
  }
  return acc;
}

// ---- jobs (SSE over fetch + ReadableStream) -------------------------------

export type CockpitJob = {
  id: string;
  title?: string;
  status?: string;
  worker_id?: string;
  branch?: string;
  [k: string]: unknown;
};

export type JobStreamHandlers = {
  onUpsert?: (job: CockpitJob) => void;
  onRemoved?: (id: string) => void;
  /** Connection liveness toggled by stream open/close and heartbeats. */
  onLive?: (live: boolean) => void;
};

/**
 * Subscribe to GET /v1/cockpit/jobs/stream. The endpoint is bearer-authed and
 * authorizes ONLY via the Authorization header, and a native EventSource cannot
 * attach headers — so we stream the SSE body with fetch() and parse the
 * text/event-stream frames ourselves. Reconnects with capped backoff. Returns a
 * disposer that aborts the stream.
 *
 * Falls back to a single poll of GET /v1/cockpit/jobs if fetch/ReadableStream/
 * AbortController are unavailable.
 */
export function subscribeJobs(handlers: JobStreamHandlers): () => void {
  if (!getToken()) {
    // Nothing to stream without a token; caller re-subscribes after pairing.
    return () => {};
  }
  if (
    typeof fetch === "undefined" ||
    typeof ReadableStream === "undefined" ||
    typeof AbortController === "undefined"
  ) {
    void pollJobsOnce(handlers);
    const timer = setInterval(() => void pollJobsOnce(handlers), 8000);
    return () => clearInterval(timer);
  }
  const ctrl = new AbortController();
  void runJobStream(ctrl, handlers);
  return () => {
    try {
      ctrl.abort();
    } catch {
      /* already aborted */
    }
  };
}

async function pollJobsOnce(handlers: JobStreamHandlers): Promise<void> {
  if (!getToken()) return;
  try {
    const r = await api("/v1/cockpit/jobs");
    if (!r.ok) return;
    const d = (await r.json()) as { jobs?: CockpitJob[] };
    if (d && Array.isArray(d.jobs)) {
      d.jobs.forEach((j) => handlers.onUpsert?.(j));
    }
  } catch {
    /* offline */
  }
}

async function runJobStream(
  ctrl: AbortController,
  handlers: JobStreamHandlers,
): Promise<void> {
  let backoff = 1000;
  while (!ctrl.signal.aborted && getToken()) {
    try {
      const r = await fetch(getGatewayBase() + "/v1/cockpit/jobs/stream", {
        headers: authHeaders({ Accept: "text/event-stream" }),
        signal: ctrl.signal,
      });
      if (!r.ok || !r.body) {
        if (r.status === 401) {
          handlers.onLive?.(false);
          return; // unpaired/expired — stop until token changes
        }
        throw new Error("stream status " + r.status);
      }
      handlers.onLive?.(true);
      backoff = 1000;
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        // Normalize CRLF → LF (server emits \r\n\r\n between frames).
        buf += dec.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        let sep: number;
        while ((sep = buf.indexOf("\n\n")) >= 0) {
          const frame = buf.slice(0, sep);
          buf = buf.slice(sep + 2);
          let event = "message";
          const dataLines: string[] = [];
          for (const raw of frame.split("\n")) {
            if (raw.startsWith("event:")) event = raw.slice(6).trim();
            else if (raw.startsWith("data:"))
              dataLines.push(raw.slice(5).replace(/^ /, ""));
          }
          if (dataLines.length) {
            dispatchJobEvent(event, dataLines.join("\n"), handlers);
          } else if (event === "heartbeat") {
            handlers.onLive?.(true);
          }
        }
      }
    } catch {
      if (ctrl.signal.aborted) return; // intentional stop
    }
    handlers.onLive?.(false);
    if (ctrl.signal.aborted || !getToken()) return;
    await new Promise((res) => setTimeout(res, backoff));
    backoff = Math.min(backoff * 2, 8000);
  }
}

function dispatchJobEvent(
  event: string,
  data: string,
  handlers: JobStreamHandlers,
): void {
  if (event === "heartbeat") {
    handlers.onLive?.(true);
    return;
  }
  let obj: CockpitJob;
  try {
    obj = JSON.parse(data) as CockpitJob;
  } catch {
    return;
  }
  if (!obj || !obj.id) return;
  if (event === "job.upsert") handlers.onUpsert?.(obj);
  else if (event === "job.removed") handlers.onRemoved?.(obj.id);
}

// ---- localStorage helpers (SSR/Tauri-safe) --------------------------------

function safeLocalStorageGet(key: string): string {
  try {
    return localStorage.getItem(key) || "";
  } catch {
    return "";
  }
}

function safeLocalStorageSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
}
