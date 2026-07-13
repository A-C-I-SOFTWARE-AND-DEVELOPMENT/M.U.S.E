import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { resolve } from "path";

// muse desktop UI build.
//
// This single Vite project is consumed two ways:
//   1. As a Progressive Web App (installable browser cockpit) — the VitePWA
//      plugin emits a web manifest + service worker so it works offline-first.
//   2. As the webview payload bundled inside the Tauri v2 desktop shell
//      (../src-tauri). Tauri loads `dist/` over the custom `tauri://` protocol,
//      so we emit relative asset URLs (`base: "./"`).
//
// The dev server port is fixed (1420) and matches `devUrl` in
// ../src-tauri/tauri.conf.json so `cargo tauri dev` finds the running UI.
const host = process.env.TAURI_DEV_HOST;

export default defineConfig({
  // Relative base so the bundle works both from a web server root and from
  // Tauri's asset protocol.
  base: "./",
  resolve: {
    alias: {
      "@muse/design-system": resolve(__dirname, "../../../design-system"),
      "@": resolve(__dirname, "src/omni"),
    },
  },
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      // The glyph favicon + derived icons live in public/ and are copied
      // verbatim into the build.
      includeAssets: ["favicon.svg", "icons/*.png"],
      manifest: {
        name: "muse",
        short_name: "muse",
        description: "Multi-Use Synaptic Entity — your local-first AI operating partner.",
        // The void. The whole brand sits on it.
        theme_color: "#050507",
        background_color: "#050507",
        display: "standalone",
        orientation: "any",
        start_url: "./",
        scope: "./",
        icons: [
          { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "icons/icon-512-maskable.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
          { src: "favicon.svg", sizes: "any", type: "image/svg+xml" },
        ],
      },
      workbox: {
        // Cache the app shell; the gateway API is always network-first (live
        // data), so we deliberately do NOT cache /v1/* responses here.
        globPatterns: ["**/*.{js,css,html,svg,png,ico,woff2}"],
        navigateFallbackDenylist: [/^\/v1\//],
      },
      devOptions: {
        // Keep the service worker out of the way during `npm run dev`.
        enabled: false,
      },
    }),
  ],
  // Tauri expects a fixed port and clear errors.
  clearScreen: false,
  server: {
    host: host || "127.0.0.1",
    port: 1420,
    strictPort: true,
    hmr: host
      ? { protocol: "ws", host, port: 1421 }
      : undefined,
  },
  build: {
    // Tauri v2 targets a modern Chromium/WebKit; widen target a little for
    // Safari/WebKit on macOS + Linux webkit2gtk.
    target: ["es2021", "chrome105", "safari15"],
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
  },
});
