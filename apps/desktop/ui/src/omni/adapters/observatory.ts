import type { ObsSnapshot, ObsStreamEvent } from '@/lib/types';
import { museBase, authHeaders } from '@/lib/config';

// ============================================================================
// Observatory adapter — live, read-only /v1/observatory/* telemetry.
// Unavailable systems remain honestly dormant; this adapter never fabricates.
// ============================================================================

function obsUrl(path: string): string {
  return `${museBase()}/v1/observatory${path}`;
}

/** Boot the map. Returns null when unconfigured or the graph is unavailable. */
export async function fetchSnapshot(): Promise<ObsSnapshot | null> {
  if (!museBase()) return null;
  try {
    const res = await fetch(obsUrl('/snapshot'), { headers: authHeaders() });
    if (!res.ok) return null;
    const raw = await res.json();
    // Tolerant of additive fields; map the {"status":"unavailable"} graph shape.
    const available = raw?.graph?.status !== 'unavailable' && Array.isArray(raw?.graph?.clusters);
    return {
      v: raw.v ?? 1,
      generated_at: raw.generated_at ?? new Date().toISOString(),
      graph: {
        available,
        graph_version: raw.graph?.graph_version ?? '',
        node_count: raw.graph?.node_count ?? 0,
        edge_count: raw.graph?.edge_count ?? 0,
        clusters: available ? raw.graph.clusters : [],
        cluster_edges: available ? raw.graph.cluster_edges ?? [] : [],
        layout_algo: raw.graph?.layout_algo,
      },
      stations: {
        nodes: raw.stations?.nodes ?? ['job', 'navigator', 'worker', 'gate', 'ledger'],
        active_jobs: raw.stations?.active_jobs ?? [],
        queue_depth: raw.stations?.queue_depth ?? 0,
      },
      ladder: { tiers: raw.ladder?.tiers ?? [] },
    };
  } catch {
    return null;
  }
}

/** Subscribe to the live delta stream (/stream). Returns an unsubscribe fn. */
export function streamObservatory(
  onEvent: (e: ObsStreamEvent) => void,
): () => void {
  if (!museBase() || typeof EventSource === 'undefined') return () => {};
  let es: EventSource | null = null;
  try {
    es = new EventSource(obsUrl('/stream'));
    const handle = (type: ObsStreamEvent['type']) => (ev: MessageEvent) => {
      try {
        onEvent({ type, ...JSON.parse(ev.data) } as ObsStreamEvent);
      } catch {
        /* drop malformed frame, never invent */
      }
    };
    (['job.stage', 'gate.verdict', 'node.activate', 'route.decision', 'resync'] as const).forEach(
      (t) => es!.addEventListener(t, handle(t)),
    );
  } catch {
    es = null;
  }
  return () => es?.close();
}
