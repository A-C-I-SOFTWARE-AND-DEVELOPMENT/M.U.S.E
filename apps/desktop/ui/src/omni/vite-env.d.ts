/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

// Build-time provenance injected via Vite `define` (see vite.config.ts). Lets the
// running app compare itself against the MUSE `main` HEAD and offer a one-click
// update. Defaults to harmless literals so vitest (which also applies `define`)
// and any non-Vite tool never sees an undefined global.
declare const __BUILD_SHA__: string;
declare const __BUILD_TIME__: string;
declare const __REPO_SLUG__: string;
