# muse — Desktop app (Tauri v2)

A native desktop shell for **muse** (Multi-Use Synaptic Entity), built with
**Tauri v2** wrapping a lean **Singularity** client (Vite + React 19 +
TypeScript). The shell loads the bundled UI and talks to a locally-running muse
**gateway** over HTTP. It does **not** bundle the Python backend — but it *can
start it*: when the gateway is down and an installed `muse` CLI is found, the
shell spawns `muse cockpit serve` as a managed child (see
[One installable](#one-installable-the-app-starts-the-brain) below).

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
│   │   ├── lib/brain.ts       # native bridge: gateway_start/stop/status, autostart
│   │   ├── routes.ts          # APPEND-ONLY route registry (the extension seam)
│   │   ├── routes.register.ts # registers the built-in Home route
│   │   ├── views/             # Home, Chat, Jobs, Approvals, Autonomy, Observatory, Settings
│   │   └── styles/tokens.css  # @import "@muse/design-system/tokens.css" + desktop motion aliases
│   ├── public/                # favicon.svg + derived PWA icons
│   └── vite.config.ts         # Vite + vite-plugin-pwa (manifest + service worker)
└── src-tauri/      # Tauri v2 Rust shell
    ├── src/lib.rs             # window + native menu + system tray + single-instance
    ├── src/brain.rs           # gateway autostart: probe /v1/health, spawn `muse cockpit serve`
    ├── src/main.rs            # thin binary entry → lib::run()
    ├── tauri.conf.json        # dark window "muse", bundle id com.aci.muse
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

### Zero-touch pairing (install → open → connected)

On a **loopback** gateway (the default) the desktop app pairs itself: at boot
(and on every health tick while unpaired) it silently walks
`pair/start → pair/confirm` and stores the minted per-device token — no code,
no owner phrase, no gateway URL to type. This leans on the gateway's own
loopback trust rule (`gateway/cockpit/handlers.py:pair_confirm`): anything that
can reach `127.0.0.1` is already on the device, so the owner phrase is only
enforced when the cockpit is started `--allow-external`. Point the app at a
**remote** gateway and auto-pairing steps aside (the server answers 403), the
manual owner-phrase pairing flow in Settings takes over, and nothing is minted
silently.

The gateway's default CORS allowlist includes the desktop webview origins
(`tauri://localhost`, `http(s)://tauri.localhost`, and the Vite dev server on
`:1420`), so the UI talks to the gateway directly — streaming SSE jobs and
NDJSON chat. Against an older gateway without those origins, requests fall
back to the shell's native HTTP proxy (buffered, non-streaming) and the jobs
list degrades to polling; everything still works.

## One installable: the app starts the brain

The desktop app is designed to be the only thing a user launches. On startup
the shell probes `GET /v1/health`; if the gateway ("the brain") is down **and
autostart is enabled** (persisted in `app_config_dir/brain.json`, default on),
it locates an installed `muse` binary — `PATH`, then common install locations
(`~/.local/bin`, `~/.cargo/bin`, `/usr/local/bin`, `/opt/homebrew/bin`,
`%LOCALAPPDATA%\Programs\…` on Windows) — and spawns **`muse cockpit serve`**
as a managed child (`src-tauri/src/brain.rs`, via `tauri-plugin-shell`,
Rust-side only; the webview gets no shell permission).

Semantics:

- It **never** spawns over a running gateway (probe first, every time) and
  never spawns twice (the child handle is tracked).
- Closing the window hides to tray and **keeps the brain running**; the child
  is killed only on real quit (tray/menu Quit).
- **Stop** only kills the child the app spawned — a gateway you started in a
  terminal is never touched.
- Settings → **Brain (gateway)** shows running/stopped + the detected binary,
  the autostart toggle, and Start/Stop buttons. The **Observatory** view's
  offline fallback offers the same Start.

If no `muse` binary is installed, the app still runs (views show the offline
fallback) and Settings links to the CLI install docs.

### Designed follow-up: bundling the runtime as a sidecar

Today the brain comes from an installed `muse` CLI. The fully self-contained
installer is a **documented follow-up**: package the gateway as a PyInstaller
single binary per OS and ship it as a Tauri *sidecar*, e.g.

```jsonc
// tauri.conf.json (sketch — not active)
"bundle": {
  "externalBin": ["binaries/muse-gateway"]  // resolves muse-gateway-<target-triple>[.exe]
}
```

with `pyinstaller --onefile` producing `muse-gateway-x86_64-unknown-linux-gnu`,
`muse-gateway-aarch64-apple-darwin`, `muse-gateway-x86_64-pc-windows-msvc.exe`,
etc., and `brain.rs` preferring the sidecar (`shell.sidecar("muse-gateway")`)
over the PATH search. Per-OS PyInstaller builds need real OS runners (they
cannot be cross-compiled or verified in a Linux container), so this lands via
the CI matrix in `muse-desktop-release.yml` when activated.

## Build

```bash
# Production UI bundle (also runs automatically as beforeBuildCommand)
cd apps/desktop/ui && npm run build      # → ui/dist/

# Native installers for the current OS (.dmg / .msi+.exe / .deb+.AppImage)
cd apps/desktop/src-tauri && cargo tauri build
```

Bundle identifier: `com.aci.muse`. Window: dark, titled **muse**, min
880×600. Icons are derived from the brand glyph
(`ui/public/favicon.svg`).

Auto-update is scaffolded but **inert**: `plugins.updater` ships an empty
`pubkey` placeholder and the plugin is only registered when a real public key
is configured. Activation is owner-gated — see [`RELEASE.md`](RELEASE.md).

## PWA

The UI is also an installable PWA: `vite-plugin-pwa` emits
`manifest.webmanifest` (name **muse**, `theme_color`/`background_color`
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
