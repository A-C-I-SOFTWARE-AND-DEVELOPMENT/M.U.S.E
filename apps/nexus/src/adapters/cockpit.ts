// ============================================================================
// MUSE cockpit adapter — typed access to the full /v1/cockpit/* gateway surface
// (gateway/cockpit/). This is what makes EVERY MUSE README capability reachable
// from the PWA: orchestration, jobs, owner approvals, emergency stop, autonomy,
// memory tree, evidence/research, GraphRAG, model routing, learning, proposals,
// audit/verify_chain, runtime, skills, voice.
//
// Honest by construction: when VITE_MUSE_BASE_URL is unset every call resolves
// to a null/empty result so the UI shows "requires gateway", never fake data.
// ============================================================================

const BASE = import.meta.env.VITE_MUSE_BASE_URL ?? '';

export function cockpitConfigured(): boolean {
  return !!BASE;
}

function url(path: string): string {
  return `${BASE.replace(/\/$/, '')}/v1/cockpit${path}`;
}

async function get<T>(path: string): Promise<T | null> {
  if (!BASE) return null;
  try {
    const res = await fetch(url(path));
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

async function post<T>(path: string, body?: unknown): Promise<T | null> {
  if (!BASE) return null;
  try {
    const res = await fetch(url(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
  base: BASE,
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
