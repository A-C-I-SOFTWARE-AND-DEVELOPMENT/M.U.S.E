import { useLocation } from 'react-router-dom';

const TITLES: Record<string, string> = {
  '/': 'CONSOLE',
  '/steer': 'AGENT OPTIMIZATION CONTROL',
  '/agents': 'AGENTS',
  '/activity': 'ACTIVITY',
  '/settings': 'SETTINGS',
};

export function TopBar() {
  const { pathname } = useLocation();
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
      <div className="mono text-[10px] text-[var(--ink-dim)]">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--state-running)]" />{' '}
        LINK
      </div>
    </header>
  );
}
