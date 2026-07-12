// ============================================================================
// Second Brain — read-only client for the gateway's hybrid-retrieval routes
// (GET /v1/cockpit/second-brain/{status,retrieve}). The Second Brain augments,
// never replaces, native retrieval and is opt-in on the gateway
// (MUSE_SECOND_BRAIN=1); this surface degrades honestly when it's off, the
// backend isn't ready, or no gateway is connected.
// ============================================================================

import { museBase, authHeaders } from './config';

export interface SecondBrainStatus {
  enabled: boolean;
  available: boolean;
  backend?: string;
  error?: string;
}

export interface SecondBrainResult {
  ok: boolean;
  enabled: boolean;
  available: boolean;
  backendReady: boolean;
  blocks: number;
  text: string;
  error?: string;
}

const EMPTY: Omit<SecondBrainResult, 'error'> = {
  ok: false,
  enabled: false,
  available: false,
  backendReady: false,
  blocks: 0,
  text: '',
};

/** Fetch whether the Second Brain is enabled/available + its backend. */
export async function fetchSecondBrainStatus(): Promise<SecondBrainStatus> {
  const base = museBase();
  if (!base) return { enabled: false, available: false, error: 'No gateway connected' };
  try {
    const res = await fetch(`${base}/v1/cockpit/second-brain/status`, { headers: authHeaders() });
    if (!res.ok) return { enabled: false, available: false, error: `Gateway responded ${res.status}` };
    const d = await res.json();
    return {
      enabled: !!d.enabled,
      available: !!d.available,
      backend: d?.settings?.backend,
      error: d.error,
    };
  } catch {
    return { enabled: false, available: false, error: 'Could not reach the gateway' };
  }
}

/** Retrieve fused Second Brain context for a query (read-only). */
export async function retrieveSecondBrain(query: string, topK?: number): Promise<SecondBrainResult> {
  const base = museBase();
  if (!base) {
    return { ...EMPTY, error: 'No gateway connected — connect a MUSE gateway in Settings → Connections.' };
  }
  const params = new URLSearchParams({ q: query });
  if (topK) params.set('top_k', String(topK));
  let res: Response;
  try {
    res = await fetch(`${base}/v1/cockpit/second-brain/retrieve?${params.toString()}`, {
      headers: authHeaders(),
    });
  } catch {
    return { ...EMPTY, error: 'Could not reach the gateway.' };
  }
  if (res.status === 401) {
    return { ...EMPTY, error: 'Not paired — pair this device with the gateway first.' };
  }
  if (!res.ok) {
    return { ...EMPTY, error: `Gateway responded ${res.status}.` };
  }
  let d: Record<string, unknown>;
  try {
    d = await res.json();
  } catch {
    return { ...EMPTY, error: 'Unexpected response from the gateway.' };
  }
  return {
    ok: true,
    enabled: !!d.enabled,
    available: !!d.available,
    backendReady: !!d.backend_ready,
    blocks: typeof d.blocks === 'number' ? d.blocks : 0,
    text: typeof d.text === 'string' ? d.text : '',
  };
}
