# Hermes Agent — Android (native companion app)

> **Status:** alpha. The Android app supports three connection modes:
> **Direct Personal API Mode** (phone-only, recommended for personal use),
> **Hermes Gateway Mode** (talks to a Hermes gateway you run elsewhere),
> and **Mock Mode** (offline UI sandbox). See
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

The Android app supports three modes, switchable at runtime in **Settings →
Edit connection**:

### 1. Direct Personal API Mode (recommended for personal use)

The phone calls an OpenAI-compatible provider (OpenRouter, OpenAI, or any
custom OpenAI-compatible endpoint) directly with an API key you paste in.
**No backend server is required.** This is the recommended path if you
just want to chat from your phone.

The key is stored in **EncryptedSharedPreferences** on this device only
(see `SecureKeyStore.kt`), is excluded from Auto Backup and Device
Transfer (`backup_rules.xml`, `data_extraction_rules.xml`), and is sent
only as a `Bearer` token to the configured provider URL.

**Phone-only setup (no server required):**

1. Install the latest debug APK on the phone (see [Building](#building))
   or download it from the GitHub Actions `hermes-agent-debug-apk`
   artifact.
2. Open **Hermes Agent** → on the welcome screen tap **"Use AI directly
   from this phone"** (the recommended card).
3. The AI Connection screen opens with **Direct API** pre-selected.
4. Pick **OpenRouter** (or **OpenAI**, or **Custom** with your own base
   URL). OpenRouter is the easiest because one key works against many
   models.
5. Paste your API key into the **API key** field. Tap the eye icon to
   reveal/hide; tap × to clear.
6. Pick a model from the recommended chips, or type one in the text box.
   The default is `openai/gpt-4o-mini` for OpenRouter, `gpt-4o-mini` for
   OpenAI direct.
7. Tap **Test direct API connection**. The app will:
   - call `GET /models` on the provider to verify the API key, then
   - call `POST /chat/completions` with a tiny test prompt
     (`Reply with exactly: Hermes direct mode is working.`)
   - and verify the response contains useful assistant text.
8. On success it remembers the model as the **last working model**
   (you can switch to a different model and come back to it with one
   tap). On failure it tells you whether the API key, the model, account
   credits, or your phone's network is likely the cause.
9. Tap **Save and continue** → you land in **Chat**. Type a message,
   send.

> If the app still says **"Connect to Hermes"** with a gateway URL on
> the welcome screen, you have an **old APK installed**. Uninstall the
> previous build (or install the new `.debug` variant alongside it) and
> launch again — the three-card welcome flow is the new shipping path.

### 2. Hermes Gateway Mode (advanced)

The app talks to a Hermes gateway you already run somewhere:

- On your **home server / VPS**, with the public Hermes install one-liner.
- On your **phone** under **Termux**, using `pkg install ... && curl ... | bash`
  and then `hermes gateway start`.
- On a friend's server you have a bearer token for.

The Android app POSTs to `/v1/chat` and reads `/v1/health`. See
[`docs/ARCHITECTURE.md#wire-format`](docs/ARCHITECTURE.md#wire-format).

This mode inherits everything Hermes already does — skill loop, memory,
tools, model switching — without duplicating it in Kotlin. Use it when
you want the full agent stack, not just chat.

> **Direct embedding of the Python runtime inside the APK** is **not**
> supported. CPython on Android requires a Termux-style userland with a
> full POSIX toolchain (clang, rust, openssl), which the Android app
> sandbox cannot provide. The pragmatic native install on Android is
> "APK + Termux gateway", not "APK with embedded Python."

### 3. Mock Mode (UI sandbox)

For UI development and demos, **mock mode** can be toggled on. In this
mode the app does not make any network calls and instead streams canned
responses locally. This makes the whole UI navigable without a backend.

---

## Native APK limitations (read this before filing issues)

- **No embedded Python runtime.** See above — Android sandboxes can't run
  CPython directly. Use Termux gateway mode if you want the whole stack on
  one device.
- **Skill execution, tool use, memory, cron scheduling, and the Hermes
  learning loop** are gateway-side features. In **Direct API mode** the
  phone is a thin chat client against an OpenAI-compatible provider —
  there are no Hermes skills/tools/memory in this path.
- **Voice features** (`.[voice]` extra) require backends not available on
  Android. Hermes itself uses `.[termux]` instead of `.[all]` for the same
  reason.
- **Cleartext HTTP** is enabled (`usesCleartextTraffic="true"`) to allow
  pointing at `http://10.0.2.2:8080` (emulator → host) and at LAN gateways
  during development. Production gateways should use HTTPS; we plan to
  flip this off by default before a 1.0 Play Store release. Direct API
  mode against OpenRouter / OpenAI is always HTTPS — there's no cleartext
  in the personal path.

---

## Direct Personal API Mode — security notes

- API keys are stored in `EncryptedSharedPreferences` under a hardware-backed
  master key when available (AES256_GCM aead, AES256_SIV index). The
  file is `hermes_secure_prefs.xml` in the app's private data dir.
- The keys are **excluded from Auto Backup and Device Transfer** so they
  cannot leak to another device via Google's transfer flows.
- API keys are **never** written to the in-app log buffer, the
  diagnostics export (clipboard "Copy logs"), Logcat, or crash text. The
  only place they appear is as a `Bearer` value on the outgoing
  Authorization header, and that is not serialised anywhere.
- The API key field is **masked by default** with an eye toggle and a
  clear-input button.
- Direct API mode is intended for **personal use on a phone you own**.
  Do not embed your key in a build distributed to others.

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
`applicationIdSuffix=".debug"` (so it installs alongside any release
build), and ships with **mock mode enabled as the default** so you can
poke around without a backend. On first launch you'll see the three-card
welcome screen — pick **"Use AI directly from this phone"** to switch
into Direct API mode.

### Tests and lint

JVM unit tests cover the form validation, suggested-model heuristics,
and the Direct API tester's HTTP error mapping (driven against an
in-process `MockWebServer`):

```bash
./gradlew testDebugUnitTest
./gradlew lintDebug
```

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

## First run on device

1. Launch **Hermes Agent**. You'll see a brief splash, then the welcome
   screen titled **"Use Hermes on this phone."**
2. Pick one of the three cards:
   - **Use AI directly from this phone — recommended.** Opens the AI
     Connection screen pre-selected to Direct API. Pick a provider,
     paste your key, optionally pick a model, **Test**, then **Save and
     continue**.
   - **Explore demo mode — no API key.** Flips into Mock mode and lands
     you in Chat with canned replies.
   - **Connect to Hermes Gateway — advanced.** Opens the AI Connection
     screen pre-selected to Hermes Gateway. Enter the gateway URL (and
     optional bearer token), **Test connection**, then **Save and
     continue**.
3. Tap **Save and continue** — you land in **Chat**.
4. To change modes later: top-right **Settings** icon → **Edit connection**.

---

## On-device manual test checklist

After installing a fresh `app-debug.apk`:

- [ ] First launch shows the new three-card welcome ("Use Hermes on this
      phone") — NOT the old "Get started / Skip and use mock mode" pair.
      If you see the old screen, an older `.debug` install is shadowing
      the new one.
- [ ] **Try demo mode** card → lands in Chat → `hello` returns a canned
      reply within 2 seconds.
- [ ] **Use AI directly** card → AI Connection opens with Direct API
      pre-selected and OpenRouter chip highlighted.
- [ ] Paste a *valid* OpenRouter key → tap **Test direct API connection**
      → ✓ "Connected to OpenRouter — openai/gpt-4o-mini replied OK." within
      ~3 seconds. **Last working model** appears below the chips.
- [ ] Paste an *invalid* key (e.g. flip one character) → Test → ✗
      "OpenRouter rejected the API key…" within ~3 seconds.
- [ ] Type a clearly non-existent model id (e.g. `openai/gpt-deleted`) →
      Test → ✗ "Model \"openai/gpt-deleted\" was not found…"
- [ ] Tap **Reset to recommended model** → model field flips back to
      `openai/gpt-4o-mini`.
- [ ] Toggle the API key field eye icon → key visible/masked. Tap × →
      key cleared. Test now reports "Enter your API key to test."
- [ ] Save and continue → Chat → send a real message → streaming reply.
- [ ] Open **Status** (top-right Insights icon) → mode = "Direct API",
      Model = the one you saved, no Gateway URL row.
- [ ] Open **Diagnostics** (bug icon) → backend OK, Connection mode =
      Direct API, no Gateway URL row (because Direct + OpenRouter uses a
      hard-coded base URL).
- [ ] Switch back to **AI Connection** → pick **Custom** provider → the
      custom base URL field appears, **separate from any old gateway URL
      value**.
- [ ] **Copy logs** in Diagnostics → paste somewhere → confirm the API
      key string never appears in the log dump.
- [ ] Airplane mode on → Test direct API → ✗ "Can't reach OpenRouter…"
      within the per-call timeout (≤20 seconds, not infinite).
- [ ] Settings → **Reset all settings** → confirm → back at three-card
      welcome, all keys gone.

---

## Screens

| Route | Purpose |
|---|---|
| `splash` | Branding + theme bootstrap |
| `setup` | Three-card welcome (Direct / Demo / Hermes Gateway) |
| `provider` | AI Connection editor — Direct API or Hermes Gateway fields, test + save. Accepts an optional `?mode=DIRECT\|HERMES\|MOCK` arg from Setup. |
| `chat` | Streaming chat (user/assistant bubbles, abort button, new convo) |
| `status` | Live connection state + provider/model + mode-aware URL row |
| `settings` | Connection summary, theme, build info, full reset |
| `diagnostics` | Backend status, app version, build type, last error, in-app log buffer |

---

## What's not wired up yet

- **Push from gateway → device.** Notifications path is permitted in the
  manifest but no FCM/WebPush integration exists.
- **Skill picker UI.** `/skills` from the CLI doesn't have a mobile-native
  equivalent yet — you can still invoke `/skill-name` in the chat input
  in Hermes Gateway mode. Direct API mode has no skills (it's a plain
  OpenAI-compatible chat client).
- **Voice input.** Future work; needs careful permission flow.
- **Release signing.** The release build type compiles but is not signed
  by default — see "Release AAB" above.
- **HTTPS-only.** Cleartext is on for local-network testing; a future
  build will gate it behind a build flag. Direct API mode against
  OpenRouter / OpenAI is always HTTPS regardless of this flag.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the gateway wire
format and the deliberate split between this Android module and the
Python core.
