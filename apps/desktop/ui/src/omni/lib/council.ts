// ============================================================================
// AOS Council dispatch — read-only client for GET /v1/cockpit/council/dispatch.
// Routes a request to the always-on active council + matching domain
// specialists (deterministic registry routing on the gateway). Degrades
// honestly when no gateway is connected.
// ============================================================================

import { museBase, authHeaders } from './config';

export interface CouncilMember {
  id: string;
  kind: string;
  role?: string;
  domain?: string;
  required_output?: string;
  owner_gated?: boolean;
}

export interface CouncilSession {
  ok: boolean;
  request: string;
  council: CouncilMember[];
  specialists: CouncilMember[];
  engagedCount: number;
  ownerGated: boolean;
  error?: string;
}

export async function dispatchCouncil(request: string): Promise<CouncilSession> {
  const base = museBase();
  const empty = {
    ok: false,
    request,
    council: [] as CouncilMember[],
    specialists: [] as CouncilMember[],
    engagedCount: 0,
    ownerGated: false,
  };
  if (!base) return { ...empty, error: 'No gateway connected — connect a MUSE gateway in Settings.' };
  try {
    const res = await fetch(
      `${base}/v1/cockpit/council/dispatch?q=${encodeURIComponent(request)}`,
      { headers: authHeaders() },
    );
    if (!res.ok) return { ...empty, error: `Gateway responded ${res.status}` };
    const d = await res.json();
    return {
      ok: true,
      request,
      council: Array.isArray(d.council) ? d.council : [],
      specialists: Array.isArray(d.specialists) ? d.specialists : [],
      engagedCount: typeof d.engaged_count === 'number' ? d.engaged_count : 0,
      ownerGated: !!d.owner_gated,
    };
  } catch {
    return { ...empty, error: 'Could not reach the gateway.' };
  }
}
