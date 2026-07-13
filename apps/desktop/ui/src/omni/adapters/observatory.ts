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

/** Subscribe to the authenticated live delta stream. Native EventSource cannot
 * attach the required bearer header, so consume SSE over fetch and reconnect
 * with bounded backoff. This keeps desktop telemetry genuinely live. */
export function streamObservatory(onEvent: (e: ObsStreamEvent) => void): () => void {
  if (!museBase() || typeof fetch === 'undefined') return () => {};
  const controller = new AbortController();
  let stopped = false;

  const connect = async () => {
    let delay = 750;
    while (!stopped) {
      try {
        const response = await fetch(obsUrl('/stream'), {
          headers: { ...authHeaders(), Accept: 'text/event-stream' },
          signal: controller.signal,
          cache: 'no-store',
        });
        if (!response.ok || !response.body) throw new Error(`observatory stream ${response.status}`);
        delay = 750;
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let eventName = 'message';
        let dataLines: string[] = [];

        const dispatch = () => {
          if (!dataLines.length) return;
          try {
            const payload = JSON.parse(dataLines.join('\n')) as Record<string, unknown>;
            const type = (eventName === 'message' ? payload.type : eventName) as ObsStreamEvent['type'];
            if (type) onEvent({ ...payload, type } as ObsStreamEvent);
          } catch {
            /* malformed frames are discarded; telemetry is never invented */
          }
          eventName = 'message';
          dataLines = [];
        };

        while (!stopped) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split(/\r?\n/);
          buffer = lines.pop() ?? '';
          for (const line of lines) {
            if (!line) dispatch();
            else if (line.startsWith('event:')) eventName = line.slice(6).trim();
            else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
          }
        }
        dispatch();
      } catch (error) {
        if (stopped || controller.signal.aborted) break;
        await new Promise((resolve) => window.setTimeout(resolve, delay));
        delay = Math.min(delay * 1.8, 10_000);
      }
    }
  };
  void connect();
  return () => { stopped = true; controller.abort(); };
}
