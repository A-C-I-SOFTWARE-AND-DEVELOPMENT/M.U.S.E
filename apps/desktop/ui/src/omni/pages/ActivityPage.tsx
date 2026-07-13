import { useEffect, useState } from 'react';
import { activityStream } from '@/lib/activityStream';
import type { ActivityEvent } from '@/lib/types';
import { useLinkState } from '@/lib/health';
import { routeForPath } from '@/universe/catalog';
import { UniversePage } from '@/universe/components/UniversePage';

const KIND_META: Record<ActivityEvent['kind'], { color: string; glyph: string }> = {
  'run-started': { color: 'var(--acc-coding)', glyph: '▸' },
  'run-completed': { color: 'var(--state-running)', glyph: '✓' },
  error: { color: 'var(--state-error)', glyph: '✕' },
  'pr-opened': { color: 'var(--acc-creativity)', glyph: '⎘' },
  idle: { color: 'var(--state-idle)', glyph: '•' },
  'needs-auth': { color: 'var(--state-auth)', glyph: '🔒' },
};

export default function ActivityPage() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const connected = useLinkState() === 'gateway';
  const route = routeForPath('/activity');

  useEffect(() => {
    activityStream.start();
    const off = activityStream.on((e) => setEvents((prev) => [e, ...prev].slice(0, 200)));
    return () => {
      off();
    };
  }, []);

  return (
    <UniversePage
      route={route}
      eyebrow="Operational pulse"
      title="Activity"
      description="Unified live feed of runs, completions, errors, and PRs from connected Muse surfaces. Empty until real events arrive — nothing is seeded."
    >
      <section className="universe-panel" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {!connected && (
          <div className="glass px-4 py-6 text-center text-[12px] text-[var(--ink-dim)]">
            Gateway offline — the feed stays empty rather than inventing traffic.
          </div>
        )}
        {events.length === 0 ? (
          <div className="glass px-4 py-10 text-center">
            <div className="text-[13px] text-[var(--ink)]">No events yet</div>
            <div className="mt-1 text-[11px] text-[var(--ink-faint)]">
              Runs, completions, errors and PRs from connected surfaces stream here.
            </div>
          </div>
        ) : (
          events.map((e) => {
            const m = KIND_META[e.kind];
            return (
              <div key={e.id} className="glass flex items-start gap-3 px-3 py-2.5">
                <span className="mono mt-0.5 text-[13px]" style={{ color: m.color }}>
                  {m.glyph}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-[12px] text-[var(--ink)]">{e.message}</div>
                  <div className="mono mt-0.5 text-[9px] text-[var(--ink-faint)]">
                    {e.surface} · {new Date(e.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </section>
    </UniversePage>
  );
}
