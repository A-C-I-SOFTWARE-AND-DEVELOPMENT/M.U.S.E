import { useCallback, useEffect, useState } from 'react';
import { cockpit, type CockpitApproval } from '@/adapters/cockpit';
import { useLinkState } from '@/lib/health';
import { routeForPath } from '@/universe/catalog';
import { UniversePage } from '@/universe/components/UniversePage';

const OWNER_PHRASE = 'Yes, with authorization.';

function asApprovals(raw: { approvals?: CockpitApproval[] } | CockpitApproval[] | null): CockpitApproval[] {
  if (!raw) return [];
  return Array.isArray(raw) ? raw : raw.approvals ?? [];
}

export default function ApprovalsPage() {
  const connected = useLinkState() === 'gateway';
  const [list, setList] = useState<CockpitApproval[]>([]);
  const [phrase, setPhrase] = useState('');
  const [error, setError] = useState<string | null>(null);
  const route = routeForPath('/approvals');
  const exact = phrase.trim() === OWNER_PHRASE;

  const refresh = useCallback(() => {
    if (!connected) {
      setList([]);
      setError(null);
      return;
    }
    void cockpit
      .approvals()
      .then((raw) => {
        setList(asApprovals(raw));
        setError(null);
      })
      .catch(() => {
        setList([]);
        setError('Gateway approvals endpoint did not respond.');
      });
  }, [connected]);

  useEffect(() => {
    refresh();
    if (!connected) return;
    const timer = window.setInterval(refresh, 10000);
    return () => window.clearInterval(timer);
  }, [connected, refresh]);

  return (
    <UniversePage
      route={route}
      eyebrow="Owner control"
      title="Approvals"
      description="Pending owner-gated actions from the live Muse gateway. Spend, deploy, publish, OAuth, and credential changes wait here until you authorize them."
    >
      <section className="universe-panel" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {!connected && (
          <div className="glass px-4 py-8 text-center text-[12px] text-[var(--ink-dim)]">
            Requires a reachable Muse gateway. No sample approvals are shown.
          </div>
        )}
        {connected && error && (
          <div className="glass px-4 py-6 text-center text-[12px]" style={{ color: 'var(--danger)' }}>{error}</div>
        )}
        {connected && !error && list.length === 0 && (
          <div className="glass px-4 py-10 text-center">
            <div className="text-[13px] text-[var(--ink)]">No pending owner-gated actions</div>
            <div className="mt-1 text-[11px] text-[var(--ink-faint)]">When the agent needs authorization, the request appears here live.</div>
          </div>
        )}
        {list.map((item) => (
          <article key={item.id} className="glass px-3 py-3">
            <div className="text-[13px] font-semibold text-[var(--ink)]">{item.title ?? item.action ?? item.id}</div>
            {item.risk && <div className="mono mt-1 text-[10px]" style={{ color: 'var(--warn)' }}>{item.risk}</div>}
            {item.detail && <p className="mt-2 text-[12px] text-[var(--ink-dim)]">{String(item.detail)}</p>}
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                className="universe-button universe-button--primary"
                disabled={!exact}
                onClick={() => void cockpit.approve(item.id, phrase).then(refresh)}
              >
                Approve
              </button>
              <button type="button" className="universe-button" onClick={() => void cockpit.deny(item.id).then(refresh)}>
                Deny
              </button>
            </div>
          </article>
        ))}
        {connected && (
          <label className="production-instruction">
            Owner phrase
            <input
              value={phrase}
              onChange={(event) => setPhrase(event.target.value)}
              placeholder={OWNER_PHRASE}
              className="mt-1 w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2.5 py-2 text-[12px] text-[var(--ink)]"
              style={{ borderColor: exact ? 'var(--ok)' : undefined }}
            />
            <span className="mt-1 block text-[10px] text-[var(--ink-faint)]">
              Type exactly “Yes, with authorization.” — the phrase is never stored.
            </span>
          </label>
        )}
      </section>
    </UniversePage>
  );
}
