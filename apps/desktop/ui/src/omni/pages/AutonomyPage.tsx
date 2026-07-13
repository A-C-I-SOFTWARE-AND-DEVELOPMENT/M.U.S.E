import { useCallback, useEffect, useState } from 'react';
import { cockpit } from '@/adapters/cockpit';
import { useLinkState } from '@/lib/health';
import { routeForPath } from '@/universe/catalog';
import { UniversePage } from '@/universe/components/UniversePage';

const BANDS = ['B0', 'B1', 'B2', 'B3'] as const;

export default function AutonomyPage() {
  const connected = useLinkState() === 'gateway';
  const [state, setState] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const route = routeForPath('/autonomy');

  const refresh = useCallback(() => {
    if (!connected) {
      setState(null);
      setError(null);
      return;
    }
    void cockpit
      .autonomy()
      .then((raw) => {
        setState(raw);
        setError(null);
      })
      .catch(() => {
        setState(null);
        setError('Gateway autonomy endpoint did not respond.');
      });
  }, [connected]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const setBand = async (band: string) => {
    setBusy(band);
    await cockpit.setAutonomy(band);
    setBusy(null);
    refresh();
  };

  const band = String(state?.band ?? state?.level ?? state?.autonomy ?? 'not reported');

  return (
    <UniversePage
      route={route}
      eyebrow="Capability bands"
      title="Autonomy"
      description="Live B0–B3 capability wall from the Muse gateway. Higher bands auto-approve local friction only — owner gates are never weakened."
    >
      <section className="universe-panel" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {!connected && (
          <div className="glass px-4 py-8 text-center text-[12px] text-[var(--ink-dim)]">
            Connect a Muse gateway to read and set autonomy bands. No default band is invented offline.
          </div>
        )}
        {connected && error && (
          <div className="glass px-4 py-6 text-center text-[12px]" style={{ color: 'var(--danger)' }}>{error}</div>
        )}
        {connected && !error && (
          <>
            <div className="atlas-overview__core universe-panel" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div>
                <p className="universe-eyebrow">Reported band</p>
                <h2 className="mono" style={{ fontSize: 28 }}>{band}</h2>
                <p className="text-[11px] text-[var(--ink-faint)]">Workspace-scoped high-autonomy coding never bypasses owner authorization.</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {BANDS.map((entry) => (
                <button
                  key={entry}
                  type="button"
                  className="universe-button"
                  style={band === entry ? { borderColor: 'var(--ring-1)', color: 'var(--ring-1)' } : undefined}
                  disabled={busy === entry}
                  onClick={() => void setBand(entry)}
                >
                  {busy === entry ? '…' : entry}
                </button>
              ))}
            </div>
            {state && (
              <pre className="scroll-area mono overflow-auto rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] p-3 text-[10px] text-[var(--ink-dim)]" style={{ maxHeight: 280 }}>
                {JSON.stringify(state, null, 2)}
              </pre>
            )}
          </>
        )}
      </section>
    </UniversePage>
  );
}
