/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { fileURLToPath, URL } from 'node:url';
import { execSync } from 'node:child_process';

// NEXUS PWA build config.
// vite-plugin-pwa wires Workbox: offline app shell + runtime caching for the
// M.U.S.E. API (network-first so live data wins, cached shell as fallback).
// NEXUS_BASE lets a subpath deploy (GitHub Pages at /M.U.S.E/) build correctly;
// root deploys (Vercel) leave it at '/'.
const base = process.env.NEXUS_BASE || '/';
const hash = base !== '/' ? '#' : ''; // HashRouter URLs under a subpath

// Build provenance — embedded so the running app can tell whether it is in sync
// with the MUSE `main` branch on GitHub and offer a one-click update.
function gitSha(): string {
  if (process.env.NEXUS_COMMIT_SHA) return process.env.NEXUS_COMMIT_SHA.slice(0, 7);
  try {
    return execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] })
      .toString()
      .trim();
  } catch {
    return 'dev';
  }
}
const BUILD_SHA = gitSha();
const BUILD_TIME = new Date().toISOString();
const REPO_SLUG = process.env.NEXUS_REPO_SLUG || 'A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E';

export default defineConfig({
  base,
  define: {
    __BUILD_SHA__: JSON.stringify(BUILD_SHA),
    __BUILD_TIME__: JSON.stringify(BUILD_TIME),
    __REPO_SLUG__: JSON.stringify(REPO_SLUG),
  },
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  plugins: [
    react(),
    VitePWA({
      // The service-worker generation (workbox-build runs its own Rollup pass)
      // can fail in constrained environments like Termux/Android ("Unable to
      // write the service worker file"). It is purely a progressive enhancement
      // (offline shell) and is NOT needed when the gateway serves NEXUS, so the
      // Termux on-device build sets NEXUS_NO_PWA=1 to skip it. `disable:true`
      // still leaves virtual:pwa-register resolvable as a no-op, so main.tsx
      // compiles unchanged.
      disable: process.env.NEXUS_NO_PWA === '1',
      // 'prompt' (not autoUpdate) so the user drives the one-click "Update NEXUS"
      // action from the Repo Sync surface. We register the SW ourselves in
      // main.tsx via virtual:pwa-register, hence injectRegister:false.
      registerType: 'prompt',
      injectRegister: false,
      includeAssets: ['favicon.svg', 'icons/icon-192.png', 'icons/icon-512.png'],
      manifest: {
        name: 'NEXUS — Agent Command Console',
        short_name: 'NEXUS',
        description:
          'Unified, live command center for M.U.S.E. — orchestration, the steering octagon, the Axiom Gate, and the Neural Observatory.',
        theme_color: '#0A0E14',
        background_color: '#0A0E14',
        display: 'standalone',
        orientation: 'portrait',
        start_url: base,
        scope: base,
        id: base,
        categories: ['productivity', 'developer', 'utilities'],
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          {
            src: 'icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
        // App shortcuts (long-press the home-screen icon).
        shortcuts: [
          { name: 'Steer', short_name: 'Steer', url: `${base}${hash}/steer`, icons: [{ src: 'icons/icon-192.png', sizes: '192x192' }] },
          { name: 'Axiom Gate', short_name: 'Axiom', url: `${base}${hash}/axiom`, icons: [{ src: 'icons/icon-192.png', sizes: '192x192' }] },
          { name: 'Observatory', short_name: 'Observatory', url: `${base}${hash}/observatory`, icons: [{ src: 'icons/icon-192.png', sizes: '192x192' }] },
          { name: 'Wallpaper', short_name: 'Wallpaper', url: `${base}${hash}/observatory?wallpaper=1`, icons: [{ src: 'icons/icon-192.png', sizes: '192x192' }] },
        ],
        // Share-sheet target: "Send to M.U.S.E." → opens a goal composer.
        share_target: {
          action: `${base}${hash}/share`,
          method: 'GET',
          params: { title: 'title', text: 'text', url: 'url' },
        },
      },
      workbox: {
        navigateFallback: `${base}index.html`,
        runtimeCaching: [
          {
            // M.U.S.E. backend: network-first, fall back to cache when offline.
            urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'muse-api',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 },
            },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
  },
});
