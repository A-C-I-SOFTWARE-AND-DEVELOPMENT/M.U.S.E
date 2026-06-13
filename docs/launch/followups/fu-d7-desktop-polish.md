# FU-D7: Desktop (Tauri v2) polish — About/menu actions, window-state, a11y, glib triage

- **Status:** in-review (PR #456)
- **Risk class:** additive (new menu actions + plugins; no default web/runtime code paths changed)
- **Branch:** `claude/fu-d7-desktop-polish-r2` · **Base:** `main` @ `f17ee72f1`
  (includes `7ba9f7bd` desktop release packaging and `bb19e9c45` dependabot fixes).
  A previous attempt at this grain was lost before pushing; this is a fresh
  rebuild. A *local* branch `claude/fu-d7-desktop-polish` existed checked out in
  another worktree (nothing on origin), so per instructions nothing was deleted
  and the `-r2` name is used.
- **PR:** #456 (draft) — the Wave-D session was suspended before any PR for
  this grain was opened (an earlier "#438" reference here was a stale
  placeholder; #438 was G1 root-tidy). Landed 2026-06-13 by cherry-picking
  `2eab724ab` from `claude/fu-d7-desktop-polish-r2` onto `main` @ `851930f2d`
  via the orchestrator session branch `claude/stoic-planck-l3dvd6`
  (single-branch pattern, as Wave C). Keep-both conflict resolution with the
  brain sidecar that had landed in the same files (`brain.rs`, shell plugin,
  RunEvent reaping): shell + window-state + clipboard plugins coexist;
  capability description merged; `Cargo.lock` re-resolved by cargo on top of
  main's lock (+347 lines; glib unchanged at 0.18.5 — triage below still
  exact). Re-validated on the rebased branch in-container: `npm ci` +
  `npm run build` green, `cargo check` green (1m02s), capabilities JSON
  parses, `scan_secrets --base origin/main` exit 0, `tokens.css` untouched.
- **Owner-gate required to merge?** no (additive desktop-shell polish; merge on
  green CI per the parallel follow-up contract)

## Intent (one paragraph)

Polish the M.U.S.E. desktop shell while keeping the Singularity brand intact
(`apps/desktop/ui/src/styles/tokens.css` stays FROZEN byte-identical — not
touched). Before: the app menu had only Quit, the Help menu carried a disabled
informational gateway item, window geometry reset every restart, the UI had no
keyboard route switching, the offline banner offered no immediate recovery,
links had no focus ring, and only the glyph spin honored reduced motion. After:
a real native About dialog, a working "Copy Gateway URL" menu action, window
size/position persisted across restarts (including the hide-to-tray quit path),
Cmd/Ctrl+1..n route switching, a Retry button on the offline banner, a
focus-visible ring on links too, and a global `prefers-reduced-motion` guard.
The deferred G9 Dependabot item (glib) is triaged below.

## Owned files (the ONLY files this task may write)

- `apps/desktop/src-tauri/src/lib.rs`
- `apps/desktop/src-tauri/Cargo.toml`
- `apps/desktop/src-tauri/Cargo.lock`
- `apps/desktop/src-tauri/capabilities/default.json`
- `apps/desktop/ui/src/App.tsx`
- `apps/desktop/ui/src/styles/app.css`
- `docs/launch/followups/fu-d7-desktop-polish.md` (this snapshot)

> Explicitly NOT touched: `apps/desktop/src-tauri/tauri.conf.json`,
> `.github/workflows/muse-desktop-release.yml`,
> `apps/desktop/ui/src/styles/tokens.css` (FROZEN),
> `docs/launch/10_10_followups_ledger.md` (orchestrator-only).

## Plan (bounded steps) — all done

1. **About menu item** — `PredefinedMenuItem::about(app, Some("About M.U.S.E."),
   Some(AboutMetadata { name, version, comments, ..Default::default() }))` in
   `build_menu`; version comes from `app.package_info().version`, comments are
   "Multi-Use Synaptic Entity — One mind, many pathways."
2. **Window-state persistence** — `tauri-plugin-window-state = "2"` (resolved
   2.4.1) registered via `.plugin(tauri_plugin_window_state::Builder::default().build())`;
   because the shell uses hide-to-tray (window rarely destroyed), the tray Quit
   handler explicitly calls `app.save_window_state(StateFlags::all())` before
   `app.exit(0)`. `window-state:default` added to capabilities (backend restore
   needs no permission; this keeps the JS-side API consistent if ever used).
3. **Copy Gateway URL** — replaced the disabled `gateway-url` info item with an
   enabled `copy-gateway-url` item ("Copy Gateway URL (<url>)", URL still
   visible); handled in the builder's `.on_menu_event` via
   `tauri-plugin-clipboard-manager` (resolved 2.3.2) `app.clipboard().write_text(...)`;
   `clipboard-manager:allow-write-text` added to capabilities.
4. **Keyboard nav** — App.tsx `keydown` listener: Cmd/Ctrl+1..n (no Alt/Shift)
   selects the nth entry of the append-only route registry (`getRoutes()[n-1]`),
   updates the hash + active route; listener removed on unmount.
5. **A11y polish** — `a:focus-visible` joined the existing 2px `var(--ring-1)`
   outline rule (buttons/nav/inputs/select/textarea were already covered); added
   a global `@media (prefers-reduced-motion: reduce)` guard zeroing
   animation/transition durations app-wide (glyph spin already had a local
   guard). Offline banner gained a Retry button (`retryHealth` bumps a nonce
   that re-runs the existing `pingHealth` effect immediately and restarts the
   10s interval), with danger-toned outline styling within the banner.
6. **glib triage** — see below.

## Security triage: GHSA-wrw7-89jp-8q8g (glib < 0.20, moderate, repo alert #49)

**Outcome: NOT fixable by a lockfile bump today; glib stays at 0.18.5.**

- `cargo update -p glib` → "Locking 0 packages" (0.18.5 is already the newest
  version satisfying the in-tree requirement `^0.18`). Lockfile unchanged.
- `cargo update -p glib --precise 0.20.12` → resolver error, verbatim chain:
  `glib = "^0.18"` is **required by `gtk v0.18.2`**, which satisfies
  `gtk = "^0.18"` **of `tauri v2.11.2` itself** (and transitively the whole
  Linux webview stack in the lock: `webkit2gtk 2.0.2`, `gdk`, `soup3`,
  `javascriptcoregtk`, `atk`, `pango`, `gdkx11`, `gdkwayland` — all gtk-rs
  0.18-series).
- **What would unlock it:** Tauri/wry releasing a version built on the gtk-rs
  0.20+ bindings (glib ≥ 0.20) or a non-GTK Linux webview backend. The gtk3-rs
  binding series used by Tauri v2 is in maintenance and stops at glib 0.18, so
  this is an upstream Tauri major change, not something this repo can pin its
  way out of. Re-check on future `cargo update` runs after Tauri minor/major
  releases; when `tauri > 2.11.x` stops requiring `gtk ^0.18`, a plain
  `cargo update` will pull glib ≥ 0.20 and the alert closes.
- **Exposure:** the advisory (RUSTSEC-2024-0429) is an unsoundness in glib's
  `VariantStrIter`; the M.U.S.E. shell does not use `glib` APIs directly —
  exposure is limited to whatever Tauri/GTK does internally on Linux. Moderate,
  not remotely triggerable through the shell's surface (no custom protocol
  handlers beyond Tauri defaults, no direct variant parsing).
