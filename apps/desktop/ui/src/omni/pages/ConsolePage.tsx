import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { StatusDot } from '@/components/shell/StatusDot';
import { CapabilityDrawer } from '@/components/muse/CapabilityDrawer';
import { antigravitySurface, aiStudioSurface, museSurface } from '@/adapters';
import { cockpit, type RuntimeStatus } from '@/adapters/cockpit';
import { CAPABILITIES, PLANES, type Capability } from '@/lib/capabilities';
import { useLinkState } from '@/lib/health';
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
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState<Capability | null>(null);
  const gatewayConnected = useLinkState() === 'gateway';

  useEffect(() => {
    museSurface.listAgents().then(setAgents).catch(() => setAgents([]));
    if (gatewayConnected) {
      cockpit.runtimeStatus().then((r) => setRuntime(r as RuntimeStatus | null));
    } else {
      setRuntime(null);
    }
  }, [gatewayConnected]);

  const tiles: Tile[] = [
    { id: 'muse', title: 'M.U.S.E.', subtitle: 'Your local-first operating partner', accent: 'var(--acc-coding)', glyph: 'M', embed: true, onOpen: () => navigate('/agents') },
    { id: 'antigravity', title: 'Antigravity', subtitle: 'antigravity-preview-05-2026 · remote agents', accent: 'var(--acc-reasoning)', glyph: '↑', embed: false, onOpen: () => antigravitySurface.openExternal?.('antigravity-preview') },
    { id: 'aistudio', title: 'AI Studio', subtitle: 'aistudio.google.com · agent playground', accent: 'var(--acc-creativity)', glyph: 'A', embed: false, onOpen: () => aiStudioSurface.openExternal?.('aistudio-chat') },
  ];

  const open = (c: Capability) => {
    if (c.surface.kind === 'tab') navigate(c.surface.to);
    else if (c.surface.kind === 'external') window.open(c.surface.href, '_blank', 'noopener,noreferrer');
    else setActive(c);
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return CAPABILITIES;
    return CAPABILITIES.filter((c) => (c.title + ' ' + c.blurb).toLowerCase().includes(q));
  }, [query]);

  return (
    <div className="px-4 pb-6">
      {/* Runtime + emergency banner */}
      <div className="glass mb-3 flex items-center justify-between px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: gatewayConnected && runtime?.state === 'running' ? 'var(--state-running)' : 'var(--ink-faint)' }} />
          <div>
            <div className="text-[12px] font-semibold">MUSE runtime</div>
            <div className="mono text-[9px] text-[var(--ink-dim)]">
              {gatewayConnected ? (runtime?.state ?? 'status not reported') : 'gateway not connected'}
              {runtime?.workers != null ? ` · ${runtime.workers} workers` : ''}
            </div>
          </div>
        </div>
        <button
          onClick={() => setActive(CAPABILITIES.find((c) => c.id === 'emergency')!)}
          disabled={!gatewayConnected}
          className="rounded-md px-3 py-1.5 text-[11px] font-bold text-white disabled:cursor-not-allowed disabled:opacity-40"
          style={{ background: 'var(--state-error)' }}
        >
          ⏹ Stop
        </button>
      </div>

      {/* Surfaces */}
      <div className="hud-label mb-2">Surfaces</div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {tiles.map((t) => (
          <button key={t.id} onClick={t.onOpen} className="glass group relative flex flex-col items-start gap-3 px-3.5 py-3.5 text-left active:scale-[0.99]">
            <div className="flex w-full items-start justify-between">
              <div className="grid h-10 w-10 place-items-center rounded-[10px] text-[18px] font-bold text-black" style={{ background: t.accent, boxShadow: `0 0 16px ${t.accent}55` }}>{t.glyph}</div>
              <span className="mono rounded-full border border-[var(--hairline)] px-2 py-0.5 text-[9px] uppercase tracking-wider text-[var(--ink-dim)]">{t.embed ? 'Embedded' : 'Link-out ↗'}</span>
            </div>
            <div>
              <div className="text-[15px] font-semibold">{t.title}</div>
              <div className="mt-0.5 text-[11px] leading-snug text-[var(--ink-dim)]">{t.subtitle}</div>
            </div>
            <StatusDot state={t.embed ? 'idle' : 'unknown'} withLabel />
          </button>
        ))}
      </div>

      {/* Capability map — every MUSE README capability, accessible */}
      <div className="mb-2 mt-5 flex items-center justify-between">
        <div className="hud-label">MUSE capabilities · {CAPABILITIES.length}</div>
      </div>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search capabilities…"
        className="mb-3 w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-3 py-2 text-[12px] text-[var(--ink)]"
      />

      {PLANES.map((plane) => {
        const caps = filtered.filter((c) => c.plane === plane.key);
        if (caps.length === 0) return null;
        return (
          <div key={plane.key} className="mb-4">
            <div className="mb-1.5 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ background: plane.accent }} />
              <span className="hud-label" style={{ color: plane.accent }}>{plane.label}</span>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {caps.map((c) => (
                <button key={c.id} onClick={() => open(c)} className="glass flex flex-col items-start gap-1 px-3 py-2.5 text-left active:scale-[0.99]">
                  <div className="flex w-full items-center justify-between">
                    <span className="text-[12px] font-semibold">{c.title}</span>
                    <span className="mono text-[12px] text-[var(--ink-faint)]">
                      {c.surface.kind === 'tab' ? '→' : c.surface.kind === 'external' ? '↗' : '⌅'}
                    </span>
                  </div>
                  <span className="text-[10px] leading-snug text-[var(--ink-dim)]">{c.blurb}</span>
                </button>
              ))}
            </div>
          </div>
        );
      })}

      {/* M.U.S.E. roster */}
      <div className="hud-label mb-2 mt-3">M.U.S.E. roster</div>
      {agents.length === 0 ? (
        <div className="glass px-4 py-5 text-center">
          <div className="text-[12px] text-[var(--ink-dim)]">No M.U.S.E. agents connected</div>
          <div className="mt-1 text-[10px] text-[var(--ink-faint)]">Set VITE_MUSE_BASE_URL to load the AOS Council.</div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
          {agents.map((a) => (
            <button key={a.id} onClick={() => navigate(`/agents?id=${a.id}`)} className="glass flex items-center justify-between px-3 py-2.5 text-left">
              <div className="min-w-0">
                <div className="truncate text-[12px] font-medium">{a.name}</div>
                {a.role && <div className="mono truncate text-[9px] text-[var(--ink-faint)]">{a.role}</div>}
              </div>
              <StatusDot state={(a.state ?? 'unknown') as AgentRunState} />
            </button>
          ))}
        </div>
      )}

      <CapabilityDrawer capability={active} onClose={() => setActive(null)} />
    </div>
  );
}
