# G0.2 — Desktop scaffold (Tauri v2 + Vite/React + PWA)

Builder-grain snapshot for the MUSE App Grainler Parallel Swarm.

- **Grain:** G0.2 — Desktop scaffold (Tauri v2 + Vite/React 19/TS + PWA).
- **Branch:** `claude/muse-app-g02-desktop-scaffold`
- **Base commit:** `d22c3e4a1efe779e234b0428f82484f8b457f9ce` (`origin/main` at start).
- **Status:** built, validated (UI hard gate green), pushed. No PR opened (per grain contract).

## Intent

Stand up a **new, lean Singularity desktop client** — a Tauri v2 shell around a
fresh Vite + React 19 + TypeScript UI (NOT a reuse of the existing `web/` SPA).
The shell loads the bundled UI and talks to a locally-running MUSE gateway over
HTTP; it does **not** bundle or spawn the Python backend. The UI mirrors the
browser cockpit's protocol (bearer-token pairing, SSE jobs over
fetch+ReadableStream, NDJSON chat) and honors the M.U.S.E. visual design
language (white incandescent core, matte spectral ring, value ladder, ≤3 color
roles, emphasized-easing motion, no lens flare / drop-shadows / ring-glow). A
core deliverable is an **append-only route registry** so future feature grains
add routes without editing a shared switch.

## Owned files (created)

All under the two owned paths; nothing else touched.

### `apps/desktop/ui/` — Vite + React 19 + TS client
- `package.json`, `package-lock.json` — React 19, Vite 6, `@vitejs/plugin-react`
  4.x (pinned to the line that supports Vite 6 — latest v6 of the plugin
  requires Vite 8), `vite-plugin-pwa` 1.x, `@types/node`.
- `index.html`, `vite.config.ts` (Vite + PWA, `base: "./"` for Tauri's asset
  protocol, fixed dev port 1420).
- `tsconfig.json` / `tsconfig.app.json` / `tsconfig.node.json`.
- `src/main.tsx` — entry; seeds the route registry, registers the PWA SW.
- `src/App.tsx` — app shell: header lockup (Glyph + "M.U.S.E." wordmark +
  status dot), nav from the route registry, minimal hash router. **Adding a
  route never requires editing this file.**
- `src/components/Glyph.tsx` — the animated incandescent mark as inline SVG
  (white core + stacked cool-white bloom halos + matte cyan→violet ring with a
  gap, rotated -32°; spin honors `prefers-reduced-motion`).
- `src/lib/gateway.ts` — typed gateway client: `pingHealth`, `pairStart` /
  `pairConfirm`, `subscribeJobs` (SSE via fetch + ReadableStream, reconnect with
  backoff, poll fallback), `chat` (NDJSON). Token in `localStorage`
  `muse.cockpit.token`; base URL configurable (`muse.gateway.base` /
  `VITE_GATEWAY_BASE`), default `http://127.0.0.1:8765`.
- `src/routes.ts` — **append-only route registry** (`routes` array +
  `registerRoute` / `getRoutes` / `findRoute`); idempotent on `id`.
- `src/routes.register.ts` — registers the built-in Home route (side-effect
  import). Grains register from their own modules, not here.
- `src/views/Home.tsx` — the one placeholder route; a *live* client exercising
  pairing + NDJSON chat end to end.
