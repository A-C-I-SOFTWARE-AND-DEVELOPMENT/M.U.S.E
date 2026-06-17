import { NavLink } from 'react-router-dom';
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
  { to: '/', label: 'Console', icon: I(<><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>) },
  { to: '/steer', label: 'Steer', icon: I(<><polygon points="12,2 19,6 19,14 12,18 5,14 5,6" /><circle cx="12" cy="10" r="2.4" /></>) },
  { to: '/agents', label: 'Agents', icon: I(<><circle cx="12" cy="8" r="3.2" /><path d="M5 20c0-3.3 3.1-5.5 7-5.5s7 2.2 7 5.5" /></>) },
  { to: '/activity', label: 'Activity', icon: I(<polyline points="2,13 7,13 10,4 14,20 17,13 22,13" />) },
  { to: '/settings', label: 'Settings', icon: I(<><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" /></>) },
];

export function TabBar() {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 flex items-stretch justify-around border-t border-[var(--hairline)] bg-[rgba(10,14,20,0.86)] backdrop-blur-xl"
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
          className="group flex flex-1 flex-col items-center justify-center gap-1"
        >
          {({ isActive }) => (
            <>
              <span
                className="transition-colors"
                style={{ color: isActive ? 'var(--octa-glow)' : 'var(--ink-faint)' }}
              >
                {t.icon}
              </span>
              <span
                className="text-[10px] font-medium transition-colors"
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
