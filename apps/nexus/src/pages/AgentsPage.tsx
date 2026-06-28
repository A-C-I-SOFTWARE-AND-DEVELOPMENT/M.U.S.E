import { useEffect, useState } from 'react';
import { StatusDot } from '@/components/shell/StatusDot';
import { surfaces } from '@/adapters';
import { museBase } from '@/lib/config';
import type { AgentSummary } from '@/lib/types';

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [embedUrl, setEmbedUrl] = useState<string | null>(null);
  const museConnected = !!museBase();

  useEffect(() => {
    let alive = true;
    setLoading(true);
    Promise.all(surfaces.map((s) => s.listAgents().catch(() => [])))
      .then((lists) => {
        if (alive) setAgents(lists.flat());
      })
      .catch(() => {
        if (alive) setAgents([]);
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
      {/* M.U.S.E. embedded panel — user controls the CSP, so it embeds in-app. */}
      <div className="hud-label mb-2 mt-1">M.U.S.E. · embedded</div>
      <div className="glass overflow-hidden">
        {embedUrl ? (
          <iframe
            title="M.U.S.E."
            src={embedUrl}
            className="h-[320px] w-full border-0 bg-black"
          />
        ) : (
          <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
            <div className="text-[12px] text-[var(--ink-dim)]">
              M.U.S.E. gateway panel (embeddable — CSP owned by you)
            </div>
            <button
              onClick={() =>
                setEmbedUrl((import.meta.env.VITE_MUSE_BASE_URL ?? '') || null)
              }
              className="rounded-md px-3 py-1.5 text-[11px] font-semibold text-black"
              style={{ background: 'var(--octa-glow)' }}
            >
              Load gateway
            </button>
            <div className="text-[10px] text-[var(--ink-faint)]">
              Requires VITE_MUSE_BASE_URL.
            </div>
          </div>
        )}
      </div>

      <AgentGroup
        title="M.U.S.E. agents"
        items={byKind.muse}
        controllable
        loading={loading}
        emptyLabel={museConnected ? 'No agents reported by the gateway' : 'Requires gateway — connect M.U.S.E. to list agents'}
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
}: {
  title: string;
  items: AgentSummary[];
  controllable?: boolean;
  loading?: boolean;
  emptyLabel?: string;
  onOpen?: () => void;
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
                  <span className="mono text-[10px] text-[var(--octa-glow)]">control →</span>
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
