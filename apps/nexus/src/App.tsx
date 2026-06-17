import { Routes, Route, Navigate } from 'react-router-dom';
import { TabBar } from './components/shell/TabBar';
import { TopBar } from './components/shell/TopBar';
import ConsolePage from './pages/ConsolePage';
import SteerPage from './pages/SteerPage';
import AgentsPage from './pages/AgentsPage';
import ActivityPage from './pages/ActivityPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <div className="flex h-full flex-col">
      <TopBar />
      <main
        className="scroll-area flex-1"
        style={{ paddingBottom: 'calc(var(--tab-h) + env(safe-area-inset-bottom))' }}
      >
        <Routes>
          <Route path="/" element={<ConsolePage />} />
          <Route path="/steer" element={<SteerPage />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/activity" element={<ActivityPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <TabBar />
    </div>
  );
}
