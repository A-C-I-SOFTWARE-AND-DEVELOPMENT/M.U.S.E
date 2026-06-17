import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, HashRouter } from 'react-router-dom';
import App from './App';
import { startHealthMonitor } from './lib/health';
import './styles/index.css';

startHealthMonitor();

// Under a non-root base (e.g. GitHub Pages at /M.U.S.E/) use HashRouter so deep
// links work without server-side SPA rewrites; root deploys (Vercel) use clean
// BrowserRouter paths.
const Router = import.meta.env.BASE_URL !== '/' ? HashRouter : BrowserRouter;

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Router>
      <App />
    </Router>
  </React.StrictMode>,
);
