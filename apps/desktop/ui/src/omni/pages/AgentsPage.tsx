import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { StatusDot } from '@/components/shell/StatusDot';
import { surfaces } from '@/adapters';
import { useLinkState } from '@/lib/health';
import type { AgentSummary } from '@/lib/types';
import { VesselHud } from '@/universe/components/VesselHud';
import { useUniverseStore } from '@/universe/store';

export default function AgentsPage() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const link = useLinkState();
  const museConnected = link === 'gateway';
  const snapshot = useUniverseStore((state) => state.snapshot);
  const selected = useUniverseStore((state) => state.selected);
  const select = useUniverseStore((state) => state.select);
  const vessels = Array.isArray(snapshot?.vessels) ? snapshot.vessels : [];
  const vessel = vessels.find((entry) => entry.id === selected) ?? vessels[0] ?? null;

  useEffect(() => {
    let alive = true;
    setLoading(true);
    Promise.allSettled(surfaces.map((s) => s.listAgents()))
      .then((results) => {
        if (!alive) return;
        setAgents(results.flatMap((result) => result.status === 'fulfilled' ? result.value : []));
        setLoadError(results.some((result) => result.status === 'rejected'));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const byKind = {
    muse: agents.filter((a) => a.surface === 'muse'),
    antigravity: agents.filter((a) => a.surface === 'antigravity'),
    aistudio: agents.filter((a) => a.surface === 'aistudio'),
  };

  return (
    <div className="px-4 pb-6">
      <div className="hud-label mb-2 mt-1">Boardable agent vessel</div>
      <VesselHud
        vessel={vessel}
        onBoard={(entry) => { select(entry.id); }}
        onCustomize={(entry) => { select(entry.id); navigate('/shipyard'); }}
      />
      {loadError && <div className="universe-error-copy mt-3" role="status">One or more agent surfaces could not be read. No unavailable agent is shown as idle or connected.</div>}

      <AgentGroup
        title="M.U.S.E. agents"
        items={byKind.muse}
        controllable
        loading={loading}
        emptyLabel={museConnected ? 'No agents reported by the gateway' : 'Requires gateway — connect M.U.S.E. to list agents'}
        onControl={() => navigate('/console')}
      />
      <AgentGroup
        title="Antigravity"
        items={byKind.antigravity}
        loading={loading}
        onOpen={() => surfaces[1].openExternal?.('antigravity-preview')}
      />
      <AgentGroup
        title="AI Studio"
        items={byKind.aistudio}
        loading={loading}
        onOpen={() => surfaces[2].openExternal?.('aistudio-chat')}
      />
    </div>
  );
}

function AgentGroup({
  title,
  items,
  controllable,
  loading,
  emptyLabel,
  onOpen,
  onControl,
}: {
  title: string;
  items: AgentSummary[];
  controllable?: boolean;
  loading?: boolean;
  emptyLabel?: string;
  onOpen?: () => void;
  onControl?: (agent: AgentSummary) => void;
}) {
  return (
    <>
      <div className="hud-label mb-2 mt-4">{title}</div>
      {loading && items.length === 0 ? (
        <div className="glass px-4 py-4 text-center text-[11px] text-[var(--ink-dim)]">
          Loading…
        </div>
      ) : items.length === 0 ? (
        <div className="glass px-4 py-4 text-center text-[11px] text-[var(--ink-dim)]">
          {emptyLabel ?? 'None connected'}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((a) => (
            <div key={a.id} className="glass flex items-center justify-between px-3 py-2.5">
              <div className="min-w-0">
                <div className="text-[13px] font-medium">{a.name}</div>
                {a.role && (
                  <div className="mono truncate text-[9px] text-[var(--ink-faint)]">{a.role}</div>
                )}
              </div>
              <div className="flex items-center gap-3">
                <StatusDot state={a.state} withLabel />
                {controllable ? (
                  <button type="button" onClick={() => onControl?.(a)} className="mono text-[10px] text-[var(--octa-glow)]">control →</button>
                ) : (
                  <button
                    onClick={onOpen}
                    className="rounded-md border border-[var(--hairline)] px-2.5 py-1 text-[10px] text-[var(--ink)]"
                  >
                    Open ↗
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
