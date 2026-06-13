# Release & Download (v1.5)

How the MUSE APK is built, signed, published, and installed — and which
steps are owner-gated.

## Build & download paths

| Path | Workflow | Output | Signing |
|---|---|---|---|
| Every change | `.github/workflows/android-build.yml` | `hermes-agent-debug-apk` artifact (14 days) | debug |
| Rolling latest | `.github/workflows/android-release.yml` (on `main` / release branch) | `android-latest` GitHub Release → `jarvis-prime-android.apk` (stable URL) | release if configured, else debug |
| Versioned | tag `android-v*` | `jarvis-prime-<ver>.apk` GitHub Release asset (90 days) | release if configured, else debug |

Direct download (rolling):
`https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent/releases/download/android-latest/jarvis-prime-android.apk`

Install: download on the phone → open → allow installs from this source if
prompted → launch **MUSE**. Requires Android 8.0+ (API 26).

## Signing status (what the app/release shows honestly)

| State | Meaning |
|---|---|
| **Unsigned / debug** | No release keystore configured; APK is debug-signed and labelled as such. Installable via sideload; Android may warn "unknown developer". |
| **Signed release** | The four secrets are set; the APK is properly release-signed. |
| **Missing signing secrets** | Named below; the workflow does **not** fail — it falls back to debug signing. |

## Owner-gated step: release signing secrets

Set these four **repository secrets** (Settings → Secrets and variables →
Actions). They are referenced by **name** only — never commit their values:

- `ANDROID_KEYSTORE_BASE64` — `base64 -w0 jarvis-release.jks`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

Generate the keystore once (see
[`RELEASE_SIGNING.md`](RELEASE_SIGNING.md)). This is the only blocker to a
properly-signed download; everything else (build, rolling release, install
instructions) works today with debug signing.

## Local build

```bash
bash scripts/setup-android-sdk.sh        # one-time SDK provision (needs dl.google.com)
export ANDROID_HOME="$HOME/android-sdk"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
export LC_ALL=C.UTF-8                     # so the Kotlin test compile handles UTF-8 test names
cd apps/android
./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

Do **not** request, paste, or commit keystore material. Releasing, merging,
and Play submission stay owner actions.

## In-app Release Center

Settings → **"Release & download"** surfaces this honestly on-device: the
running build's version + build type + application id, the rolling download
link (copyable), the signing model (the four secret **names** below, never
values), and the paired backend's version/capabilities. It deliberately shows
no live CI/PR status — that needs a configured GitHub token (not wired) — rather
than fabricating one.

## Keeping `android-latest` in sync with `main`

The `android-latest` download is also refreshed by the repo-wide
[`Sync main to releases`](../../../docs/releases/sync-main-to-releases.md)
engine — an hourly auto-sync (and the `muse sync` button) dispatches the
Android release workflow in rolling mode so the channel tracks `main` even for
changes that don't touch `apps/android/**`.

## CI notes

The `Unit tests` job (`testDebugUnitTest`) can intermittently flake on a few
pre-existing timing-sensitive tests that drive real `DataStore` / file IO and
poll wall-clock time via the shared `awaitUntil` helper (5s default) — e.g.
`AvatarPickerViewModelTest`. These pass deterministically locally; under a
loaded CI runner the poll can occasionally time out. A re-run clears it. The
flake is independent of app behaviour (no production code path is involved).
