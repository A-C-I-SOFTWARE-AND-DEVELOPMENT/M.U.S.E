import { NavLink } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState, type ReactNode } from 'react';

// Full navigation — every destination the app has, so the web app exposes
// the whole MUSE surface on BOTH desktop and mobile, not just the 7 quick tabs.
// Desktop: a persistent left rail (the "PC version"). Mobile: the same list as a
// slide-over drawer opened from the TopBar hamburger, so the phone reaches
// everything the PC does. The bottom TabBar remains for one-tap mobile access.

const I = (p: ReactNode) => (
  <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    {p}
  </svg>
);

interface Dest { to: string; label: string; icon: ReactNode }
interface Group { heading: string; items: Dest[] }

const GROUPS: Group[] = [
  {
    heading: 'Command',
    items: [
      { to: '/atlas', label: 'Atlas Crown', icon: I(<><circle cx="12" cy="12" r="3" /><ellipse cx="12" cy="12" rx="9" ry="5" /><path d="M12 3v18M3 12h18" /></>) },
      { to: '/stations', label: 'Stations', icon: I(<><circle cx="12" cy="12" r="2" /><circle cx="12" cy="12" r="7" /><path d="M12 2v3M22 12h-3M12 22v-3M2 12h3" /></>) },
      { to: '/', label: 'Chat', icon: I(<path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.7A8.5 8.5 0 1 1 21 11.5z" />) },
      { to: '/console', label: 'Console', icon: I(<><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>) },
      { to: '/fusion', label: 'Fusion', icon: I(<><circle cx="5" cy="6" r="2" /><circle cx="5" cy="18" r="2" /><circle cx="19" cy="12" r="2.4" /><path d="M7 6.5l10 4.5M7 17.5l10-4.5" /></>) },
      { to: '/jobs', label: 'Jobs', icon: I(<path d="M4 6h16M4 12h10M4 18h14M16 10l4 2-4 2" />) },
      { to: '/approvals', label: 'Approvals', icon: I(<><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></>) },
      { to: '/autonomy', label: 'Autonomy', icon: I(<><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2.2 2.2M16.8 16.8L19 19M19 5l-2.2 2.2M7.2 16.8L5 19" /></>) },
      { to: '/axiom', label: 'Axiom Gate', icon: I(<><path d="M12 3l8 5v8l-8 5-8-5V8z" /><path d="M12 8l4 2.5v0L12 13l-4-2.5z" /></>) },
      { to: '/steer', label: 'Steer', icon: I(<><polygon points="12,2 19,6 19,14 12,18 5,14 5,6" /><circle cx="12" cy="10" r="2.4" /></>) },
    ],
  },
  {
    heading: 'Build',
    items: [
      { to: '/shipyard', label: 'Shipyard', icon: I(<><path d="M4 17h16M6 17l2-9h8l2 9M9 8V5h6v3" /><circle cx="12" cy="13" r="2" /></>) },
      { to: '/forge', label: 'Forge', icon: I(<><path d="M14 7l6 6M3 21l4-1 11-11-3-3L4 17z" /></>) },
      { to: '/fleet', label: 'Fleet', icon: I(<><circle cx="6" cy="7" r="2.5" /><circle cx="18" cy="7" r="2.5" /><circle cx="12" cy="17" r="2.5" /><path d="M6 9.5v3l6 2 6-2v-3" /></>) },
      { to: '/agents', label: 'Agents', icon: I(<><circle cx="12" cy="8" r="3.2" /><path d="M4 20a8 8 0 0 1 16 0" /></>) },
      { to: '/studio', label: 'Studio', icon: I(<><path d="M3 9l9-6 9 6v10l-9 4-9-4z" /><path d="M12 3v20M3 9l9 4 9-4" /></>) },
      { to: '/fabrication', label: 'Fabrication', icon: I(<><path d="M5 4h14v16H5zM8 8h8M8 12h5M8 16h7" /></>) },
      { to: '/game-foundry', label: 'Game Foundry', icon: I(<><path d="M7 8h10l3 9-3 2-3-3h-4l-3 3-3-2z" /><path d="M8 12h4M10 10v4M16 12h.01" /></>) },
      { to: '/cinema', label: 'Cinema Stage', icon: I(<><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M8 5l3 5M14 5l3 5M3 10h18" /></>) },
      { to: '/release', label: 'Release Dock', icon: I(<><path d="M12 3v12M8 7l4-4 4 4M5 14v6h14v-6" /></>) },
      { to: '/repo', label: 'Repo', icon: I(<><path d="M6 3v12M6 15a3 3 0 0 0 3 3h6M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 6a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" /></>) },
    ],
  },
  {
    heading: 'Intelligence',
    items: [
      { to: '/models', label: 'Models', icon: I(<><rect x="3" y="4" width="18" height="4" rx="1" /><rect x="3" y="10" width="18" height="4" rx="1" /><rect x="3" y="16" width="12" height="4" rx="1" /></>) },
      { to: '/second-brain', label: 'Second Brain', icon: I(<><path d="M9 3a4 4 0 0 0-4 4 4 4 0 0 0-1 7 3.5 3.5 0 0 0 3 5h2V3zM15 3a4 4 0 0 1 4 4 4 4 0 0 1 1 7 3.5 3.5 0 0 1-3 5h-2V3z" /></>) },
      { to: '/observatory', label: 'Observatory', icon: I(<><circle cx="12" cy="12" r="2.4" /><ellipse cx="12" cy="12" rx="9" ry="3.6" /><ellipse cx="12" cy="12" rx="9" ry="3.6" transform="rotate(60 12 12)" /></>) },
      { to: '/championship', label: 'Championship', icon: I(<><path d="M7 4h10v4a5 5 0 0 1-10 0zM5 4h2v2a2 2 0 0 1-2 2zM19 4h-2v2a2 2 0 0 0 2 2zM9 13h6l-1 4h-4z" /></>) },
    ],
  },
  {
    heading: 'Governance',
    items: [
      { to: '/civilizations', label: 'Civilizations', icon: I(<><circle cx="8" cy="9" r="3" /><circle cx="17" cy="7" r="2" /><path d="M3 20a5 5 0 0 1 10 0M14 20a4 4 0 0 1 7-2" /></>) },
      { to: '/council', label: 'Council', icon: I(<><circle cx="7" cy="9" r="2" /><circle cx="17" cy="9" r="2" /><circle cx="12" cy="7" r="2.2" /><path d="M3 19a4 4 0 0 1 8 0M13 19a4 4 0 0 1 8 0" /></>) },
      { to: '/federation', label: 'Federation', icon: I(<><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" /></>) },
    ],
  },
  {
    heading: 'Systems',
    items: [
      { to: '/activity', label: 'Activity', icon: I(<path d="M3 12h4l3 8 4-16 3 8h4" />) },
      { to: '/share', label: 'Share', icon: I(<><circle cx="18" cy="5" r="2.5" /><circle cx="6" cy="12" r="2.5" /><circle cx="18" cy="19" r="2.5" /><path d="M8.2 10.8l7.6-4.6M8.2 13.2l7.6 4.6" /></>) },
      { to: '/settings', label: 'Settings', icon: I(<><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" /></>) },
    ],
  },
];

// Tonal hover for nav items: lift the void tone on hover/focus (never a glow).
// The active wash + ring-grad marker are rendered inline per item below; this
// only covers the non-active hover lift so the whole rail reads as one system.
const NAV_CSS = `
.nexus-nav-item:hover { background: var(--void-2); }
.nexus-nav-item:hover .nexus-nav-icon { color: var(--signal); }
@media (prefers-reduced-motion: reduce) { .nexus-nav-item { transition: none; } }
`;

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-4 px-2 py-4">
      <style>{NAV_CSS}</style>
      {GROUPS.map((g) => (
        <div key={g.heading} className="flex flex-col gap-0.5">
          <div className="hud-label px-3 pb-1 text-[10px]" style={{ color: 'var(--ink-faint)' }}>
            {g.heading}
          </div>
          {g.items.map((d) => (
            <NavLink
              key={d.to}
              to={d.to}
              end={d.to === '/'}
              onClick={onNavigate}
              className="nexus-nav-item group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[13px]"
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <>
                      {/* Active spectral WASH — a matte cyan→violet gradient that
                          fades to nothing (never a glow), exactly the cockpit's
                          active nav fill. Animated between items via layoutId. */}
                      <motion.span
                        layoutId="rail-active-wash"
                        className="absolute inset-0 -z-0 rounded-lg"
                        style={{
                          background:
                            'linear-gradient(90deg, rgba(122,224,255,0.12) 0%, rgba(179,136,255,0.05) 60%, rgba(179,136,255,0) 100%)',
                        }}
                        transition={{ type: 'spring', stiffness: 480, damping: 36 }}
                      />
                      {/* Thin ring-grad accent MARKER — a 3px cyan→violet bar pinned
                          to the left edge. Matte: no glow, round caps. */}
                      <motion.span
                        layoutId="rail-active-marker"
                        className="absolute left-0 top-1/2 -z-0 -translate-y-1/2 rounded-full"
                        style={{ width: 3, height: 18, background: 'var(--ring-grad)' }}
                        transition={{ type: 'spring', stiffness: 480, damping: 36 }}
                      />
                    </>
                  )}
                  <span className="nexus-nav-icon z-10 shrink-0" style={{ color: isActive ? 'var(--signal)' : 'var(--ink-faint)' }}>
                    {d.icon}
                  </span>
                  <span className="z-10 font-medium" style={{ color: isActive ? 'var(--ink)' : 'var(--ink-dim)' }}>
                    {d.label}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  );
}

export function SideNav() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const o = () => setOpen(true);
    window.addEventListener('nexus:open-nav', o);
    return () => window.removeEventListener('nexus:open-nav', o);
  }, []);

  return (
    <>
      {/* Desktop: persistent rail — the full "PC version" navigation. */}
      <aside
        className="scroll-area hidden w-60 shrink-0 overflow-y-auto border-r border-[var(--hairline)] md:block"
        style={{ background: 'rgba(10,14,20,0.50)' }}
      >
        <NavList />
      </aside>

      {/* Mobile: the same full nav as a slide-over drawer (TopBar hamburger). */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              className="fixed inset-0 z-40 md:hidden"
              style={{ background: 'rgba(0,0,0,0.55)' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.aside
              className="scroll-area fixed inset-y-0 left-0 z-50 w-72 overflow-y-auto border-r border-[var(--hairline)] backdrop-blur-xl md:hidden"
              style={{ background: 'rgba(10,14,20,0.96)', paddingTop: 'env(safe-area-inset-top)' }}
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 420, damping: 40 }}
            >
              <NavList onNavigate={() => setOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
