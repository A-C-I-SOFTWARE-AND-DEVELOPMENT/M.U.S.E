import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { TabBar } from './components/shell/TabBar';
import { TopBar } from './components/shell/TopBar';
import { useNexusStore } from './store/useNexusStore';
import ConsolePage from './pages/ConsolePage';
import SteerPage from './pages/SteerPage';
import AxiomGatePage from './pages/AxiomGatePage';
import ObservatoryPage from './pages/ObservatoryPage';
import AgentsPage from './pages/AgentsPage';
import ActivityPage from './pages/ActivityPage';
import SettingsPage from './pages/SettingsPage';

// Apple/Google-grade page transition: a quick, springy fade + lift. Respects
// prefers-reduced-motion via the CSS media query in tokens.css (transforms are
// disabled there) — Framer still mounts, just without motion distance.
function Page({ children }: { children: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

export default function App() {
  const location = useLocation();
  const wallpaper = useNexusStore((s) => s.wallpaper);

  // Wallpaper ("mirror") mode renders the Observatory full-bleed with no chrome.
  if (wallpaper) return <ObservatoryPage />;

  return (
    <div className="flex h-full flex-col">
      <TopBar />
      <main
        className="scroll-area flex-1"
        style={{ paddingBottom: 'calc(var(--tab-h) + env(safe-area-inset-bottom))' }}
      >
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={<Page><ConsolePage /></Page>} />
            <Route path="/steer" element={<Page><SteerPage /></Page>} />
            <Route path="/axiom" element={<Page><AxiomGatePage /></Page>} />
            <Route path="/observatory" element={<Page><ObservatoryPage /></Page>} />
            <Route path="/agents" element={<Page><AgentsPage /></Page>} />
            <Route path="/activity" element={<Page><ActivityPage /></Page>} />
            <Route path="/settings" element={<Page><SettingsPage /></Page>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AnimatePresence>
      </main>
      <TabBar />
    </div>
  );
}
