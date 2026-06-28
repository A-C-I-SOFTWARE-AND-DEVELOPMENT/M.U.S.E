import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Suspense, lazy, useEffect, useState, type ReactNode } from 'react';
import { TabBar } from './components/shell/TabBar';
import { SideNav } from './components/shell/SideNav';
import { TopBar } from './components/shell/TopBar';
import { CinematicBackdrop } from './components/shell/CinematicBackdrop';
import { CommandPalette } from './components/shell/CommandPalette';
import { ConnectWizard } from './components/setup/ConnectWizard';
import { isConfigured } from './lib/config';
import { anyProviderReady } from './lib/directProvider';
import { useNexusStore } from './store/useNexusStore';
import ConsolePage from './pages/ConsolePage';
import SteerPage from './pages/SteerPage';
import AxiomGatePage from './pages/AxiomGatePage';
import ObservatoryPage from './pages/ObservatoryPage';
import ChatPage from './pages/ChatPage';
import FusionPage from './pages/FusionPage';
import ForgePage from './pages/ForgePage';
import FleetPage from './pages/FleetPage';
import ModelsPage from './pages/ModelsPage';
import SecondBrainPage from './pages/SecondBrainPage';
import ChampionshipPage from './pages/ChampionshipPage';
import FederationPage from './pages/FederationPage';
import CouncilPage from './pages/CouncilPage';
import RepoPage from './pages/RepoPage';
import SharePage from './pages/SharePage';
import AgentsPage from './pages/AgentsPage';
import ActivityPage from './pages/ActivityPage';
import SettingsPage from './pages/SettingsPage';

// SignInPage is authored by a sibling task; lazy-import it so the route is
// code-split off the shell. The module may not be on disk yet at the moment
// this file is integrated, so the missing-module diagnostic is suppressed —
// it resolves cleanly once the sibling task lands its page.
// @ts-ignore -- ./pages/SignInPage is provided by a sibling task
const SignInPage = lazy(() => import('./pages/SignInPage'));

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

const ONBOARD_KEY = 'nexus.onboarded';

export default function App() {
  const location = useLocation();
  const wallpaper = useNexusStore((s) => s.wallpaper);

  // First-run: auto-open the connect wizard only when there's nothing to go on —
  // no gateway AND no provider key. If either is present we auto go online and use
  // the app directly (no nag). The wizard stays reachable via "Install & connect".
  const [wizard, setWizard] = useState(
    () => !isConfigured() && !anyProviderReady() && localStorage.getItem(ONBOARD_KEY) !== '1',
  );
  useEffect(() => {
    const open = () => setWizard(true);
    window.addEventListener('nexus:open-setup', open);
    // Once a provider key (or gateway) lands — including after async secret
    // hydration — drop the first-run wizard and go straight online.
    const reeval = () => {
      if (localStorage.getItem(ONBOARD_KEY) !== '1' && (isConfigured() || anyProviderReady())) {
        setWizard(false);
      }
    };
    window.addEventListener('nexus:config', reeval);
    return () => {
      window.removeEventListener('nexus:open-setup', open);
      window.removeEventListener('nexus:config', reeval);
    };
  }, []);
  const closeWizard = () => {
    localStorage.setItem(ONBOARD_KEY, '1');
    setWizard(false);
  };

  // Wallpaper ("mirror") mode renders the Observatory full-bleed with no chrome.
  if (wallpaper) return <ObservatoryPage />;

  return (
    <div className="flex h-full flex-col">
      <CinematicBackdrop />
      <ConnectWizard open={wizard} onClose={closeWizard} />
      <CommandPalette />
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <SideNav />
        <main className="scroll-area flex-1 pb-[calc(var(--tab-h)+env(safe-area-inset-bottom))] md:pb-0">
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={<Page><ChatPage /></Page>} />
            <Route path="/chat" element={<Navigate to="/" replace />} />
            <Route path="/console" element={<Page><ConsolePage /></Page>} />
            <Route
              path="/signin"
              element={
                <Suspense fallback={null}>
                  <Page><SignInPage /></Page>
                </Suspense>
              }
            />
            <Route path="/steer" element={<Page><SteerPage /></Page>} />
            <Route path="/axiom" element={<Page><AxiomGatePage /></Page>} />
            <Route path="/observatory" element={<Page><ObservatoryPage /></Page>} />
            <Route path="/fusion" element={<Page><FusionPage /></Page>} />
            <Route path="/forge" element={<Page><ForgePage /></Page>} />
            <Route path="/fleet" element={<Page><FleetPage /></Page>} />
            <Route path="/models" element={<Page><ModelsPage /></Page>} />
            <Route path="/second-brain" element={<Page><SecondBrainPage /></Page>} />
            <Route path="/championship" element={<Page><ChampionshipPage /></Page>} />
            <Route path="/federation" element={<Page><FederationPage /></Page>} />
            <Route path="/council" element={<Page><CouncilPage /></Page>} />
            <Route path="/repo" element={<Page><RepoPage /></Page>} />
            <Route path="/share" element={<Page><SharePage /></Page>} />
            <Route path="/agents" element={<Page><AgentsPage /></Page>} />
            <Route path="/activity" element={<Page><ActivityPage /></Page>} />
            <Route path="/settings" element={<Page><SettingsPage /></Page>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AnimatePresence>
        </main>
      </div>
      <TabBar />
    </div>
  );
}
