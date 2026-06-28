import { useEffect, useRef, useState } from 'react';
import { Galaxy } from '@/components/observatory/Galaxy';
import { StationPipeline } from '@/components/observatory/StationPipeline';
import { BrainLadder } from '@/components/observatory/BrainLadder';
import { useNexusStore } from '@/store/useNexusStore';
import {
  fetchSnapshot,
  streamObservatory,
  sampleSnapshot,
  sampleEventLoop,
} from '@/adapters/observatory';
import type { ObsActiveJob, ObsSnapshot, ObsStreamEvent } from '@/lib/types';

export default function ObservatoryPage() {
  const wallpaper = useNexusStore((s) => s.wallpaper);
  const setWallpaper = useNexusStore((s) => s.setWallpaper);
  const demo = useNexusStore((s) => s.observatoryDemo);
  const setDemo = useNexusStore((s) => s.setObservatoryDemo);

  const [snapshot, setSnapshot] = useState<ObsSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [pulses, setPulses] = useState<Record<string, number>>({});
  const [queuePulse, setQueuePulse] = useState(0);
  const [activeJobs, setActiveJobs] = useState<ObsActiveJob[]>([]);
  const [queueDepth, setQueueDepth] = useState(0);
  const [gateFlare, setGateFlare] = useState<{ verdict: 'pass' | 'fail' | 'override'; ts: number } | null>(null);
  const [streakTier, setStreakTier] = useState<string | null>(null);
  const pulsesRef = useRef(pulses);
  pulsesRef.current = pulses;

  // Load snapshot (live, or clearly-labelled sample when demo is on).
  useEffect(() => {
    let alive = true;
    setLoading(true);
    const load = demo ? Promise.resolve(sampleSnapshot()) : fetchSnapshot();
    load.then((snap) => {
      if (!alive) return;
      setSnapshot(snap);
      setActiveJobs(snap?.stations.active_jobs ?? []);
      setQueueDepth(snap?.stations.queue_depth ?? 0);
      setQueuePulse(Math.min(1, (snap?.stations.queue_depth ?? 0) / 6));
      setLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [demo]);

  // Decay live pulses (~12fps) so activations bloom then fade — the "mirror".
  useEffect(() => {
    const id = window.setInterval(() => {
      setPulses((prev) => {
        const next: Record<string, number> = {};
        let changed = false;
        for (const [k, v] of Object.entries(prev)) {
          const nv = v * 0.88;
          if (nv > 0.02) { next[k] = nv; changed = true; }
          else changed = true;
        }
        return changed ? next : prev;
      });
    }, 80);
    return () => window.clearInterval(id);
  }, []);

  // Subscribe to the live delta stream (or scripted sample loop in demo).
  useEffect(() => {
    const onEvent = (e: ObsStreamEvent) => {
      switch (e.type) {
        case 'node.activate':
          setPulses((p) => ({ ...p, [e.cluster_id]: Math.min(1, (p[e.cluster_id] ?? 0) + e.weight) }));
          break;
        case 'job.stage':
          setQueueDepth(e.queue_depth);
          setQueuePulse(Math.min(1, e.queue_depth / 6));
          setActiveJobs((jobs) => {
            const others = jobs.filter((j) => j.job_id !== e.job_id);
            if (e.stage === 'done' || e.stage === 'failed') return others;
            return [...others, { job_id: e.job_id, task_class: e.task_class, stage: e.stage, stage_entered_at: e.ts, queue_pos: null }];
          });
          break;
        case 'gate.verdict':
          setGateFlare({ verdict: e.verdict, ts: Date.now() });
          break;
        case 'route.decision':
          setStreakTier(e.tier);
          window.setTimeout(() => setStreakTier(null), 1000);
          break;
        case 'resync':
          (demo ? Promise.resolve(sampleSnapshot()) : fetchSnapshot()).then(setSnapshot);
          break;
      }
    };
    const off = demo ? sampleEventLoop(onEvent) : streamObservatory(onEvent);
    return off;
  }, [demo]);

  const dormant = !snapshot || !snapshot.graph.available;
  const status = demo ? 'SAMPLE' : dormant ? 'DORMANT' : 'LIVE';
  const statusColor = demo ? '#FFB020' : dormant ? 'var(--ink-faint)' : 'var(--state-running)';

  // ---- Wallpaper ("mirror") mode: full-bleed galaxy, chrome hidden ----
  if (wallpaper) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[var(--bg-base)]">
        <Galaxy snapshot={snapshot} pulses={pulses} queuePulse={queuePulse} height={Math.min(window.innerHeight * 0.74, 520)} />
        <div className="absolute left-4 top-[calc(env(safe-area-inset-top)+12px)] flex items-center gap-2">
          <span className="mono rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: `${statusColor}22`, color: statusColor }}>
            {status}
          </span>
          <span className="mono text-[10px] text-[var(--ink-dim)]">NEXUS · Neural Observatory</span>
        </div>
        <button
          onClick={() => setWallpaper(false)}
          className="absolute right-4 top-[calc(env(safe-area-inset-top)+10px)] rounded-full border border-[var(--hairline)] px-3 py-1.5 text-[11px]"
        >
          Exit wallpaper
        </button>
        {dormant && !demo && (
          <div className="mono mt-3 text-[11px] text-[var(--ink-dim)]">Observatory dormant — no live graph</div>
        )}
      </div>
    );
  }

  return (
    <div className="px-4 pb-6">
      {/* Header */}
      <div className="glass mb-3 flex items-center justify-between px-3 py-2.5">
        <div>
          <div className="text-[13px] font-semibold">Neural Observatory</div>
          <div className="mono text-[10px] text-[var(--ink-dim)]">
            {demo
              ? `sample topology · ${snapshot?.graph.node_count?.toLocaleString() ?? 0} nodes (not live)`
              : dormant
                ? 'live system mirror · no live graph'
                : `live system mirror · ${snapshot?.graph.node_count?.toLocaleString() ?? 0} nodes`}
          </div>
        </div>
        <span className="mono rounded-full px-2.5 py-1 text-[10px] font-bold" style={{ background: `${statusColor}22`, color: statusColor }}>
          {status}
        </span>
      </div>

      {/* Galaxy */}
      <div className="glass flex flex-col items-center overflow-hidden px-2 py-3">
        {loading ? (
          <div className="grid h-[300px] place-items-center text-[12px] text-[var(--ink-dim)]">Reading observatory…</div>
        ) : (
          <Galaxy snapshot={snapshot} pulses={pulses} queuePulse={queuePulse} />
        )}
        {dormant && !demo && (
          <div className="-mt-6 mb-2 text-center">
            <div className="text-[12px] text-[var(--ink-dim)]">Observatory dormant</div>
            <div className="text-[10px] text-[var(--ink-faint)]">
              No live graph — connect the gateway, or preview the design with sample topology.
            </div>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          onClick={() => setWallpaper(true)}
          className="flex-1 rounded-md px-3 py-2 text-[12px] font-semibold text-black"
          style={{ background: 'var(--octa-glow)' }}
        >
          Wallpaper mode
        </button>
        <button
          onClick={() => setDemo(!demo)}
          className="flex-1 rounded-md border px-3 py-2 text-[12px] font-medium"
          style={{ borderColor: demo ? '#FFB020' : 'var(--hairline)', color: demo ? '#FFB020' : 'var(--ink)' }}
        >
          {demo ? 'Sample: ON' : 'Demo topology'}
        </button>
      </div>
      {demo && (
        <div className="mono mt-2 text-center text-[9px] text-[var(--ink-faint)]">
          SAMPLE topology — illustrative only, not live telemetry.
        </div>
      )}

      {/* Pipeline + Ladder */}
      <div className="mt-3 flex flex-col gap-3">
        <StationPipeline
          nodes={snapshot?.stations.nodes ?? []}
          activeJobs={activeJobs}
          queueDepth={queueDepth}
          gateFlare={gateFlare}
        />
        <BrainLadder tiers={snapshot?.ladder.tiers ?? []} streakTier={streakTier} />
      </div>
    </div>
  );
}
