import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

interface Tab {
  to: string;
  label: string;
  icon: ReactNode;
}

const I = (path: ReactNode) => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    {path}
  </svg>
);

const TABS: Tab[] = [
  { to: '/', label: 'Chat', icon: I(<path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.7A8.5 8.5 0 1 1 21 11.5z" />) },
  { to: '/console', label: 'Console', icon: I(<><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>) },
  { to: '/fusion', label: 'Fusion', icon: I(<><circle cx="5" cy="6" r="2" /><circle cx="5" cy="18" r="2" /><circle cx="19" cy="12" r="2.4" /><path d="M7 6.5l10 4.5M7 17.5l10-4.5" /></>) },
  { to: '/steer', label: 'Steer', icon: I(<><polygon points="12,2 19,6 19,14 12,18 5,14 5,6" /><circle cx="12" cy="10" r="2.4" /></>) },
  { to: '/axiom', label: 'Axiom', icon: I(<><path d="M12 3l8 5v8l-8 5-8-5V8z" /><path d="M12 8l4 2.5v0L12 13l-4-2.5z" /></>) },
  { to: '/observatory', label: 'Observ.', icon: I(<><circle cx="12" cy="12" r="2.4" /><ellipse cx="12" cy="12" rx="9" ry="3.6" /><ellipse cx="12" cy="12" rx="9" ry="3.6" transform="rotate(60 12 12)" /></>) },
  { to: '/models', label: 'Models', icon: I(<><rect x="3" y="4" width="18" height="4" rx="1" /><rect x="3" y="10" width="18" height="4" rx="1" /><rect x="3" y="16" width="12" height="4" rx="1" /></>) },
  { to: '/settings', label: 'Settings', icon: I(<><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" /></>) },
];

export function TabBar() {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 flex items-stretch justify-around border-t border-[var(--hairline)] bg-[rgba(10,14,20,0.86)] backdrop-blur-xl md:hidden"
      style={{
        height: 'calc(var(--tab-h) + env(safe-area-inset-bottom))',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
    >
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.to === '/'}
          className="group relative flex flex-1 flex-col items-center justify-center gap-1"
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <>
                  {/* Active spectral WASH — matte cyan→violet fill, never a glow. */}
                  <motion.span
                    layoutId="tab-active"
                    className="absolute inset-x-2 top-1.5 -z-0 rounded-xl"
                    style={{
                      height: 'calc(100% - 12px)',
                      background:
                        'linear-gradient(180deg, rgba(122,224,255,0.12) 0%, rgba(179,136,255,0.05) 70%, rgba(179,136,255,0) 100%)',
                    }}
                    transition={{ type: 'spring', stiffness: 480, damping: 36 }}
                  />
                  {/* Thin ring-grad accent MARKER — a top cyan→violet bar, round caps. */}
                  <motion.span
                    layoutId="tab-active-marker"
                    className="absolute top-0 -z-0 rounded-full"
                    style={{ width: 22, height: 3, background: 'var(--ring-grad)' }}
                    transition={{ type: 'spring', stiffness: 480, damping: 36 }}
                  />
                </>
              )}
              <motion.span
                className="z-10 transition-colors"
                animate={{ scale: isActive ? 1.08 : 1, y: isActive ? -1 : 0 }}
                transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                style={{ color: isActive ? 'var(--signal)' : 'var(--ink-faint)' }}
              >
                {t.icon}
              </motion.span>
              <span
                className="z-10 text-[9.5px] font-medium transition-colors"
                style={{ color: isActive ? 'var(--ink)' : 'var(--ink-faint)' }}
              >
                {t.label}
              </span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
