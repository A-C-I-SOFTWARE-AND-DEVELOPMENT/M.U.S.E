import { useCallback, useEffect, useState } from 'react';
import { cockpit, type CockpitJob } from '@/adapters/cockpit';
import { useLinkState } from '@/lib/health';
import { routeForPath } from '@/universe/catalog';
import { UniversePage } from '@/universe/components/UniversePage';

function asJobs(raw: { jobs?: CockpitJob[] } | CockpitJob[] | null): CockpitJob[] {
  if (!raw) return [];
  return Array.isArray(raw) ? raw : raw.jobs ?? [];
}

export default function JobsPage() {
  const connected = useLinkState() === 'gateway';
  const [jobs, setJobs] = useState<CockpitJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const route = routeForPath('/jobs');

  const refresh = useCallback(() => {
    if (!connected) {
      setJobs([]);
      setError(null);
      return;
    }
    void cockpit
      .jobs()
      .then((raw) => {
        setJobs(asJobs(raw));
        setError(null);
      })
      .catch(() => {
        setJobs([]);
        setError('Gateway jobs endpoint did not respond.');
      });
  }, [connected]);

  useEffect(() => {
    refresh();
    if (!connected) return;
    const timer = window.setInterval(refresh, 8000);
    return () => window.clearInterval(timer);
  }, [connected, refresh]);

  const act = async (id: string, action: 'approve' | 'pause' | 'resume' | 'cancel') => {
    setBusy(id + action);
    const fn = {
      approve: cockpit.jobApprove,
      pause: cockpit.jobPause,
      resume: cockpit.jobResume,
      cancel: cockpit.jobCancel,
    }[action];
    await fn(id);
    setBusy(null);
    refresh();
  };

  return (
    <UniversePage
      route={route}
      eyebrow="Live orchestration"
      title="Jobs"
      description="Authoritative gateway job stream — approve, pause, resume, or cancel real cockpit work. Empty when nothing is in flight."
    >
      <section className="universe-panel production-grid" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="flex items-center justify-between gap-3">
          <p className="universe-eyebrow">{connected ? `${jobs.length} live job${jobs.length === 1 ? '' : 's'}` : 'gateway offline'}</p>
          <button type="button" className="universe-button" onClick={refresh} disabled={!connected}>Refresh</button>
        </div>
        {!connected && (
          <div className="glass px-4 py-8 text-center text-[12px] text-[var(--ink-dim)]">
            Connect a Muse gateway to mirror live jobs. Nothing is fabricated while offline.
          </div>
        )}
        {connected && error && (
          <div className="glass px-4 py-6 text-center text-[12px]" style={{ color: 'var(--danger)' }}>{error}</div>
        )}
        {connected && !error && jobs.length === 0 && (
          <div className="glass px-4 py-10 text-center">
            <div className="text-[13px] text-[var(--ink)]">No jobs in flight</div>
            <div className="mt-1 text-[11px] text-[var(--ink-faint)]">Orchestrate a goal from Console or Fleet — results stream here live.</div>
          </div>
        )}
        {jobs.map((job) => {
          const state = String(job.state ?? job.status ?? 'unknown');
          return (
            <article key={job.id} className="glass flex flex-col gap-2 px-3 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-[13px] font-semibold text-[var(--ink)]">{job.goal ?? job.id}</div>
                  <div className="mono mt-0.5 text-[10px] text-[var(--ink-faint)]">{job.id} · {state}{job.created_at ? ` · ${job.created_at}` : ''}</div>
                </div>
                <span className="universe-chip">{state}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {(['approve', 'pause', 'resume', 'cancel'] as const).map((action) => (
                  <button
                    key={action}
                    type="button"
                    className="universe-button"
                    disabled={busy === job.id + action}
                    onClick={() => void act(job.id, action)}
                  >
                    {busy === job.id + action ? '…' : action}
                  </button>
                ))}
              </div>
            </article>
          );
        })}
      </section>
    </UniversePage>
  );
}
