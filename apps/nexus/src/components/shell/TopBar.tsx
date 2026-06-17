import { useLocation, Link } from 'react-router-dom';
import { useLinkState } from '@/lib/health';

const TITLES: Record<string, string> = {
  '/': 'CONSOLE',
  '/steer': 'AGENT OPTIMIZATION CONTROL',
  '/axiom': 'AXIOM GATE · FUSION',
  '/observatory': 'NEURAL OBSERVATORY',
  '/agents': 'AGENTS',
  '/activity': 'ACTIVITY',
  '/settings': 'SETTINGS',
};

const LINK_META = {
  gateway: { color: 'var(--state-running)', label: 'GATEWAY' },
  online: { color: 'var(--octa-glow)', label: 'ONLINE' },
  connecting: { color: 'var(--state-auth)', label: 'SYNC' },
  offline: { color: 'var(--ink-faint)', label: 'OFFLINE' },
} as const;

export function TopBar() {
  const { pathname } = useLocation();
  const link = useLinkState();
  const meta = LINK_META[link];
  return (
    <header
      className="flex items-center justify-between px-4"
      style={{ paddingTop: 'calc(env(safe-area-inset-top) + 10px)', paddingBottom: 10 }}
    >
      <div className="flex items-center gap-2.5">
        <div
          className="grid h-7 w-7 place-items-center rounded-md"
          style={{
            background: 'linear-gradient(135deg, var(--acc-coding), var(--acc-creativity))',
            boxShadow: '0 0 14px rgba(52,229,200,0.4)',
          }}
        >
          <span className="text-[13px] font-bold text-black">N</span>
        </div>
        <div className="leading-none">
          <div className="text-[15px] font-bold tracking-wide">NEXUS</div>
          <div className="hud-label mt-0.5">{TITLES[pathname] ?? ''}</div>
        </div>
      </div>
      <div className="flex items-center gap-2.5">
      <Link
        to="/chat"
        aria-label="Open chat"
        className="grid h-6 w-6 place-items-center rounded-md border border-[var(--hairline)] text-[var(--ink-dim)]"
      >
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.7A8.5 8.5 0 1 1 21 11.5z" /></svg>
      </Link>
      <button
        onClick={() => window.dispatchEvent(new CustomEvent('nexus:open-palette'))}
        aria-label="Open command palette"
        className="grid h-6 w-6 place-items-center rounded-md border border-[var(--hairline)] text-[var(--ink-dim)]"
      >
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
      </button>
      <div className="mono flex items-center gap-1.5 text-[10px]" style={{ color: meta.color }}>
        <span
          className="inline-block h-1.5 w-1.5 rounded-full"
          style={{
            background: meta.color,
            boxShadow: link === 'online' || link === 'gateway' ? `0 0 8px ${meta.color}` : undefined,
            animation: link === 'connecting' ? 'octa-pulse 1.2s ease-in-out infinite' : undefined,
          }}
        />
        {meta.label}
      </div>
      </div>
    </header>
  );
}
