/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { fileURLToPath, URL } from 'node:url';

// NEXUS PWA build config.
// vite-plugin-pwa wires Workbox: offline app shell + runtime caching for the
// M.U.S.E. API (network-first so live data wins, cached shell as fallback).
export default defineConfig({
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
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
        start_url: '/',
        scope: '/',
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
          { name: 'Steer', short_name: 'Steer', url: '/steer', icons: [{ src: 'icons/icon-192.png', sizes: '192x192' }] },
          { name: 'Axiom Gate', short_name: 'Axiom', url: '/axiom', icons: [{ src: 'icons/icon-192.png', sizes: '192x192' }] },
          { name: 'Observatory', short_name: 'Observatory', url: '/observatory', icons: [{ src: 'icons/icon-192.png', sizes: '192x192' }] },
          { name: 'Wallpaper', short_name: 'Wallpaper', url: '/observatory?wallpaper=1', icons: [{ src: 'icons/icon-192.png', sizes: '192x192' }] },
        ],
        // Share-sheet target: "Send to M.U.S.E." → opens a goal composer.
        share_target: {
          action: '/share',
          method: 'GET',
          params: { title: 'title', text: 'text', url: 'url' },
        },
      },
      workbox: {
        navigateFallback: '/index.html',
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
