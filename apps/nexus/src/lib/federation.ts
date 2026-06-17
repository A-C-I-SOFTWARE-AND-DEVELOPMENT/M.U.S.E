// ============================================================================
// Federation — read-only client for GET /v1/cockpit/federation/status.
// Surfaces this node's PUBLIC identity + known peers. The gateway never returns
// private key / secret material, so neither does this client. Degrades honestly
// when no gateway is connected.
// ============================================================================

import { museBase, authHeaders } from './config';

export interface FederationIdentity {
  node_id: string;
  display_name: string;
  created_at: string;
  algo: string;
  public_key_hex: string;
}

export type FederationPeer = Record<string, unknown>;

export interface FederationStatus {
  ok: boolean;
  identity: FederationIdentity | null;
  peers: FederationPeer[];
  peerCount: number;
  error?: string;
}

const EMPTY: Omit<FederationStatus, 'error'> = {
  ok: false,
  identity: null,
  peers: [],
  peerCount: 0,
};

export async function fetchFederationStatus(): Promise<FederationStatus> {
  const base = museBase();
  if (!base) return { ...EMPTY, error: 'No gateway connected — connect a MUSE gateway in Settings.' };
  try {
    const res = await fetch(`${base}/v1/cockpit/federation/status`, { headers: authHeaders() });
    if (!res.ok) return { ...EMPTY, error: `Gateway responded ${res.status}` };
    const d = await res.json();
    return {
      ok: true,
      identity: (d.identity as FederationIdentity) ?? null,
      peers: Array.isArray(d.peers) ? d.peers : [],
      peerCount: typeof d.peer_count === 'number' ? d.peer_count : 0,
    };
  } catch {
    return { ...EMPTY, error: 'Could not reach the gateway.' };
  }
}