- Per the grain instructions, no incompatible versions were forced and the
  no-op attempt left the lock exactly as the plugin-addition resolution wrote it.

## Validation

- `npm --prefix apps/desktop/ui ci` → green, 0 vulnerabilities.
- `npm --prefix apps/desktop/ui run build` (`tsc -b && vite build`) → green
  (`✓ built in 2.02s`, PWA precache generated).
- `cargo check` in `apps/desktop/src-tauri` (cargo 1.94.1, with
  libwebkit2gtk-4.1-dev/libgtk-3-dev installed) →
  `Finished 'dev' profile ... in 1m 35s`, exit 0 — so CI `Tauri check (cargo)`
  is corroborated locally, not just delegated.
- `python3 -m json.tool capabilities/default.json` → parses.
- `python3 scripts/scan_secrets.py --base origin/main` → exit 0.
- `tokens.css` diff vs base → byte-identical (untouched).

## Residual / follow-on

- glib 0.18.5 remains in the lock (see triage above) — revisit on each Tauri
  upgrade; closes automatically once Tauri drops `gtk ^0.18`.
- The About item uses the native dialog; macOS shows it under the app menu,
  Linux/Windows render Tauri's fallback — no custom About window was built
  (out of scope for this grain).
- Keyboard shortcuts are webview-level (App.tsx), not native accelerators, so
  they work only when the window is focused — acceptable for route switching.
