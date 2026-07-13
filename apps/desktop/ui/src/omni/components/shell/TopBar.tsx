import { useLocation, Link } from 'react-router-dom';
import { useLinkState } from '@/lib/health';
import { Dot } from './StatusDot';
import { useUniverseStore, type UniverseConnection } from '@/universe/store';

const TITLES: Record<string, string> = {
  '/': 'NEURAL CONVERSATION',
  '/chat': 'NEURAL CONVERSATION',
  '/console': 'MISSION CONTROL',
  '/fusion': 'FUSION CHAMBER',
  '/steer': 'AGENT OPTIMIZATION CONTROL',
  '/axiom': 'AXIOM GATE · FUSION',
  '/forge': 'CREATION FORGE',
  '/fleet': 'AGENT FLEET',
  '/agents': 'AGENT WORKSHOP',
  '/council': 'COUNCIL CHAMBER',
  '/studio': 'AAA STUDIO',
  '/repo': 'REPOSITORY MATRIX',
  '/models': 'MODEL ARSENAL',
  '/second-brain': 'SECOND BRAIN',
  '/observatory': 'NEURAL OBSERVATORY',
  '/championship': 'CHAMPIONSHIP ARENA',
  '/federation': 'FEDERATION',
  '/activity': 'ACTIVITY PULSE',
  '/share': 'SIGNAL BROADCAST',
  '/settings': 'SYSTEM CORE',
  '/atlas': 'ATLAS CROWN · NEURAL CORE',
  '/stations': 'CELESTIAL STATION NETWORK',
  '/shipyard': 'NEURAL SHIPYARD',
  '/civilizations': 'RELAY EMBASSY · CIVILIZATIONS',
  '/fabrication': 'LIVE SOURCE FABRICATION',
  '/game-foundry': 'AAA GAME FOUNDRY',
  '/cinema': 'NATIVE-STEREO CINEMA STAGE',
  '/release': 'VERIFIED RELEASE DOCK',
};

// Live-link → cockpit status pill. The pill is a tonal chip (never a bloom); its
// dot carries the only colour signal, mapped onto the Singularity dot states.
// `gateway` and `online` both read as live (cyan pulse); `connecting` is a warn
// amber; `offline` is a muted off dot. Labels stay honest — no fabricated state.
const LINK_META = {
  gateway: { dot: 'live', label: 'Gateway' },
  online: { dot: 'live', label: 'Online' },
  connecting: { dot: 'warn', label: 'Connecting' },
  offline: { dot: 'off', label: 'Offline' },
} as const;

const UNIVERSE_META: Record<UniverseConnection, { dot: 'ok' | 'warn' | 'danger' | 'live' | 'off'; label: string }> = {
  idle: { dot: 'off', label: 'Atlas idle' },
  loading: { dot: 'warn', label: 'Atlas loading' },
  online: { dot: 'live', label: 'Atlas live' },
  empty: { dot: 'ok', label: 'Atlas empty' },
  offline: { dot: 'off', label: 'Atlas stale' },
  denied: { dot: 'warn', label: 'Atlas denied' },
  conflict: { dot: 'warn', label: 'Atlas conflict' },
  degraded: { dot: 'warn', label: 'Atlas degraded' },
  error: { dot: 'danger', label: 'Atlas error' },
};

// The brand glyph: a WHITE CORE that blooms via stacked cool-white radial halos
// behind a thin MATTE spectral ring (cyan #7ae0ff → violet #b388ff). The bloom
// is sized to the core only (the matte ring is never glowed). The ring SVG spins
// slowly in the live header; the spin is disabled under prefers-reduced-motion
// via the scoped style block below.
const GLYPH_CSS = `
@keyframes nexus-glyph-spin { to { transform: rotate(360deg); } }
.nexus-glyph-ring { transform-origin: 50% 50%; animation: nexus-glyph-spin 8.5s linear infinite; }
@media (prefers-reduced-motion: reduce) { .nexus-glyph-ring { animation: none; } }
`;

