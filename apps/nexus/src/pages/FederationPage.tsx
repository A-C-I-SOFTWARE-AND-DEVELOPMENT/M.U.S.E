import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchFederationStatus, type FederationStatus } from '@/lib/federation';
import { museBase } from '@/lib/config';

/** Federation — this node's PUBLIC identity + known peers (read-only). The
 *  gateway never returns private key material, so neither does this view. */
export default function FederationPage() {
  const navigate = useNavigate();
  const [st, setSt] = useState<FederationStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const connected = !!museBase();

  useEffect(() => {
    if (!connected) return;
    let alive = true;
    setLoading(true);
    fetchFederationStatus()
      .then((s) => { if (alive) setSt(s); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [connected]);

  return (
    <div className="px-4 pb-6">
      <div className="glass mb-3 px-3 py-2.5">
        <div className="text-[13px] font-semibold">Federation</div>
        <div className="mono text-[10px] text-[var(--ink-dim)]">
          Sovereign-node identity + peers. Public material only — keys never leave the node.
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
      ) : loading && !st ? (
        <div className="glass px-4 py-8 text-center text-[12px] text-[var(--ink-dim)]">Reading federation status…</div>
      ) : st?.error ? (
        <div className="glass mono px-3 py-3 text-[11px] text-[var(--state-error)]">{st.error}</div>
      ) : (
        <>
          <div className="glass mb-3 px-3 py-2.5">
            <div className="hud-label mb-1.5">This node</div>
            {st?.identity ? (
              <div className="mono text-[11px] leading-relaxed text-[var(--ink)]">
                <div>{st.identity.display_name || '(unnamed)'}</div>
                <div className="text-[10px] text-[var(--ink-dim)]">{st.identity.node_id}</div>
                <div className="text-[9px] text-[var(--ink-faint)]">
                  {st.identity.algo}
                  {st.identity.public_key_hex ? ` · ${st.identity.public_key_hex.slice(0, 16)}…` : ''}
                </div>
              </div>
            ) : (
              <div className="mono text-[10px] text-[var(--ink-dim)]">
                No node identity — run <span className="text-[var(--ink)]">jarvis_prime federation identity init</span>.
              </div>
            )}
          </div>

          <div className="glass px-3 py-2.5">
            <div className="hud-label mb-1.5">Peers · {st?.peerCount ?? 0}</div>
            {st && st.peers.length > 0 ? (
              <div className="flex flex-col gap-1">
                {st.peers.map((p, i) => (
                  <div key={i} className="mono text-[10px] text-[var(--ink-dim)]">
                    {String((p as Record<string, unknown>).display_name ?? '')} · {String((p as Record<string, unknown>).node_id ?? '')}
                  </div>
                ))}
              </div>
            ) : (
              <div className="mono text-[10px] text-[var(--ink-faint)]">No peers imported yet.</div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
