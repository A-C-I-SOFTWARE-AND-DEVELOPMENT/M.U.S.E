import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchForgeLeaderboard, type ForgeLeaderboard } from '@/lib/forgeArena';
import { useLinkState } from '@/lib/health';

/** The tournament/championship Forge (Glicko-2 + MAP-Elites) — distinct from the
 *  per-agent-knowledge "Forge" tab. Read-only standings over the gateway. */
export default function ChampionshipPage() {
  const navigate = useNavigate();
  const [lb, setLb] = useState<ForgeLeaderboard | null>(null);
  const [loading, setLoading] = useState(false);
  const connected = useLinkState() === 'gateway';

  useEffect(() => {
    if (!connected) return;
    setLoading(true);
    fetchForgeLeaderboard()
      .then(setLb)
      .finally(() => setLoading(false));
  }, [connected]);

  const stat = (label: string, value: string | number) => (
    <div className="glass flex-1 px-3 py-2 text-center">
      <div className="mono text-[15px] font-semibold text-[var(--ink)]">{value}</div>
      <div className="mono text-[9px] text-[var(--ink-faint)]">{label}</div>
    </div>
  );

  return (
    <div className="px-4 pb-6">
      <div className="glass mb-3 px-3 py-2.5">
        <div className="text-[13px] font-semibold">Championship</div>
        <div className="mono text-[10px] text-[var(--ink-dim)]">
          Forge tournament — Glicko-2 ratings + MAP-Elites quality-diversity.
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
      ) : !lb && loading ? (
        <div className="glass mono px-3 py-6 text-center text-[11px] text-[var(--ink-dim)]">Loading standings…</div>
      ) : lb?.error ? (
        <div className="glass mono px-3 py-3 text-[11px] text-[var(--state-error)]">{lb.error}</div>
      ) : !lb ? (
        <div className="glass mono px-3 py-6 text-center text-[11px] text-[var(--ink-dim)]">No standings available.</div>
      ) : (
        <>
          <div className="mb-3 flex gap-2">
            {stat('candidates', lb.candidates)}
            {stat('coverage', `${Math.round(lb.coverage * 100)}%`)}
            {stat('QD score', lb.qdScore.toFixed(2))}
          </div>
          {lb.standings.length > 0 ? (
            <div className="flex flex-col gap-1.5">
              {lb.standings.map((s, i) => (
                <div key={i} className="glass flex items-center justify-between px-3 py-2">
                  <span className="mono text-[11px] text-[var(--ink)]">
                    #{i + 1} {String((s as Record<string, unknown>).candidate_id ?? (s as Record<string, unknown>).contributor_id ?? '')}
                  </span>
                  <span className="mono text-[10px] text-[var(--ink-dim)]">
                    {String((s as Record<string, unknown>).rating ?? (s as Record<string, unknown>).score ?? '')}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="glass mono px-3 py-6 text-center text-[11px] text-[var(--ink-dim)]">
              No competitors yet — run <span className="text-[var(--ink)]">jarvis_prime forge tournament</span> to populate the board.
            </div>
          )}
        </>
      )}
    </div>
  );
}
