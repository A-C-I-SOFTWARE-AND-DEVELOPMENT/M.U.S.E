import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { StatusDot } from '@/components/shell/StatusDot';
import { antigravitySurface, aiStudioSurface, museSurface } from '@/adapters';
import type { AgentRunState, AgentSummary } from '@/lib/types';

interface Tile {
  id: string;
  title: string;
  subtitle: string;
  accent: string;
  glyph: string;
  embed: boolean;
  onOpen: () => void;
}

export default function ConsolePage() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState<AgentSummary[]>([]);

  useEffect(() => {
    museSurface.listAgents().then(setAgents).catch(() => setAgents([]));
  }, []);

  const tiles: Tile[] = [
    {
      id: 'muse',
      title: 'M.U.S.E.',
      subtitle: 'Your local-first operating partner',
      accent: 'var(--acc-coding)',
      glyph: 'M',
      embed: true,
      onOpen: () => navigate('/agents'),
    },
    {
      id: 'antigravity',
      title: 'Antigravity',
      subtitle: 'antigravity-preview-05-2026 · remote agents',
      accent: 'var(--acc-reasoning)',
      glyph: '↑',
      embed: false,
      // Link-out: Antigravity refuses iframe embedding (frame-ancestors CSP).
      onOpen: () => antigravitySurface.openExternal?.('antigravity-preview'),
    },
    {
      id: 'aistudio',
      title: 'AI Studio',
      subtitle: 'aistudio.google.com · agent playground',
      accent: 'var(--acc-creativity)',
      glyph: 'A',
      embed: false,
      // Link-out: AI Studio also blocks iframe embedding.
      onOpen: () => aiStudioSurface.openExternal?.('aistudio-chat'),
    },
  ];

  return (
    <div className="px-4 pb-6">
      <div className="hud-label mb-2 mt-1">Surfaces</div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {tiles.map((t) => (
          <button
            key={t.id}
            onClick={t.onOpen}
            className="glass group relative flex flex-col items-start gap-3 px-3.5 py-3.5 text-left active:scale-[0.99]"
          >
            <div className="flex w-full items-start justify-between">
              <div
                className="grid h-10 w-10 place-items-center rounded-[10px] text-[18px] font-bold text-black"
                style={{ background: t.accent, boxShadow: `0 0 16px ${t.accent}55` }}
              >
                {t.glyph}
              </div>
              <span
                className="mono rounded-full border border-[var(--hairline)] px-2 py-0.5 text-[9px] uppercase tracking-wider text-[var(--ink-dim)]"
              >
                {t.embed ? 'Embedded' : 'Link-out ↗'}
              </span>
            </div>
            <div>
              <div className="text-[15px] font-semibold">{t.title}</div>
              <div className="mt-0.5 text-[11px] leading-snug text-[var(--ink-dim)]">
                {t.subtitle}
              </div>
            </div>
            <StatusDot state={t.embed ? 'idle' : 'unknown'} withLabel />
          </button>
        ))}
      </div>

      {/* M.U.S.E. AOS Council roster */}
      <div className="hud-label mb-2 mt-5">M.U.S.E. roster</div>
      {agents.length === 0 ? (
        <div className="glass px-4 py-6 text-center">
          <div className="text-[12px] text-[var(--ink-dim)]">No M.U.S.E. agents connected</div>
          <div className="mt-1 text-[10px] text-[var(--ink-faint)]">
            Set VITE_MUSE_BASE_URL to your gateway to load the AOS Council.
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
          {agents.map((a) => (
            <button
              key={a.id}
              onClick={() => navigate(`/agents?id=${a.id}`)}
              className="glass flex items-center justify-between px-3 py-2.5 text-left"
            >
              <div className="min-w-0">
                <div className="truncate text-[12px] font-medium">{a.name}</div>
                {a.role && (
                  <div className="mono truncate text-[9px] text-[var(--ink-faint)]">{a.role}</div>
                )}
              </div>
              <StatusDot state={(a.state ?? 'unknown') as AgentRunState} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