- `src/styles/tokens.css` — **inlined** Singularity tokens, byte-identical to
  `gateway/cockpit/static/tokens.css`, with `TODO: consume @muse/design-system
  once merged` (the G0.1 grain's package).
- `src/styles/app.css` — shell styling (void background, tonal elevation, ring
  accent, emphasized motion 250–350ms; no drop-shadows, no ring-glow).
- `src/vite-env.d.ts` — Vite + PWA type refs.
- `public/favicon.svg` — copy of the canonical glyph (`website/static/img/favicon.svg`).
- `public/icons/icon-maskable.svg` + derived PNGs (`icon-192.png`,
  `icon-512.png`, `icon-512-maskable.png`, `apple-touch-icon.png`).
- `.gitignore` — excludes `node_modules/`, `dist/`, `dev-dist/`, `*.tsbuildinfo`.

### `apps/desktop/src-tauri/` — Tauri v2 Rust shell
- `Cargo.toml` — Tauri 2 (`tray-icon` feature; `devtools` in debug),
  `tauri-plugin-single-instance` 2, serde. Release profile: LTO + strip.
- `Cargo.lock` — committed (application crate; reproducible builds).
- `tauri.conf.json` — schema v2; dark window titled **M.U.S.E.** (1180×800, min
  880×600, centered, `backgroundColor #050507`); `beforeDevCommand` /
  `beforeBuildCommand` drive the UI; `frontendDist ../ui/dist`; bundle
  identifier **`com.aci.muse`**, all targets, glyph icon set; a tight CSP whose
  `connect-src` allows the default gateway origins.
- `src/lib.rs` — `run()` shared entry: single-instance plugin (2nd launch
  focuses the window), native menu (app/Quit + Edit + Help→Gateway URL), system
  tray (Show / Hide / Quit + left-click focus), hide-to-tray on window close.
- `src/main.rs` — thin binary entry (Windows subsystem guard) → `run()`.
- `build.rs` — `tauri_build::build()`.
- `capabilities/default.json` — minimal window/tray/menu permissions only (no
  fs/shell/http-plugin scopes; the UI uses plain fetch).
- `icons/` — `32x32.png`, `128x128.png`, `128x128@2x.png`, `icon.png`,
  `icon.ico` (multi-size 16–256), `icon.icns`, all derived from the glyph.
- `.gitignore` — excludes `target/` and `gen/`.

### Other
- `apps/desktop/.gitignore` — belt-and-suspenders artifact exclusion.
- `apps/desktop/README.md` — dev (`npm run dev`; `cargo tauri dev`), build
  (`cargo tauri build`), PWA notes, and the CI dual Rust+Node lane + Linux
  webkit2gtk system-libs note.
- `docs/launch/muse-app/g02-desktop-scaffold.md` — this snapshot.

## Validation results

### UI production build — HARD GATE — PASS
```
cd apps/desktop/ui && npm install && npm run build
```
- `npm install` → 351 packages, **0 vulnerabilities**.
- `npm run build` (= `tsc -b && vite build`) → **green**. 38 modules
  transformed; `dist/` emitted with `index.html`, hashed JS/CSS,
  `manifest.webmanifest` (name "M.U.S.E.", theme/background `#050507`, 192/512/
  maskable + SVG icons, relative `start_url`/`scope`), and the PWA service
  worker (`sw.js`, 16 precache entries). A clean rebuild (`rm -rf dist`) is also
  green. `npx tsc -b` typecheck passes standalone. `ui/dist/` exists.
- Icons rendered and **eyeballed** (design-loop rule): the 512 standard icon and
  512 maskable both show the incandescent white core + matte cyan→violet ring
  with the lower-right gap on the void; the 32px Tauri icon stays legible (ring
  doesn't collapse into a blob).

### Tauri Rust — `cargo check` — EXPECTED ENV FAILURE (NOT a code defect)
```
cd apps/desktop/src-tauri && cargo check
```
- Cargo **resolved the full Tauri v2 dependency tree** and began compiling the
  `*-sys` crates. It then failed in the `gdk-sys` build script:
  `Package 'gdk-3.0' ... not found` — i.e. the Linux **WebKitGTK / GTK system
  libraries are absent in this sandbox** (`pkg-config` reports
  `webkit2gtk-4.1`, `gtk+-3.0`, `javascriptcoregtk-4.1`, `libsoup-3.0` all
  MISSING). This is a system-library gap, **not** a Rust source or
  `tauri.conf.json` error — the failure occurs at the native `pkg-config` probe,
  before our own crate compiles.
- **Compensating review** (since the final link can't run here): every Tauri v2
  API used in `lib.rs` was verified against the resolved crate source
  (`tauri 2.11.2`): `TrayIconBuilder::with_id/.icon/.tooltip/.menu/
  .show_menu_on_left_click/.on_menu_event/.on_tray_icon_event/.build`;
  `TrayIcon::app_handle`; `Menu::with_items`, `Submenu::with_items`,
  `MenuItem::with_id(manager,id,text,enabled,Option<accel>)`,
  `PredefinedMenuItem::{quit,undo,redo,cut,copy,paste,select_all,separator}`;
  `App::set_menu(Menu<R>)`, `AppHandle: Clone`, `App::handle() -> &AppHandle`,
  `Manager::get_webview_window`, `AppHandle::exit`, `on_window_event(Fn(&Window,
  &WindowEvent))`. Signatures and arities match. The setup closure clones the
  `AppHandle` to keep menu/tray construction independent of the `&mut App`
  borrow `set_menu` needs.

## Residual risks

1. **Tauri compilation requires the CI toolchain lane + Linux system libs**
   (the headline caveat). `cargo check` / `cargo tauri build` cannot complete on
   a Linux box without `libwebkit2gtk-4.1-dev`, `libgtk-3-dev`,
   `libjavascriptcoregtk-4.1-dev`, `libsoup-3.0-dev`, `librsvg2-dev`,
   `libayatana-appindicator3-dev` (+ `build-essential pkg-config`). The README
   lists the exact apt line and the recommended CI matrix
   (`tauri-apps/tauri-action`, or a manual Rust+Node lane). macOS/Windows
   runners need no extra system libs. **Until that lane runs, the final Rust
   link of `lib.rs`/`main.rs` is review-verified, not machine-compiled.**
2. **No `cargo tauri icon` available here**, so the icon set was generated with
   `cairosvg` + Pillow from the glyph SVG. The PNG/ICO sizes match what
   `tauri.conf.json` references; the `.icns` is a single-source Pillow render
   (Apple's iconutil would produce a more exhaustive set — regenerate on a mac
   if pixel-perfect Retina dock icons matter).
3. **Inlined design tokens are a temporary duplicate.** `src/styles/tokens.css`
   copies `gateway/cockpit/static/tokens.css`; once the G0.1 `@muse/design-system`
   package merges, swap the inline copy for an import (TODO is in the file).
   Until then, a token change in the canonical source must be mirrored here.
4. **PWA caching is intentionally shell-only.** `/v1/*` is never cached
   (network-first live data). If a future grain wants offline job history it
   must add an explicit, namespaced runtime-caching rule — don't loosen the
   navigate-fallback denylist.
5. **Tauri version pinning:** `Cargo.toml` uses `tauri = "2"` (resolved to
   2.11.2 in `Cargo.lock`). The committed lockfile pins the resolution; a future
   `cargo update` should be reviewed against the CI lane.
6. **No collisions with sibling grains.** Work is confined to `apps/desktop/**`
   and this snapshot; `web/`, `apps/android/`, `design-system/`, `gateway/`, and
   the central ledger were not touched. The `@muse/design-system` dependency is
   declared only as a TODO comment, so there is no build coupling to G0.1 yet.

## Reproduce

```bash
git checkout claude/muse-app-g02-desktop-scaffold
cd apps/desktop/ui && npm install && npm run build   # hard gate (green)
# Native shell (needs Rust + Tauri CLI + Linux webkit2gtk libs):
cd ../src-tauri && cargo tauri dev                     # or: cargo tauri build
```
