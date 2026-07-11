/**
 * muse gateway client.
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

/**
 * Fired on window whenever the stored token changes (pairing, paste, clear).
 * The `storage` event only fires in OTHER documents, so same-document views
 * (Home, Chat, Jobs, …) listen for this to flip their paired state live.
 */
export const TOKEN_EVENT = "muse:token";

/**
 * Tauri v2 IPC: use window.__TAURI_INTERNALS__.invoke directly.
 * This is the lowest-level API, always available in the Tauri webview.
 * The @tauri-apps/api package wraps this, but we go raw to avoid any
 * import/resolution issues.
 */
function tauriInvoke(cmd: string, args?: Record<string, unknown>): Promise<unknown> {
  const internals = (
    window as unknown as {
      __TAURI_INTERNALS__?: {
        invoke?: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;
      };
    }
  ).__TAURI_INTERNALS__;
  if (!internals?.invoke) {
    return Promise.reject(new Error("Not in Tauri shell"));
  }
  return internals.invoke(cmd, args);
}

function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

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
  reportBaseToShell(getGatewayBase());
}

/**
 * Best-effort: tell the native shell (when running inside it) which gateway
 * base the UI is using. The Settings override lives in localStorage where the
 * Rust side cannot see it; this hint keeps native surfaces (Help → Copy
 * Gateway URL) truthful. A no-op in a plain browser.
 */
function reportBaseToShell(base: string): void {
  try {
    const inv = (
      window as unknown as {
        __TAURI__?: { core?: { invoke?: (cmd: string, args?: unknown) => Promise<unknown> } };
      }
    ).__TAURI__?.core?.invoke;
    if (inv) void inv("gateway_url_hint_set", { url: base }).catch(() => {});
  } catch {
    // Not in the shell (or invoke unavailable) — the hint is optional.
  }
}

// Report the initial base once on module load so the shell is truthful even
// before the user ever opens Settings.
reportBaseToShell(getGatewayBase());

export function getToken(): string {
  return safeLocalStorageGet(TOKEN_KEY) || "";
}

export function setToken(token: string): void {
  safeLocalStorageSet(TOKEN_KEY, token.trim());
  try {
    window.dispatchEvent(new Event(TOKEN_EVENT));
  } catch {
    /* no window (SSR) — nothing to notify */
  }
}

