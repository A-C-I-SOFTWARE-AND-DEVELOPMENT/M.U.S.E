import type { ObsSnapshot, ObsStreamEvent } from '@/lib/types';

// ============================================================================
// Observatory adapter — the read-only /v1/observatory/* route family.
// Live by default; honest DORMANT state when the gateway is unset/unavailable
// (no fabricated activity). A separate, clearly-LABELLED sample topology lets
// the design be previewed without ever passing demo data off as telemetry.
// ============================================================================

const BASE = import.meta.env.VITE_MUSE_BASE_URL ?? '';

function obsUrl(path: string): string {
  return `${BASE.replace(/\/$/, '')}/v1/observatory${path}`;
}

/** Boot the map. Returns null when unconfigured or the graph is unavailable. */
export async function fetchSnapshot(): Promise<ObsSnapshot | null> {
  if (!BASE) return null;
  try {
    const res = await fetch(obsUrl('/snapshot'));
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
  if (!BASE || typeof EventSource === 'undefined') return () => {};
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

// --- Clearly-labelled SAMPLE topology (never presented as real telemetry) ---
// Mirrors the gateway stub's spec-shaped canned payloads. Used only when the
// user explicitly enables "Demo topology"; every render carries a SAMPLE badge.
export function sampleSnapshot(): ObsSnapshot {
  const clusters: ObsSnapshot['graph']['clusters'] = [
    { id: 'c-017', label: 'gateway/cockpit', type_mix: { code: 0.8, docs: 0.2 }, members: 412, pos: [62, -18, 40] as [number, number, number], radius: 4.2, heat: 0.62 },
    { id: 'c-042', label: 'orchestration', type_mix: { code: 0.7, test: 0.3 }, members: 318, pos: [-48, 30, -20] as [number, number, number], radius: 3.6, heat: 0.34 },
    { id: 'c-088', label: 'graphrag', type_mix: { code: 0.5, docs: 0.5 }, members: 256, pos: [20, 64, 10] as [number, number, number], radius: 3.1, heat: 0.81 },
    { id: 'c-103', label: 'skills', type_mix: { docs: 0.9, code: 0.1 }, members: 188, pos: [-70, -40, 30] as [number, number, number], radius: 2.7, heat: null },
    { id: 'c-211', label: 'memory', type_mix: { code: 0.6, docs: 0.4 }, members: 142, pos: [80, 48, -30] as [number, number, number], radius: 2.4, heat: 0.21 },
    { id: 'c-260', label: 'plugins', type_mix: { code: 0.85, test: 0.15 }, members: 96, pos: [-30, -70, -10] as [number, number, number], radius: 2.0, heat: 0.45 },
  ];
  return {
    v: 1,
    generated_at: new Date().toISOString(),
    sample: true,
    graph: {
      available: true,
      graph_version: 'sample-g0',
      node_count: 28600,
      edge_count: 51600,
      layout_algo: 'solar-orbital',
      clusters,
      cluster_edges: [
        { a: 'c-017', b: 'c-042', weight: 96, heat: 0.4 },
        { a: 'c-042', b: 'c-088', weight: 74, heat: 0.5 },
        { a: 'c-017', b: 'c-088', weight: 51, heat: 0.3 },
        { a: 'c-088', b: 'c-211', weight: 40, heat: null },
        { a: 'c-042', b: 'c-260', weight: 33, heat: 0.2 },
      ],
    },
    stations: {
      nodes: ['job', 'navigator', 'worker', 'gate', 'ledger'],
      active_jobs: [
        { job_id: 'jb-91ac', task_class: 'code', stage: 'worker', stage_entered_at: new Date().toISOString(), queue_pos: null },
        { job_id: 'jb-77de', task_class: 'docs', stage: 'gate', stage_entered_at: new Date().toISOString(), queue_pos: null },
      ],
      queue_depth: 3,
    },
    ladder: {
      tiers: [
        { tier: 'local', model: 'qwen2.5-3b-instruct-q4', share_1h: 0.62, p50_latency_ms: 840, p95_latency_ms: 2390 },
        { tier: 'hosted', model: 'claude-opus-4-8', share_1h: 0.28, p50_latency_ms: 1200, p95_latency_ms: 3100 },
        { tier: 'paired', model: 'gpt-via-bridge', share_1h: 0.10, p50_latency_ms: 1500, p95_latency_ms: 4200 },
      ],
    },
  };
}

/** A scripted sample event loop so the dashboard visibly "mirrors" in demo mode. */
export function sampleEventLoop(onEvent: (e: ObsStreamEvent) => void): () => void {
  const clusters = ['c-017', 'c-042', 'c-088', 'c-211', 'c-260'];
  const stages: ObsStreamEvent['type'][] = ['node.activate', 'job.stage', 'gate.verdict', 'route.decision'];
  let i = 0;
  const id = window.setInterval(() => {
    const pick = stages[i % stages.length];
    i++;
    const now = new Date().toISOString();
    if (pick === 'node.activate')
      onEvent({ type: 'node.activate', cluster_id: clusters[i % clusters.length], node_id: null, kind: 'query', weight: 0.4 + Math.random() * 0.6, ts: now });
    else if (pick === 'job.stage')
      onEvent({ type: 'job.stage', job_id: 'jb-91ac', task_class: 'code', stage: (['navigator', 'worker', 'gate', 'ledger'] as const)[i % 4], queue_depth: 2 + (i % 3), ts: now });
    else if (pick === 'gate.verdict')
      onEvent({ type: 'gate.verdict', job_id: 'jb-91ac', gate: 'test', verdict: i % 7 === 0 ? 'fail' : 'pass', attempt: 1, ts: now });
    else
      onEvent({ type: 'route.decision', turn_id: `t-${i}`, tier: (['local', 'hosted', 'paired'] as const)[i % 3], model: 'qwen2.5', reason: 'cheap-first', latency_ms: 800, ts: now });
  }, 1100);
  return () => window.clearInterval(id);
}
