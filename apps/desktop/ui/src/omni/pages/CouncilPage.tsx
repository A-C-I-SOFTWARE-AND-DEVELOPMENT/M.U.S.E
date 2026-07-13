import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { dispatchCouncil, type CouncilSession, type CouncilMember } from '@/lib/council';
import { useLinkState } from '@/lib/health';

/** AOS Council Dispatch — route a request to the active council + matching
 *  domain specialists (the executable council runtime, via the gateway). */
export default function CouncilPage() {
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [session, setSession] = useState<CouncilSession | null>(null);
  const connected = useLinkState() === 'gateway';

  const run = async () => {
    const request = q.trim();
    if (!request || busy) return;
    setBusy(true);
    try {
      setSession(await dispatchCouncil(request));
    } finally {
      setBusy(false);
    }
  };

  const row = (m: CouncilMember) => (
    <div key={m.id} className="glass flex items-center justify-between px-3 py-2">
      <div className="min-w-0">
        <div className="mono text-[11px] text-[var(--ink)]">{m.id}</div>
        <div className="mono truncate text-[9px] text-[var(--ink-faint)]">
          {m.domain || m.role || ''}
        </div>
      </div>
      {m.owner_gated && (
        <span className="mono shrink-0 rounded-full px-1.5 py-0.5 text-[8px]" style={{ color: 'var(--state-auth)', border: '1px solid var(--state-auth)' }}>
          owner-gated
        </span>
      )}
    </div>
  );

  return (
    <div className="px-4 pb-6">
      <div className="glass mb-3 px-3 py-2.5">
        <div className="text-[13px] font-semibold">Council Dispatch</div>
        <div className="mono text-[10px] text-[var(--ink-dim)]">
          Route a request to the AOS active council + matching domain specialists.
        </div>
      </div>

      {!connected ? (
        <div className="glass px-4 py-8 text-center">
          <div className="text-[12px] text-[var(--ink-dim)]">No gateway connected</div>
          <button
            onClick={() => navigate('/settings')}
            className="mt-3 rounded-md px-3 py-1.5 text-[11px] font-semibold text-black"
            style={{ background: 'var(--octa-glow)' }}
          >
            Open Settings
          </button>
        </div>
      ) : (
        <>
          <div className="mb-3 flex gap-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void run(); }}
              placeholder="Describe the goal or decision…"
              className="flex-1 rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-3 py-2 text-[12px] text-[var(--ink)]"
            />
            <button
              onClick={() => void run()}
              disabled={busy || !q.trim()}
              className="rounded-md px-3 py-2 text-[11px] font-semibold text-black disabled:opacity-40"
              style={{ background: 'var(--octa-glow)' }}
            >
              {busy ? '…' : 'Dispatch'}
            </button>
          </div>

          {session?.error ? (
            <div className="glass mono px-3 py-3 text-[11px] text-[var(--state-error)]">{session.error}</div>
          ) : session ? (
            <>
              <div className="mono mb-2 text-[10px] text-[var(--ink-faint)]">
                {session.engagedCount} engaged{session.ownerGated ? ' · ⚠ owner-gated specialists' : ''}
              </div>
              <div className="hud-label mb-1.5">Active council · {session.council.length}</div>
              <div className="mb-3 flex flex-col gap-1.5">{session.council.map(row)}</div>
              <div className="hud-label mb-1.5">Specialists engaged · {session.specialists.length}</div>
              {session.specialists.length > 0 ? (
                <div className="flex flex-col gap-1.5">{session.specialists.map(row)}</div>
              ) : (
                <div className="glass mono px-3 py-4 text-center text-[10px] text-[var(--ink-dim)]">No domain specialist matched.</div>
              )}
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
