import { useEffect, useState } from 'react';

interface Metrics {
  loss?: number;
  accuracy?: number;
  epoch?: number;
  trainingSets?: number;
}

/**
 * Live telemetry (LOSS / ACCURACY / EPOCH + training-set grid), matching the
 * mock. Driven ONLY by the connected agent's real metrics endpoint. If no live
 * metrics are available we show an honest empty state — NEVER fabricated numbers.
 */
export function TelemetryPanel() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const base = import.meta.env.VITE_MUSE_BASE_URL ?? '';
    if (!base) {
      setLoading(false);
      return;
    }
    fetch(`${base}/api/metrics`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((m: Metrics) => alive && setMetrics(m))
      .catch(() => alive && setMetrics(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="glass flex flex-col gap-3 px-3 py-3">
      <div className="hud-label">Telemetry</div>

      {metrics ? (
        <>
          <div className="grid grid-cols-2 gap-2">
            <Stat label="LOSS" value={metrics.loss?.toFixed(3) ?? '—'} />
            <Stat
              label="ACCURACY"
              value={metrics.accuracy != null ? `${(metrics.accuracy * 100).toFixed(1)}%` : '—'}
            />
            <Stat label="EPOCH" value={metrics.epoch != null ? String(metrics.epoch) : '—'} />
            <Stat label="SETS" value={metrics.trainingSets != null ? String(metrics.trainingSets) : '—'} />
          </div>
          <div>
            <div className="hud-label mb-1.5">Training sets</div>
            <div className="grid grid-cols-4 gap-1">
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="aspect-square rounded-[4px] border border-[var(--hairline)]"
                  style={{ background: 'rgba(52,229,200,0.06)' }}
                />
              ))}
            </div>
          </div>
        </>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 py-6 text-center">
          <div
            className="grid h-9 w-9 place-items-center rounded-full border border-[var(--hairline)]"
            style={{ color: 'var(--ink-faint)' }}
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6">
              <polyline points="3,14 8,14 11,5 15,19 18,12 21,12" />
            </svg>
          </div>
          <div className="text-[11px] text-[var(--ink-dim)]">
            {loading ? 'Reading metrics…' : 'No live metrics'}
          </div>
          <div className="text-[10px] leading-snug text-[var(--ink-faint)]">
            Connect an agent to stream LOSS / ACCURACY / EPOCH.
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[8px] border border-[var(--hairline)] px-2 py-1.5">
      <div className="hud-label">{label}</div>
      <div className="mono mt-0.5 text-[15px] font-semibold text-[var(--ink)]">{value}</div>
    </div>
  );
}
