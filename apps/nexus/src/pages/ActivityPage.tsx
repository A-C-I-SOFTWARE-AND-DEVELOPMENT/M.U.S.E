import { useEffect, useState } from 'react';
import { activityStream } from '@/lib/activityStream';
import type { ActivityEvent } from '@/lib/types';

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

  useEffect(() => {
    activityStream.start();
    const off = activityStream.on((e) => setEvents((prev) => [e, ...prev].slice(0, 200)));
    return () => {
      off();
    };
  }, []);

  return (
    <div className="px-4 pb-6">
      <div className="hud-label mb-2 mt-1">Unified activity feed</div>
      {events.length === 0 ? (
        <div className="glass px-4 py-10 text-center">
          <div className="text-[12px] text-[var(--ink-dim)]">No events yet</div>
          <div className="mt-1 text-[10px] text-[var(--ink-faint)]">
            Runs, completions, errors and PRs from connected surfaces stream here.
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {events.map((e) => {
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
          })}
        </div>
      )}
    </div>
  );
}