function BrandGlyph() {
  return (
    <span className="relative grid place-items-center" style={{ lineHeight: 0 }}>
      <style>{GLYPH_CSS}</style>
      {/* Volumetric core bloom — four cool-white radial halos, tight bright
          centre → wide faint edge. Lives BEHIND the svg, sized to the core, so
          the matte ring is never bloomed. Deterministic, no filters. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute rounded-full"
        style={{
          inset: -12,
          background: [
            'radial-gradient(circle at 50% 50%, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0) 9%)',
            'radial-gradient(circle at 50% 50%, rgba(242,251,255,0.55) 0%, rgba(242,251,255,0) 16%)',
            'radial-gradient(circle at 50% 50%, rgba(224,248,255,0.30) 0%, rgba(224,248,255,0) 30%)',
            'radial-gradient(circle at 50% 50%, rgba(212,242,255,0.16) 0%, rgba(212,242,255,0) 52%)',
          ].join(','),
        }}
      />
      <svg viewBox="0 0 48 48" width="28" height="28" aria-label="muse" style={{ position: 'relative', zIndex: 1 }}>
        <defs>
          <linearGradient id="nexus-hdr-ring" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#7ae0ff" />
            <stop offset="1" stopColor="#b388ff" />
          </linearGradient>
        </defs>
        {/* The matte spectral ring — a thin arc, round line caps, slowly spinning. */}
        <g className="nexus-glyph-ring" transform="rotate(-32 24 24)">
          <circle
            cx="24"
            cy="24"
            r="15"
            fill="none"
            stroke="url(#nexus-hdr-ring)"
            strokeWidth="1.6"
            strokeDasharray="66 28"
            strokeLinecap="round"
          />
        </g>
        {/* The single white core. */}
        <circle cx="24" cy="24" r="3.1" fill="#ffffff" />
      </svg>
    </span>
  );
}

export function TopBar() {
  const { pathname } = useLocation();
  const title = TITLES[pathname] ?? (pathname.startsWith('/stations/') ? 'CELESTIAL STATION INTERIOR' : 'Multi-Use Synaptic Entity');
  const link = useLinkState();
  const meta = LINK_META[link];
  const universe = useUniverseStore((state) => state.connection);
  const universeMeta = UNIVERSE_META[universe];
  return (
    <header
      className="flex items-center justify-between px-4 backdrop-blur-xl"
      style={{
        paddingTop: 'calc(env(safe-area-inset-top) + 10px)',
        paddingBottom: 10,
        // Floating glass app bar: a soft top-down scrim so the lockup and status
        // read cleanly over the cinematic depth pool, closed by a hairline.
        background:
          'linear-gradient(180deg, rgba(8,11,16,0.78) 0%, rgba(8,11,16,0.42) 70%, transparent 100%)',
        borderBottom: '1px solid var(--hairline)',
      }}
    >
      <div className="flex items-center gap-2.5">
        <button
          onClick={() => window.dispatchEvent(new CustomEvent('nexus:open-nav'))}
          aria-label="Open navigation"
          className="grid h-7 w-7 place-items-center rounded-md border border-[var(--hairline)] text-[var(--ink-dim)] md:hidden"
        >
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M3 6h18M3 12h18M3 18h18" /></svg>
        </button>
        {/* Brand lockup: white-core glyph + muse wordmark + expansion subtitle. */}
        <div className="flex min-w-0 items-center gap-2.5">
          <BrandGlyph />
          <div className="flex min-w-0 items-baseline gap-2">
            <span
              className="cinematic-title text-[18px] font-semibold leading-none"
              style={{ color: 'var(--core)', letterSpacing: '0.5px' }}
            >
              muse
            </span>
            <span
              className="hidden truncate text-[10px] uppercase leading-none sm:inline"
              style={{ color: 'var(--signal-mute)', letterSpacing: '0.4px' }}
            >
              {title}
            </span>
          </div>
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
      {/* Live status pill — tonal chip; the dot carries the colour signal. */}
      <span
        className="hud-label inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-[10px]"
        style={{ background: 'var(--void-2)', border: '1px solid var(--edge)', color: 'var(--signal-dim)' }}
      >
        <Dot state={meta.dot} />
        {meta.label}
      </span>
      <span
        className="hud-label hidden items-center gap-1.5 rounded-full px-2 py-1 text-[10px] sm:inline-flex"
        style={{ background: 'var(--void-2)', border: '1px solid var(--edge)', color: 'var(--signal-dim)' }}
      >
        <Dot state={universeMeta.dot} />
        {universeMeta.label}
      </span>
      </div>
    </header>
  );
}
