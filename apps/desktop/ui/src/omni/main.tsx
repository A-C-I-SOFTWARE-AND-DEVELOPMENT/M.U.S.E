import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, HashRouter } from 'react-router-dom';
import { registerSW } from 'virtual:pwa-register';
import App from './App';
import { AuthProvider } from './auth/AuthProvider';
import { startHealthMonitor } from './lib/health';
import { registerUpdater, markNeedRefresh, markOfflineReady } from './lib/appUpdate';
import { autoSyncOnLaunch } from './lib/autoSync';
import './styles/index.css';

startHealthMonitor();

// On install / every launch: silently sync to a MUSE gateway on this device and
// import the owner's existing providers + keys (owner-gated first pairing aside).
void autoSyncOnLaunch();

// Register the service worker ourselves (vite-plugin-pwa injectRegister:false) so
// the Repo Sync surface can drive a one-click "Update NEXUS" — pulling the newest
// build off the MUSE `main` deploy. registerType:'prompt' surfaces onNeedRefresh.
const updateSW = registerSW({
  immediate: true,
  onNeedRefresh: markNeedRefresh,
  onOfflineReady: markOfflineReady,
});
registerUpdater(updateSW);

// Under a non-root base (e.g. GitHub Pages at /M.U.S.E/) use HashRouter so deep
// links work without server-side SPA rewrites; root deploys (Vercel) use clean
// BrowserRouter paths.
const Router = import.meta.env.BASE_URL !== '/' ? HashRouter : BrowserRouter;

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Router>
      <AuthProvider>
        <App />
      </AuthProvider>
    </Router>
  </React.StrictMode>,
);
