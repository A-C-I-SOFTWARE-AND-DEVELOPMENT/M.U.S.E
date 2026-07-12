// ============================================================================
// Forge Championship — read-only client for GET /v1/cockpit/forge/leaderboard
// (the tournament/championship Forge, distinct from NEXUS's per-agent-knowledge
// "Forge" tab). Glicko-2 standings + MAP-Elites coverage. Degrades honestly when
// no gateway is connected.
// ============================================================================

import { museBase, authHeaders } from './config';

export type ForgeStanding = Record<string, unknown>;

export interface ForgeLeaderboard {
  ok: boolean;
  standings: ForgeStanding[];
  candidates: number;
  coverage: number;
  qdScore: number;
  error?: string;
}

const EMPTY: Omit<ForgeLeaderboard, 'error'> = {
  ok: false,
  standings: [],
  candidates: 0,
  coverage: 0,
  qdScore: 0,
};

export async function fetchForgeLeaderboard(): Promise<ForgeLeaderboard> {
  const base = museBase();
  if (!base) return { ...EMPTY, error: 'No gateway connected — connect a MUSE gateway in Settings.' };
  try {
    const res = await fetch(`${base}/v1/cockpit/forge/leaderboard`, { headers: authHeaders() });
    if (!res.ok) return { ...EMPTY, error: `Gateway responded ${res.status}` };
    const d = await res.json();
    return {
      ok: true,
      standings: Array.isArray(d.standings) ? d.standings : [],
      candidates: typeof d.candidates === 'number' ? d.candidates : 0,
      coverage: typeof d.coverage === 'number' ? d.coverage : 0,
      qdScore: typeof d.qd_score === 'number' ? d.qd_score : 0,
    };
  } catch {
    return { ...EMPTY, error: 'Could not reach the gateway.' };
  }
}