/** True iff `base` points at this machine (the local-trust boundary). */
export function isLoopbackBase(base?: string): boolean {
  const b = (base ?? getGatewayBase()).toLowerCase();
  try {
    const host = new URL(b).hostname;
    return host === "127.0.0.1" || host === "localhost" || host === "::1" || host === "[::1]";
  } catch {
    return false;
  }
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

/**
 * A single authenticated fetch against the gateway.
 *
 * Direct fetch first — the gateway allowlists the Tauri webview origins for
 * CORS, so inside the shell this is the streaming-capable fast path. If the
 * direct fetch throws (an older gateway without the Tauri origins, a webview
 * CORS quirk), fall back to the Rust `gateway_proxy` command, which speaks
 * plain HTTP from the native side (no CORS, but the body arrives buffered).
 */
export async function api(path: string, opts?: RequestInit): Promise<Response> {
  const o: RequestInit = { ...(opts || {}) };
  o.headers = authHeaders(o.headers as Record<string, string> | undefined);
  try {
    return await fetch(getGatewayBase() + path, o);
  } catch (err) {
    if (!isTauri()) throw err;
  }
  const method = (opts?.method as string) || "GET";
  const body = opts?.body ? String(opts.body) : undefined;
  const token = getToken();
  const result = (await tauriInvoke("gateway_proxy", {
    method,
    path,
    body,
    authToken: token || undefined,
  })) as { ok: boolean; status: number; body: string };
  // The proxy reports transport failures as status 0; the Response
  // constructor rejects statuses outside 200–599, so surface those as 503.
  const status = result.status >= 200 && result.status <= 599 ? result.status : 503;
  return new Response(result.body, {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// ---- health ---------------------------------------------------------------

/** Ping GET /v1/health. Resolves true iff the gateway answers ok. */
export async function pingHealth(): Promise<boolean> {
  // When inside Tauri, use the native gateway_status command (raw TCP).
  if (isTauri()) {
    try {
      const status = await tauriInvoke("gateway_status") as { reachable?: boolean };
      return status?.reachable === true;
    } catch {
      return false;
    }
  }
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
    const r = await api("/v1/cockpit/pair/start", {
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
 * A 403 means the owner authorization was wrong/required. On a loopback-only
 * gateway (the default) the server does not require the phrase, so an empty
 * `authorization` is valid there — that is what zero-touch auto-pairing uses.
 */
export async function pairConfirm(
  pairingCode: string,
  authorization: string,
): Promise<PairConfirmResult> {
  try {
    const r = await api("/v1/cockpit/pair/confirm", {
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

// ---- zero-touch auto-pairing (native shell + loopback gateway) -------------

export type AutoPairOutcome =
  | "paired" // a fresh per-device token was minted and stored
  | "already-paired" // a token already exists — nothing to do
  | "blocked" // the gateway demands the owner phrase (external mode) — manual pairing required
  | "unavailable"; // gateway unreachable / rate-limited / not applicable — retry later

// Auto-pair bookkeeping: single-flight, spaced attempts (the gateway
// rate-limits pair/start to one per 30s), and a latch once the server says
// the owner phrase is required so we never hammer an external-mode gateway.
let autoPairInFlight: Promise<AutoPairOutcome> | null = null;
let autoPairLastAttempt = 0;
let autoPairBlocked = false;
const AUTO_PAIR_MIN_INTERVAL_MS = 30_000;

/** True iff the server latched auto-pairing off (owner phrase required). */
export function isAutoPairBlocked(): boolean {
  return autoPairBlocked;
}

/**
 * Zero-touch pairing for the desktop shell: install → open → connected.
 *
 * On a loopback-only gateway the server deliberately does NOT require the
 * owner phrase to confirm a pairing code (anything that can reach 127.0.0.1
 * is already on this machine — see gateway/cockpit/handlers.py:pair_confirm).
 * So when the app runs inside the native shell, points at a loopback base and
 * has no token yet, it silently walks pair/start → pair/confirm and stores
 * the minted per-device token. Manual pairing (Settings) stays for remote
 * gateways, where the owner phrase is enforced and this returns "blocked".
 *
 * `force` bypasses the shell/interval gates (the Settings "Reconnect" button)
 * but never the loopback requirement.
 */
export function autoPairLocal(opts?: { force?: boolean }): Promise<AutoPairOutcome> {
  const force = opts?.force === true;
  if (!force && getToken()) return Promise.resolve("already-paired");
  if (!isLoopbackBase()) return Promise.resolve("blocked");
  if (!force) {
    if (!isTauri()) return Promise.resolve("unavailable");
    if (autoPairBlocked) return Promise.resolve("blocked");
    if (Date.now() - autoPairLastAttempt < AUTO_PAIR_MIN_INTERVAL_MS) {
      return Promise.resolve("unavailable");
    }
  }
  if (autoPairInFlight) return autoPairInFlight;
  autoPairLastAttempt = Date.now();
  autoPairInFlight = (async (): Promise<AutoPairOutcome> => {
    try {
      const started = await pairStart(defaultDeviceName());
      if (!started.ok || !started.pairingCode) return "unavailable";
      const confirmed = await pairConfirm(started.pairingCode, "");
      if (confirmed.forbidden) {
        autoPairBlocked = true; // external-mode gateway — owner phrase required
        return "blocked";
      }
      return confirmed.ok ? "paired" : "unavailable";
    } catch {
      return "unavailable";
    } finally {
      autoPairInFlight = null;
    }
  })();
  return autoPairInFlight;
}

/** A human-recognizable default device name for auto-pairing. */
function defaultDeviceName(): string {
  let platform = "";
  try {
    platform = String(navigator.platform || "").trim();
  } catch {
    /* navigator unavailable */
  }
  return "muse desktop" + (platform ? " (" + platform + ")" : "");
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
  signal?: AbortSignal,
): Promise<string> {
  const request = (path: string) =>
    api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, history }),
      signal,
    });

  let r: Response;
  try {
    // Prefer the full agent (tools, coding, approvals). A gateway started in
    // normal JARVIS mode answers 409, in which case the lean responder remains
    // a transparent fallback rather than breaking desktop chat.
    r = await request("/v1/agent/chat");
    if (r.status === 409) r = await request("/v1/jarvis/chat");
  } catch (error) {
    if (signal?.aborted) return "";
    cb?.onError?.("Can't reach the gateway — is the brain running? (Settings → Brain)");
    return "";
  }
  if (!r.ok || !r.body) {
    const msg =
      r.status === 401
        ? "Not paired — open Settings to connect this device."
        : r.status === 503
          ? "Can't reach the gateway — is the brain running? (Settings → Brain)"
          : "error: " + r.status;
    cb?.onError?.(msg);
    return "";
  }

  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let acc = "";
  let sawBodyDelta = false;
  const consume = (line: string) => {
    if (!line) return;
    try {
      const obj = JSON.parse(line) as Record<string, unknown>;
      if (obj.type === "error" || obj.error) {
        cb?.onError?.(String(obj.message ?? obj.error ?? "Agent error"));
      } else if (obj.type === "body" && obj.text != null) {
        // Full mode follows token deltas with one canonical final body. Replace
        // the streamed draft instead of appending it; lean JARVIS mode emits
        // body chunks only, so those remain additive.
        const text = String(obj.text);
        acc = sawBodyDelta ? text : acc + text;
      } else if (obj.type === "body_delta" && obj.text != null) {
        sawBodyDelta = true;
        acc += String(obj.text);
      } else if (obj.role === "assistant" && obj.content != null) {
        // Compatibility with OpenAI-shaped NDJSON responders.
        acc += String(obj.content);
      } else if (obj.content != null && obj.role !== "user" && obj.role !== "system") {
        acc += String(obj.content);
      }
      cb?.onDelta?.(acc);
    } catch {
      // Keep a partial line buffered; malformed completed lines are ignored.
    }
  };

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        consume(buf.slice(0, nl).trim());
        buf = buf.slice(nl + 1);
      }
    }
    consume((buf + dec.decode()).trim());
  } catch {
    if (!signal?.aborted) {
      cb?.onError?.(acc ? acc + "\n[connection lost]" : "Connection lost mid-reply — try again.");
    }
  }
  return acc;
}

/** Interrupt the current full-agent turn. Safe to call against a lean gateway. */
export async function stopAgent(): Promise<void> {
  try {
    await api("/v1/agent/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
  } catch {
    // The local AbortController still stops rendering if the gateway is gone.
  }
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

/** One authenticated poll of GET /v1/cockpit/jobs. True iff data arrived. */
async function pollJobsOnce(handlers: JobStreamHandlers): Promise<boolean> {
  if (!getToken()) return false;
  try {
    const r = await api("/v1/cockpit/jobs");
    if (!r.ok) return false;
    const d = (await r.json()) as { jobs?: CockpitJob[] };
    if (d && Array.isArray(d.jobs)) {
      d.jobs.forEach((j) => handlers.onUpsert?.(j));
      return true;
    }
    return false;
  } catch {
    return false; /* offline */
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
    if (ctrl.signal.aborted || !getToken()) {
      handlers.onLive?.(false);
      return;
    }
    // The stream is down (gateway restarting, or an older gateway whose CORS
    // allowlist predates the desktop shell). Degrade to polling the snapshot
    // endpoint so the list keeps updating while we keep retrying the stream;
    // api() itself falls back to the native proxy when direct fetch is blocked.
    const polled = await pollJobsOnce(handlers);
    handlers.onLive?.(polled);
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

// ---- job phase rail (vocabulary + position) -------------------------------

/**
 * Canonical job lifecycle phases the rail walks through. Mirrors the cockpit's
 * (gateway/cockpit/static/index.html) collapsed, owner-meaningful progression
 * over the server's CockpitJob status vocabulary (contract.JOB_STATUSES).
 */
export const JOB_PHASES = [
  "QUEUED",
  "RUNNING",
  "WAITING_FOR_APPROVAL",
  "APPROVED",
  "PUBLISHING",
  "PUBLISHED",
] as const;

export type JobPhase = (typeof JOB_PHASES)[number];

export const JOB_PHASE_LABEL: Record<JobPhase, string> = {
  QUEUED: "Queued",
  RUNNING: "Running",
  WAITING_FOR_APPROVAL: "Approval",
  APPROVED: "Approved",
  PUBLISHING: "Publishing",
  PUBLISHED: "Published",
};

const TERMINAL_OK = new Set(["COMPLETED", "PUBLISHED"]);
const TERMINAL_BAD = new Set(["FAILED", "CANCELLED"]);

export type PhaseState = "done" | "current" | "pending" | "failed";

/**
 * Resolve, for a given job status, the visual state of each rail segment.
 * Mirrors the cockpit's `phaseRail` mapping exactly: COMPLETED maps to the end
 * of the build arc; paused/blocked/draft sit at the start; terminal-bad marks
 * the current segment failed.
 */
export function phaseStates(status: string | undefined): PhaseState[] {
  const st = String(status || "").toUpperCase();
  let idx: number = (JOB_PHASES as readonly string[]).indexOf(st);
  if (st === "COMPLETED") idx = JOB_PHASES.indexOf("PUBLISHED");
  if (st === "PAUSED" || st === "BLOCKED" || st === "DISCONNECTED" || st === "DRAFT") {
    idx = 0;
  }
  const failed = TERMINAL_BAD.has(st);
  return JOB_PHASES.map((_ph, i): PhaseState => {
    if (failed && i === Math.max(idx, 0)) return "failed";
    if (i < idx) return "done";
    if (i === idx) return TERMINAL_OK.has(st) ? "done" : "current";
    return "pending";
  });
}

// ---- approvals (owner-gated decide) ---------------------------------------

export type CockpitApproval = {
  id: string;
  title?: string;
  kind?: string;
  tier?: string;
  status?: string;
  summary?: string;
  proposed_action?: string;
  [k: string]: unknown;
};

export type ApprovalsResult =
  | { ok: true; approvals: CockpitApproval[] }
  | { ok: false; unauthorized?: boolean; error?: string };

/** GET /v1/cockpit/approvals. Tolerates the `approvals` or `items` envelope. */
export async function getApprovals(): Promise<ApprovalsResult> {
  try {
    const r = await api("/v1/cockpit/approvals");
    if (!r.ok) {
      return { ok: false, unauthorized: r.status === 401, error: String(r.status) };
    }
    const d = (await r.json()) as {
      approvals?: CockpitApproval[];
      items?: CockpitApproval[];
    };
    return { ok: true, approvals: d.approvals || d.items || [] };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

export type DecideResult = {
  ok: boolean;
  /** Server demanded the owner phrase (or it mismatched). */
  forbidden?: boolean;
  error?: string;
};

/**
 * POST /v1/cockpit/approvals/{id}. `approve` is owner-gated: pass the owner
 * `authorization` phrase (prompted for at action time, never stored). `reject`
 * needs no phrase, but a 403 is surfaced as `forbidden` so the caller can
 * re-prompt once — exactly the cockpit's behavior.
 */
export async function decideApproval(
  id: string,
  decision: "approve" | "reject",
  authorization?: string,
): Promise<DecideResult> {
  const body: Record<string, unknown> = { decision };
  if (authorization) body.authorization = authorization;
  try {
    const r = await api("/v1/cockpit/approvals/" + encodeURIComponent(id), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (r.status === 403) return { ok: false, forbidden: true };
    if (!r.ok) {
      const d = await r.json().catch(() => ({}) as Record<string, unknown>);
      return { ok: false, error: String(d.error ?? r.status) };
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

// ---- autonomy (raise is owner-gated; lower/revoke is token-only) ----------

export type AutonomyCapabilities = {
  auto_approved?: string[];
  requires_approval?: string[];
  always_deny?: string[];
};

export type AutonomyState = {
  level?: string;
  display_name?: string;
  set_by?: string;
  workspace_root?: string;
  capabilities?: AutonomyCapabilities;
  [k: string]: unknown;
};

export type AutonomyResult =
  | { ok: true; state: AutonomyState }
  | { ok: false; unauthorized?: boolean; error?: string };

/** The selectable autonomy levels, in display order (mirrors the cockpit). */
export const AUTONOMY_LEVELS: ReadonlyArray<readonly [string, string]> = [
  ["read_only", "Read-only"],
  ["assisted", "Assisted"],
  ["autonomous", "Autonomous"],
  ["yolo", "YOLO"],
  ["owner_high_autonomy_coding", "High-Autonomy Coding"],
];

/**
 * Ordinal rank used to decide whether a level change is a *raise* (more
 * autonomy). A raise is owner-gated; the same ranking the cockpit uses.
 */
export const AUTONOMY_RANK: Record<string, number> = {
  read_only: 0,
  assisted: 1,
  autonomous: 2,
  owner_high_autonomy_coding: 3,
  yolo: 4,
};

/** True iff moving `from`→`to` increases autonomy (an owner-gated raise). */
export function isAutonomyRaise(from: string, to: string): boolean {
  return (AUTONOMY_RANK[to] ?? 0) > (AUTONOMY_RANK[from] ?? 0);
}

/** GET /v1/cockpit/autonomy. */
export async function getAutonomy(): Promise<AutonomyResult> {
  try {
    const r = await api("/v1/cockpit/autonomy");
    if (!r.ok) {
      return { ok: false, unauthorized: r.status === 401, error: String(r.status) };
    }
    const d = (await r.json()) as AutonomyState;
    return { ok: true, state: d };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

export type SetAutonomyResult = {
  ok: boolean;
  forbidden?: boolean;
  error?: string;
};

/**
 * POST /v1/cockpit/autonomy to set the level. A raise (more autonomy than the
 * current level) is owner-gated server-side; pass the `authorization` phrase
 * for raises (sending it on a lower/equal change is harmless). `workspacePath`
 * scopes High-Autonomy Coding. A 403 is surfaced for a single re-prompt.
 */
export async function setAutonomy(
  level: string,
  opts?: { authorization?: string; workspacePath?: string },
): Promise<SetAutonomyResult> {
  const body: Record<string, unknown> = { level };
  if (opts?.workspacePath) body.workspace_path = opts.workspacePath;
  if (opts?.authorization) body.authorization = opts.authorization;
  return postAutonomy(body);
}

/** POST /v1/cockpit/autonomy with `revoke: true` (token-only; lowers to Assisted). */
export async function revokeAutonomy(): Promise<SetAutonomyResult> {
  return postAutonomy({ revoke: true });
}

async function postAutonomy(body: Record<string, unknown>): Promise<SetAutonomyResult> {
  try {
    const r = await api("/v1/cockpit/autonomy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (r.status === 403) return { ok: false, forbidden: true };
    if (!r.ok) {
      const d = await r.json().catch(() => ({}) as Record<string, unknown>);
      return { ok: false, error: String(d.error ?? r.status) };
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

// ---- emergency stop (owner-gated) -----------------------------------------

/**
 * POST /v1/cockpit/emergency-stop — cancel all jobs and latch autonomy to
 * read-only. Owner-gated: pass the owner `authorization` phrase. A 403 is
 * surfaced so the caller can re-prompt once.
 */
export async function emergencyStop(authorization?: string): Promise<SetAutonomyResult> {
  const body: Record<string, unknown> = {};
  if (authorization) body.authorization = authorization;
  try {
    const r = await api("/v1/cockpit/emergency-stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (r.status === 403) return { ok: false, forbidden: true };
    if (!r.ok) {
      const d = await r.json().catch(() => ({}) as Record<string, unknown>);
      return { ok: false, error: String(d.error ?? r.status) };
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

// ---- owner-gate helper ----------------------------------------------------

/**
 * Prompt for the owner authorization phrase at the moment of an owner-gated
 * action. Returns the trimmed phrase, or null if the user cancelled. The phrase
 * is NEVER persisted (no localStorage, no module state) — it is handed straight
 * to the request and discarded. Mirrors the cockpit's `promptOwnerPhrase`.
 */
export function promptOwnerPhrase(action: string): string | null {
  let v: string | null;
  try {
    v = window.prompt(
      "Owner-gated: " +
        action +
        "\n\nEnter the exact owner authorization phrase to proceed.",
    );
  } catch {
    return null;
  }
  if (v == null) return null;
  return v.trim();
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
