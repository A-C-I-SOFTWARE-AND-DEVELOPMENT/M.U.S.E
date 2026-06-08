# M.U.S.E. — Desktop app (Tauri v2)

A native desktop shell for **M.U.S.E.** (Multi-Use Synaptic Entity), built with
**Tauri v2** wrapping a lean **Singularity** client (Vite + React 19 +
TypeScript). The shell loads the bundled UI and talks to a locally-running MUSE
**gateway** over HTTP — it does **not** bundle or spawn the Python backend.

> One white core that blazes in the void, wrapped by one thin spectral ring.
> See [`docs/brand/muse-design-language.md`](../../docs/brand/muse-design-language.md).

## Layout

```
apps/desktop/
├── ui/             # Vite + React 19 + TS — the Singularity client
│   ├── src/
│   │   ├── App.tsx            # app shell: header lockup, nav, hash router
│   │   ├── components/Glyph.tsx   # the animated incandescent mark (inline SVG)
│   │   ├── lib/gateway.ts     # gateway client: health, pairing, SSE jobs, NDJSON chat
│   │   ├── routes.ts          # APPEND-ONLY route registry (the extension seam)
│   │   ├── routes.register.ts # registers the built-in Home route
│   │   ├── views/Home.tsx     # the one placeholder route
│   │   └── styles/tokens.css  # inlined Singularity tokens (TODO: @muse/design-system)
│   ├── public/                # favicon.svg + derived PWA icons
│   └── vite.config.ts         # Vite + vite-plugin-pwa (manifest + service worker)
└── src-tauri/      # Tauri v2 Rust shell
    ├── src/lib.rs             # window + native menu + system tray + single-instance
    ├── src/main.rs            # thin binary entry → lib::run()
    ├── tauri.conf.json        # dark window "M.U.S.E.", bundle id com.aci.muse
    ├── capabilities/default.json  # minimal window/tray/menu permissions
    ├── icons/                 # app icons derived from the glyph
    ├── Cargo.toml
    └── build.rs
```

## Prerequisites

- **Node** ≥ 20 and **npm** ≥ 10.
- **Rust** (stable, ≥ 1.77.2) + Cargo.
- The **Tauri CLI**: `cargo install tauri-cli --version "^2"` (gives
  `cargo tauri …`).
- **Linux only:** the WebKitGTK / GTK system libraries Tauri's webview needs.
  On Debian/Ubuntu:

  ```bash
  sudo apt-get install -y \
    libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev \
    libsoup-3.0-dev libjavascriptcoregtk-4.1-dev \
    libayatana-appindicator3-dev build-essential curl wget file pkg-config
  ```

  (macOS and Windows need no extra system libs beyond Xcode CLT / MSVC +
  WebView2.)

## Develop

The UI and the shell can be run independently or together.

```bash
# 1) UI only (browser / PWA), hot-reloading on http://127.0.0.1:1420
cd apps/desktop/ui
npm install
npm run dev

# 2) Full desktop app (spawns the UI dev server via beforeDevCommand)
cd apps/desktop/src-tauri
cargo tauri dev
```

`cargo tauri dev` runs `npm --prefix ../ui run dev` and points the native
window at `http://127.0.0.1:1420` (see `build.devUrl` in `tauri.conf.json`).

### Pointing at a gateway

The app defaults to `http://127.0.0.1:8765`. Override it at runtime in-app
(stored in `localStorage` under `muse.gateway.base`), or at build time with the
`VITE_GATEWAY_BASE` env var for the UI. The native menu's **Help → Gateway**
item reflects `MUSE_GATEWAY_URL` if set.

The first launch is unpaired: use the **Pair this device** card to mint a
per-device bearer token (owner-phrase gated), exactly like the browser cockpit.

## Build

```bash
# Production UI bundle (also runs automatically as beforeBuildCommand)
cd apps/desktop/ui && npm run build      # → ui/dist/

# Native installers for the current OS (.dmg / .msi+.exe / .deb+.AppImage)
cd apps/desktop/src-tauri && cargo tauri build
```

Bundle identifier: `com.aci.muse`. Window: dark, titled **M.U.S.E.**, min
880×600. Icons are derived from the brand glyph
(`ui/public/favicon.svg`).

## PWA

The UI is also an installable PWA: `vite-plugin-pwa` emits
`manifest.webmanifest` (name **M.U.S.E.**, `theme_color`/`background_color`
`#050507`) and a service worker that precaches the app shell. The gateway API
(`/v1/*`) is deliberately **not** cached — it's always live. Serve `ui/dist/`
from any static host (or open the built `index.html`) to install it.

## CI note

Building the desktop app needs a **dual Rust + Node lane** in CI:

1. Set up Node (≥ 20) and Rust (stable), with caching for `~/.cargo`,
   `src-tauri/target`, and `ui/node_modules`.
2. **On Linux runners, install the WebKitGTK system libs above** before
   `cargo tauri build` / `cargo check` — without `libwebkit2gtk-4.1-dev` &
   friends, the `*-sys` crates (`gdk-sys`, `webkit2gtk-sys`, …) fail at the
   `pkg-config` probe, not at Rust compile time.
3. The UI build (`npm ci && npm run build` in `ui/`) is the cheap, fast gate
   and can run on any runner without system libs; gate PRs on it first, then
   run the heavier Tauri compile/bundle on a matrix of macOS / Windows / Linux.

The official [`tauri-apps/tauri-action`](https://github.com/tauri-apps/tauri-action)
GitHub Action wraps steps 1–2 and produces per-OS installers.
