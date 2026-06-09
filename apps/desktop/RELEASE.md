# Releasing the M.U.S.E. desktop app

The desktop app (Tauri v2, this directory) is built and published by
[`.github/workflows/muse-desktop-release.yml`](../../.github/workflows/muse-desktop-release.yml).
It produces native installers for **macOS** (`.dmg`), **Windows** (`-setup.exe`,
NSIS) and **Linux** (`.AppImage` + `.deb`) and uploads them to a GitHub Release.

Like the Android lane, **signing is entirely secret-driven** — nothing sensitive
lives in the repo, and **builds succeed unsigned** when secrets are absent (clearly
marked in the release notes), so forks and first bring-up are never blocked.

## Cutting a release

- **One button (recommended):** Actions → *MUSE desktop release* → *Run workflow*
  with **no input**. Cuts a permanent versioned release auto-stamped
  `0.1.<commit-count>` — no tag to type.
- **Hand-named version:** push a tag `muse-desktop-v1.2.3` (or set the dispatch
  `tag` input).
- **Rolling latest:** every push to `main` that touches `apps/desktop/**` refreshes
  the prerelease tag `muse-desktop-latest` so there's always a current download at a
  stable URL.

The bundle version is a valid semver `0.1.<commit-count>` (the `0.1` line is the
bring-up default — bump it in the workflow's `meta` step when you're ready). The
app's `tauri.conf.json` stays at `0.1.0`; the CI version is injected via a
`--config` merge at build time.

## Code-signing (optional — unsigned otherwise)

Add these repository secrets (Settings → Secrets and variables → Actions) to get
signed installers. Until then, installers are **unsigned** and the OS will warn about
an unknown developer (macOS Gatekeeper / Windows SmartScreen); they still install via
the normal "open anyway" path.

**macOS** (Developer ID Application cert + notarization):
- `APPLE_CERTIFICATE` — base64 of the `.p12` Developer ID Application certificate
- `APPLE_CERTIFICATE_PASSWORD` — its export password
- `APPLE_SIGNING_IDENTITY` — e.g. `Developer ID Application: Your Org (TEAMID)`
- `APPLE_ID`, `APPLE_PASSWORD` (app-specific password), `APPLE_TEAM_ID` — for notarization

**Windows** (Authenticode): provide a cert and set Tauri's Windows signing config
(`bundle.windows.certificateThumbprint` in `tauri.conf.json`, or the equivalent env).
EV/OV certs avoid SmartScreen warnings.

There is no `REQUIRE_*_SIGNING` hard-gate yet (the Android lane has one): add a guard
step in the `build` job keyed on a `REQUIRE_DESKTOP_SIGNING` repo variable if you want
tagged releases to fail rather than publish unsigned.

## Auto-update (not enabled yet)

Self-update via `tauri-plugin-updater` is **deliberately deferred** to the
update-check phase because it requires a signing keypair you provision:

1. `tauri signer generate -w ~/.tauri/muse-updater.key` (keep the private key safe).
2. Commit the **public** key to `tauri.conf.json` under `plugins.updater.pubkey`.
3. Add `TAURI_SIGNING_PRIVATE_KEY` (+ `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`) secrets and
   set `bundle.createUpdaterArtifacts: true` so the release emits the `.sig` sidecars +
   `latest.json` the updater reads.

Until then, the app installs and runs normally; users update by downloading the latest
installer.
