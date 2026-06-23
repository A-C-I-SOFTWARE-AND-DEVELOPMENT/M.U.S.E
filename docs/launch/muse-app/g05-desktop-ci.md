# G0.5 — Desktop CI lane

Swarm builder grain snapshot.

## Intent

Add a self-contained GitHub Actions workflow that gates changes to the muse
desktop app (`apps/desktop/`, a Tauri v2 shell + Vite/React client) on CI. The
app previously had no CI. The workflow runs only when desktop sources — or the
workflow file itself — change.

Two jobs, both on `ubuntu-latest`:

- **ui-build** — the cheap, fast gate. Sets up Node 22 with npm caching keyed on
  `apps/desktop/ui/package-lock.json`, then runs `npm ci` and `npm run build`
  in `apps/desktop/ui` (the build script is `tsc -b && vite build`).
- **tauri-check** — compiles the Rust shell. Installs the WebKitGTK / GTK system
  libraries the Tauri `*-sys` crates probe for via `pkg-config` (without them the
  build fails at the probe, not at Rust compile time), sets up the stable Rust
  toolchain, caches the Cargo build keyed on `apps/desktop/src-tauri`, then runs
  `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`.

## Owned files

- `.github/workflows/muse-desktop.yml` (new) — the workflow.
- `docs/launch/muse-app/g05-desktop-ci.md` (this snapshot).

No other files were created or modified.

## Branch / base

- Branch: `claude/muse-app-g05-desktop-ci`
- Base commit (`git rev-parse origin/main`): `d4c66c0927ea904187b697135111b75d1e2ca77e`

## Action versions (pinned by major)

- `actions/checkout@v4`
- `actions/setup-node@v4` (node-version `22`, `cache: npm`,
  `cache-dependency-path: apps/desktop/ui/package-lock.json`)
- `dtolnay/rust-toolchain@stable`
- `Swatinem/rust-cache@v2` (`workspaces: apps/desktop/src-tauri`)

## Validation

All performed before push, in this sandbox.

- **YAML parse:** `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/muse-desktop.yml'))"`
  parses cleanly. Structural check confirms two jobs (`ui-build`, `tauri-check`),
  both `runs-on: ubuntu-latest`; `push` + `pull_request` triggers each filtered to
  `paths: ['apps/desktop/**', '.github/workflows/muse-desktop.yml']`;
  `permissions: contents: read`.
  (Note: PyYAML 1.1 normalizes the bare `on:` key to the boolean `True`; this is a
  PyYAML quirk, not a defect in the file — GitHub Actions reads `on` as the trigger
  key. The trigger content was verified present and correct.)
- **UI build (matches the workflow exactly):** `npm ci` (added 354 packages,
  0 vulnerabilities) then `npm run build` in `apps/desktop/ui` — `tsc -b && vite build`
  succeeded, emitting `dist/` (index.html, assets, PWA manifest + service worker).
  Confirms the command and `package-lock.json` are correct.
- **Tauri check (matches the workflow exactly):** the WebKitGTK libs were already
  present in the sandbox (`pkg-config --exists webkit2gtk-4.1` → present), so
  `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml` was run directly
  and finished cleanly (`Finished dev profile` after compiling `muse-desktop`).
- Toolchain in sandbox: Node v22.22.2, npm 10.9.7, cargo 1.94.1.

## Residual risks

- **apt package availability on the GitHub runner.** The `apt-get install` list
  (`libwebkit2gtk-4.1-dev libgtk-3-dev libsoup-3.0-dev librsvg2-dev
  libayatana-appindicator3-dev pkg-config`) is the line that works locally and is
  the documented set for current `ubuntu-latest` (Ubuntu 24.04, which ships the
  4.1 / soup-3 packages). If GitHub later moves `ubuntu-latest` to a release where
  these package names change, the install step would need updating — same exposure
  as any Tauri Linux CI.
- **`sudo` in the install step.** Standard on GitHub-hosted runners; would need
  adjusting only for a rootless self-hosted runner.
- **No Tauri bundling / multi-OS matrix.** This grain intentionally implements the
  fast PR gate (UI build + `cargo check` on Linux), per the README's CI note. Full
  `cargo tauri build` and a macOS/Windows/Linux installer matrix are out of scope
  and can be layered on later without touching this workflow.
- The workflow is additive and only triggers on `apps/desktop/**` (or itself), so
  it cannot affect any other lane's CI.
