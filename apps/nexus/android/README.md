# NEXUS — native Android app (WebView shell)

A thin, native Android wrapper that turns the **NEXUS PWA** into a **true
installable app**: its own launcher icon, full-screen (no browser chrome), and
real **device access** — camera, microphone, location, file upload/download, and
notifications — granted through the WebView's permission bridges. Tap the icon and
NEXUS opens like any native app.

This is distinct from the two other Android surfaces in the repo:

- **`apps/android/`** — the full native Hermes/MUSE cockpit (Compose UI).
- **`apps/nexus/companion-android/`** — a background daemon (notifications, widget,
  share target) that *opens* the PWA.

This module simply **is** NEXUS, rendered natively.

## What it loads

By default it loads the GitHub Pages deploy
`https://a-c-i-software-and-development.github.io/M.U.S.E/`. Override at build time:

```sh
NEXUS_URL="http://127.0.0.1:8765/nexus/" ./gradlew :app:assembleDebug   # local Termux gateway
```

## Build

Requires the Android SDK (`platforms;android-34`, `build-tools;34.0.0`) + JDK 17.

```sh
cd apps/nexus/android
./gradlew :app:assembleDebug
# → app/build/outputs/apk/debug/app-debug.apk  (debug-signed, sideloadable)
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Download (CI)

Every push to `main` touching `apps/nexus/android/**` (or a manual
**Actions → "NEXUS Android" → Run workflow**) builds a debug-signed APK, uploads it
as a workflow artifact, and refreshes the rolling **`nexus-android-latest`**
release:

`https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/releases/download/nexus-android-latest/nexus-android.apk`

Debug-signed = installable via sideload (Android may warn about an "unknown
developer"); add the `ANDROID_KEYSTORE_*` secrets to release-sign it. Requires
Android 8.0+ (API 26).
