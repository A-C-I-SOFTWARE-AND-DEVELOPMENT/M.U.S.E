// ============================================================================
// MUSE cockpit adapter — typed access to the full /v1/cockpit/* gateway surface
// (gateway/cockpit/). This is what makes EVERY MUSE README capability reachable
// from the PWA: orchestration, jobs, owner approvals, emergency stop, autonomy,
// memory tree, evidence/research, GraphRAG, model routing, learning, proposals,
// audit/verify_chain, runtime, skills, voice.
//
// Two transports, picked automatically:
//   • direct  — fetch the configured gateway base directly (local / Termux /
//               same-origin, or any https gateway the browser can reach). The
//               per-device bearer is attached client-side via authHeaders().
//   • relay   — on a HOSTED https origin, route through this app's own
//               /api/gateway/... edge relay. A hosted https page CANNOT reach a
//               http://localhost gateway (mixed content) and must never hold a
//               per-account gateway bearer; the relay resolves the account's OWN
//               stored gateway + bearer SERVER-SIDE (no SSRF, no cross-account,
//               token never sent to the browser). The relay is authenticated
//               with the Supabase session credential, NOT the gateway bearer.
//
// Honest by construction: when nothing is configured every call resolves to a
// null/empty result so the UI shows "requires gateway", never fake data.
// ============================================================================

import { museBase, authHeaders, isConfigured, supabaseAnonCfg } from '@/lib/config';

export function cockpitConfigured(): boolean {
  // Direct path: a gateway base is configured locally. Relay path: hosted over
  // https with a Supabase session the server can resolve to a stored gateway.
  return isConfigured() || (useRelay() && !!supabaseAnonCfg());
}

/** True on a hosted https origin (not a local file:// or http://localhost dev /
 *  Termux origin). Only there does this app's own /api/gateway relay exist, and
 *  only there is a direct http://localhost gateway unreachable (mixed content). */
function hostedHttpsOrigin(): boolean {
  if (typeof window === 'undefined') return false;
  return window.location.protocol === 'https:';
}

/** Use the server relay when hosted over https — a direct fetch to a local
 *  http gateway would be blocked, and the per-account bearer must stay server
 *  side. Falls back to the direct path everywhere else (local / Termux / a
 *  reachable https gateway). */
function useRelay(): boolean {
  return hostedHttpsOrigin();
}

/** Authorization for the relay: the Supabase session credential the browser
 *  holds (so the server can resolve which account -> which stored gateway). The
 *  gateway's own per-account bearer is NEVER sent from the browser. */
function relayAuthHeaders(): Record<string, string> {
  const anon = supabaseAnonCfg();
  return anon ? { Authorization: `Bearer ${anon}` } : {};
}

function url(path: string): string {
  return `${museBase()}/v1/cockpit${path}`;
}

/** Relay URL: /api/gateway/<gateway-relative-path>. The server appends this to
 *  the account's STORED gateway base — the client never names the host. */
function relayUrl(path: string): string {
  return `/api/gateway/v1/cockpit${path}`;
}

async function get<T>(path: string): Promise<T | null> {
  const relay = useRelay();
  if (!relay && !museBase()) return null;
  try {
    const res = relay
      ? await fetch(relayUrl(path), { headers: relayAuthHeaders() })
      : await fetch(url(path), { headers: authHeaders() });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

async function post<T>(path: string, body?: unknown): Promise<T | null> {
  const relay = useRelay();
  if (!relay && !museBase()) return null;
  try {
    const target = relay ? relayUrl(path) : url(path);
    const auth = relay ? relayAuthHeaders() : authHeaders();
    const res = await fetch(target, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...auth },
      body: body == null ? undefined : JSON.stringify(body),
    });
    if (!res.ok) return null;
    const text = await res.text();
    return text ? (JSON.parse(text) as T) : ({} as T);
  } catch {
    return null;
  }
}

export interface CockpitJob {
  id: string;
  goal?: string;
  state?: string;
  status?: string;
  created_at?: string;
  [k: string]: unknown;
}

export interface CockpitApproval {
  id: string;
  action?: string;
  title?: string;
  risk?: string;
  detail?: string;
  [k: string]: unknown;
}

export interface RuntimeStatus {
  state?: string;
  workers?: number;
  autonomy?: string;
  [k: string]: unknown;
}

export const cockpit = {
  get base() {
    return museBase();
  },
  configured: cockpitConfigured,
  rawGet: get,
  rawPost: post,

  // Discovery
  capabilities: () => get<Record<string, unknown>>('/capabilities'),
  runtimeStatus: () => get<RuntimeStatus>('/runtime/status'),
  diagnostics: () => get<Record<string, unknown>>('/diagnostics'),

  // Orchestration & jobs
  orchestrate: (goal: string) => post<{ id?: string; job_id?: string }>('/orchestrate', { goal }),
  jobs: () => get<{ jobs?: CockpitJob[] } | CockpitJob[]>('/jobs'),
  job: (id: string) => get<CockpitJob>(`/jobs/${id}`),
  jobTree: (id: string) => get<unknown>(`/jobs/${id}/tree`),
  jobApprove: (id: string) => post(`/jobs/${id}/approve`),
  jobCancel: (id: string) => post(`/jobs/${id}/cancel`),
  jobPause: (id: string) => post(`/jobs/${id}/pause`),
  jobResume: (id: string) => post(`/jobs/${id}/resume`),

  // Owner control
  approvals: () => get<{ approvals?: CockpitApproval[] } | CockpitApproval[]>('/approvals'),
  approve: (id: string, phrase: string) => post(`/approvals/${id}`, { decision: 'approve', authorization: phrase }),
  deny: (id: string) => post(`/approvals/${id}`, { decision: 'deny' }),
  emergencyStop: () => post('/emergency-stop', { stop: true }),
  autonomy: () => get<Record<string, unknown>>('/autonomy'),
  setAutonomy: (band: string) => post('/autonomy', { band }),

  // Cognition plane
  memoryTree: () => get<unknown>('/memory/tree'),
  memorySearch: (q: string) => get<unknown>(`/memory?q=${encodeURIComponent(q)}`),
  contradictions: () => get<unknown>('/memory/contradictions'),
  evidenceSearch: (q: string) => get<unknown>(`/evidence/search?q=${encodeURIComponent(q)}`),
  research: () => get<unknown>('/research'),
  graphQuery: (q: string, scope = 'local') => post<unknown>('/graph/query', { query: q, scope }),

  // Intelligence
  modelRoutes: () => get<unknown>('/model-routes'),
  models: () => get<unknown>('/models'),
  localModels: () => get<unknown>('/models/local'),
  learning: () => get<unknown>('/learning'),
  proposals: () => get<unknown>('/proposals'),

  // Governance / evidence ledger
  audit: () => get<unknown>('/audit'),
  ledger: () => get<unknown>('/ledger'),
  axiom: () => get<unknown>('/axiom'),

  // Skills & sessions
  skills: () => get<unknown>('/skills'),
  sessions: () => get<unknown>('/sessions'),
  templates: () => get<unknown>('/templates'),
};
