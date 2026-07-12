import { useEffect, useRef, useState } from 'react';
import { Galaxy } from '@/components/observatory/Galaxy';
import { StationPipeline } from '@/components/observatory/StationPipeline';
import { BrainLadder } from '@/components/observatory/BrainLadder';
import { useNexusStore } from '@/store/useNexusStore';
import { fetchSnapshot, streamObservatory } from '@/adapters/observatory';
import type { ObsActiveJob, ObsSnapshot, ObsStreamEvent } from '@/lib/types';

export default function ObservatoryPage() {
  const wallpaper = useNexusStore((s) => s.wallpaper);
  const setWallpaper = useNexusStore((s) => s.setWallpaper);
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

  const applySnapshot = (snap: ObsSnapshot | null) => {
    setSnapshot(snap);
    setActiveJobs(snap?.stations.active_jobs ?? []);
    setQueueDepth(snap?.stations.queue_depth ?? 0);
    setQueuePulse(Math.min(1, (snap?.stations.queue_depth ?? 0) / 6));
  };

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetchSnapshot().then((snap) => {
      if (!alive) return;
      applySnapshot(snap);
      setLoading(false);
    });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    const id = window.setInterval(() => {
      setPulses((prev) => {
        const next: Record<string, number> = {};
        let changed = false;
        for (const [key, value] of Object.entries(prev)) {
          const decayed = value * 0.88;
          if (decayed > 0.02) next[key] = decayed;
          changed = true;
        }
        return changed ? next : prev;
      });
    }, 80);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const onEvent = (event: ObsStreamEvent) => {
      switch (event.type) {
        case 'node.activate':
          setPulses((current) => ({ ...current, [event.cluster_id]: Math.min(1, (current[event.cluster_id] ?? 0) + event.weight) }));
          break;
        case 'job.stage':
          setQueueDepth(event.queue_depth);
          setQueuePulse(Math.min(1, event.queue_depth / 6));
          setActiveJobs((jobs) => {
            const others = jobs.filter((job) => job.job_id !== event.job_id);
            if (event.stage === 'done' || event.stage === 'failed') return others;
            return [...others, { job_id: event.job_id, task_class: event.task_class, stage: event.stage, stage_entered_at: event.ts, queue_pos: null }];
          });
          break;
        case 'gate.verdict':
          setGateFlare({ verdict: event.verdict, ts: Date.now() });
          break;
        case 'route.decision':
          setStreakTier(event.tier);
          window.setTimeout(() => setStreakTier(null), 1000);
          break;
        case 'resync':
          void fetchSnapshot().then(applySnapshot);
          break;
      }
    };
    return streamObservatory(onEvent);
  }, []);

  const dormant = !snapshot || !snapshot.graph.available;
  const status = dormant ? 'DORMANT' : 'LIVE';
  const statusColor = dormant ? 'var(--ink-faint)' : 'var(--state-running)';

  if (wallpaper) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[var(--bg-base)]">
        <Galaxy snapshot={snapshot} pulses={pulses} queuePulse={queuePulse} height={Math.min(window.innerHeight * 0.74, 520)} />
        <div className="absolute left-4 top-[calc(env(safe-area-inset-top)+12px)] flex items-center gap-2">
          <span className="mono rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: `${statusColor}22`, color: statusColor }}>{status}</span>
          <span className="mono text-[10px] text-[var(--ink-dim)]">MUSE · Neural Observatory</span>
        </div>
        <button onClick={() => setWallpaper(false)} className="absolute right-4 top-[calc(env(safe-area-inset-top)+10px)] rounded-full border border-[var(--hairline)] px-3 py-1.5 text-[11px]">Exit wallpaper</button>
        {dormant && <div className="mono mt-3 text-[11px] text-[var(--ink-dim)]">Observatory dormant — awaiting live graph telemetry</div>}
      </div>
    );
  }

  return (
    <div className="px-4 pb-6">
      <div className="glass mb-3 flex items-center justify-between px-3 py-2.5">
        <div>
          <div className="text-[13px] font-semibold">Neural Observatory</div>
          <div className="mono text-[10px] text-[var(--ink-dim)]">
            {dormant ? 'live system mirror · no graph telemetry available' : `live system mirror · ${snapshot?.graph.node_count?.toLocaleString() ?? 0} nodes`}
          </div>
        </div>
        <span className="mono rounded-full px-2.5 py-1 text-[10px] font-bold" style={{ background: `${statusColor}22`, color: statusColor }}>{status}</span>
      </div>

      <div className="glass flex flex-col items-center overflow-hidden px-2 py-3">
        {loading ? <div className="grid h-[300px] place-items-center text-[12px] text-[var(--ink-dim)]">Reading live observatory…</div> : <Galaxy snapshot={snapshot} pulses={pulses} queuePulse={queuePulse} />}
        {dormant && !loading && (
          <div className="-mt-6 mb-2 text-center">
            <div className="text-[12px] text-[var(--ink-dim)]">Observatory dormant</div>
            <div className="text-[10px] text-[var(--ink-faint)]">Connect the gateway to render the live knowledge graph and execution stream.</div>
          </div>
        )}
      </div>

      <div className="mt-3 flex gap-2">
        <button onClick={() => setWallpaper(true)} className="flex-1 rounded-md px-3 py-2 text-[12px] font-semibold text-black" style={{ background: 'var(--octa-glow)' }}>Wallpaper mode</button>
        <button onClick={() => void fetchSnapshot().then(applySnapshot)} className="rounded-md border border-[var(--hairline)] px-4 py-2 text-[12px] font-medium">Refresh live data</button>
      </div>

      <div className="mt-3 flex flex-col gap-3">
        <StationPipeline nodes={snapshot?.stations.nodes ?? []} activeJobs={activeJobs} queueDepth={queueDepth} gateFlare={gateFlare} />
        <BrainLadder tiers={snapshot?.ladder.tiers ?? []} streakTier={streakTier} />
      </div>
    </div>
  );
}
