# Hermes Agent — Android (native companion app)

> **Status:** alpha. The Android app is a **native companion** to a running
> Hermes backend (CLI/gateway). It is intentionally *not* a wrapped webview
> and not a port of the full desktop terminal UX — see
> [Runtime modes](#runtime-modes) below.

This module contains the native Android app shell for Hermes Agent.

- **Package:** `com.aci.hermes`
- **App name:** Hermes Agent
- **min SDK:** 26 (Android 8.0)  
- **target SDK / compileSdk:** 35
- **Language / UI:** Kotlin + Jetpack Compose (Material 3)
- **Architecture:** MVVM, hand-rolled DI ([`AppContainer`](app/src/main/java/com/aci/hermes/di/AppContainer.kt))
- **Networking:** OkHttp + OkHttp-SSE, kotlinx-serialization
- **Settings:** Jetpack DataStore for non-secrets, EncryptedSharedPreferences for API keys/tokens

The rest of this README covers builds, runtime modes, and what is and isn't
wired up yet. Architecture details live in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Runtime modes

The Android app supports two modes, switchable at runtime in **Settings →
Connection**:

### 1. Remote Hermes gateway mode (recommended)

The app talks to a Hermes gateway you already run somewhere:

- On your **home server / VPS**, with the public Hermes install one-liner.
- On your **phone** under **Termux**, using `pkg install ... && curl ... | bash`
  and then `hermes gateway start`.
- On a friend's server you have a bearer token for.

The Android app POSTs to `/v1/chat` and reads `/v1/health`. See
[`docs/ARCHITECTURE.md#wire-format`](docs/ARCHITECTURE.md#wire-format).

This is the recommended mode because it inherits everything Hermes already
does — skill loop, memory, tools, model switching — without duplicating it
in Kotlin.

### 2. Local Android/Termux-compatible mode

If the user runs `hermes gateway start` inside Termux on the *same device*,
the Android app can point at `http://127.0.0.1:8080`. The two processes share
the device but live in different sandboxes — they only talk over loopback
HTTP. This works today.

> **Direct embedding of the Python runtime inside the APK** is **not**
> supported. CPython on Android requires a Termux-style userland with a full
> POSIX toolchain (clang, rust, openssl), which the Android app sandbox
> cannot provide. The pragmatic native install on Android is "APK + Termux
> gateway", not "APK with embedded Python."

### 3. Mock mode (UI sandbox)

For UI development and demos, **mock mode** can be toggled on. In this mode
the app does not make any network calls and instead streams canned responses
locally. This makes the whole UI navigable without a gateway running.

---

## Native APK limitations (read this before filing issues)

- **No embedded Python runtime.** See above — Android sandboxes can't run
  CPython directly. Use Termux gateway mode if you want the whole stack on
  one device.
- **Skill execution, tool use, memory, cron scheduling, and the Hermes
  learning loop run on the gateway side**, not in the Android process. The
  app is a thin client.
- **Voice features** (`.[voice]` extra) require backends not available on
  Android. Hermes itself uses `.[termux]` instead of `.[all]` for the same
  reason.
- **Cleartext HTTP** is enabled (`usesCleartextTraffic="true"`) to allow
  pointing at `http://10.0.2.2:8080` (emulator → host) and at LAN gateways
  during development. Production gateways should use HTTPS; we plan to
  flip this off by default before a 1.0 Play Store release.

---

## Building

### Prerequisites

- **JDK 17** (Temurin recommended).
- **Android SDK** with platform `android-35` and build-tools `35.0.0`.
  Android Studio Ladybug | 2024.2.x or newer installs these automatically.

### Debug APK

From the repository root:

```bash
cd apps/android
./gradlew assembleDebug
```

The unsigned debug APK lands at:

```
apps/android/app/build/outputs/apk/debug/app-debug.apk
```

Install on a connected device or emulator:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The debug build is keyed with the standard Android debug keystore, has
`applicationIdSuffix=".debug"` (so it installs alongside any release build),
and ships with **mock mode enabled by default** so you can poke around
without a backend.

### Release AAB for Google Play

You need a release signing keystore. **Do not commit it.**

```bash
keytool -genkey -v \
  -keystore hermes-release.keystore \
  -alias hermes \
  -keyalg RSA -keysize 2048 -validity 36500
```

Create `apps/android/keystore.properties` (already in `.gitignore`):

```properties
storeFile=/absolute/path/to/hermes-release.keystore
storePassword=...
keyAlias=hermes
keyPassword=...
```

Wire up signing in `app/build.gradle.kts` (left as a TODO — we don't ship
sample release-signing code so nobody accidentally checks it in), then:

```bash
./gradlew bundleRelease
```

The signed bundle lands at:

```
apps/android/app/build/outputs/bundle/release/app-release.aab
```

Upload that file to the Google Play Console.

### CI

`.github/workflows/android-build.yml` builds the debug APK on every change
under `apps/android/` and uploads it as a workflow artifact (`hermes-agent-debug-apk`).
A separate lint job uploads `lint-results-debug.html`. Manual trigger is also
supported via `workflow_dispatch`.

---

## First run (on device)

1. Launch **Hermes Agent**. You'll see a brief splash, then onboarding.
2. Pick **"Get started"** to enter your gateway URL, or **"Skip and use
   mock mode"** to explore the UI offline.
3. On the connection screen, enter:
   - **Gateway URL** — e.g. `https://hermes.example.com`, `http://10.0.2.2:8080`
     (emulator → host loopback), or `http://127.0.0.1:8080` (Termux on
     same device).
   - **Gateway token** — optional bearer token configured on the gateway.
   - **Provider + API key** — defaults to OpenRouter. The key is forwarded
     to the gateway in an `X-Hermes-Provider-Key` header.
4. Tap **Test connection** to hit `/v1/health`. Green = good.
5. Tap **Save and continue** — you land in **Chat**.

---

## Screens

| Route | Purpose |
|---|---|
| `splash` | Branding + theme bootstrap |
| `setup` | Welcome / onboarding entry |
| `provider` | Gateway URL, token, provider/API key, mock toggle, test connection |
| `chat` | Streaming chat (user/assistant bubbles, abort button, new convo) |
| `status` | Live connection state + provider/model + mock indicator |
| `settings` | Theme, mock toggle shortcut, build info, full reset |
| `diagnostics` | Backend status, app version, build type, last error, in-app log buffer |

---

## What's not wired up yet

- **Push from gateway → device.** Notifications path is permitted in the
  manifest but no FCM/WebPush integration exists.
- **Skill picker UI.** `/skills` from the CLI doesn't have a mobile-native
  equivalent yet — you can still invoke `/skill-name` in the chat input.
- **Voice input.** Future work; needs careful permission flow.
- **Release signing.** The release build type compiles but is not signed by
  default — see "Release AAB" above.
- **HTTPS-only.** Cleartext is on for local-network testing; a future build
  will gate it behind a build flag.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the gateway wire
format and the deliberate split between this Android module and the Python
core.
