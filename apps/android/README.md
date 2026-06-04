# Hermes Agent — Android (JARVIS Prime cockpit)

> **Status:** alpha. The Android app is the **JARVIS Prime cockpit**: a
> networked review-and-control client for a Hermes **cockpit gateway**. When
> paired, it talks to the gateway over HTTP with a bearer token — streaming
> chat, jobs, approvals, evidence/research, autonomy, and voice intake — and
> never proxies a model provider or holds a provider API key (those live on
> the gateway). When **unpaired** (no backend configured), it falls back to a
> local **handoff** mode: it organizes work for the official AI tools you
> already subscribe to (Codex, Claude Code, ChatGPT, Claude) and hands off via
> clipboard, deep links, or the Termux bridge.

## ⬇️ Download & install (sideload)

The latest build is published as a downloadable APK on the
[**`android-latest` release**](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent/releases/tag/android-latest):

- Direct link: **[jarvis-prime-android.apk](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent/releases/download/android-latest/jarvis-prime-android.apk)**

To install: open the link on your phone, download the `.apk`, tap it, and
allow installs from this source if Android prompts. Requires **Android 8.0+
(API 26)**, arm64-v8a / armeabi-v7a. The build is refreshed automatically by
the [`Android release`](../../.github/workflows/android-release.yml) workflow
on every change under `apps/android/`. Tagged versions (`android-v*`) get their
own permanent, versioned release. Until the release-signing secrets are
configured the APK is debug-signed — still installable; Android may flag it as
from an "unknown developer." See [`docs/RELEASE_SIGNING.md`](docs/RELEASE_SIGNING.md).

---

This module is the native Android shell.

- **Package:** `com.aci.hermes`
- **App name:** Hermes Agent
- **min SDK:** 26 (Android 8.0)
- **target SDK / compileSdk:** 35
- **Language / UI:** Kotlin + Jetpack Compose (Material 3)
- **Architecture:** MVVM with hand-rolled DI ([`AppContainer`](app/src/main/java/com/aci/hermes/di/AppContainer.kt))
- **Persistence:** Jetpack DataStore (`hermes_settings`) for non-secret prefs + a single JSON file (`hermes_tasks.json`) in `filesDir`; the cockpit bearer token lives in `EncryptedSharedPreferences`
- **Networking:** a hand-rolled HTTP client over the JDK's `HttpURLConnection` (no OkHttp / Retrofit / Ktor dependency) — `HermesCockpitClient` for the `/v1/cockpit/*` REST routes and `HttpJarvisChatGateway` for the `POST /v1/jarvis/chat` NDJSON stream. Default endpoint `http://127.0.0.1:8765`, configurable in Settings.

Architecture details live in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## What the app does

**Paired (networked cockpit) — the mainline:**

1. **Pairs** to a Hermes cockpit gateway: set the endpoint and paste the
   gateway's bearer token (stored in `EncryptedSharedPreferences`).
2. **Streams chat** with JARVIS Prime over `POST /v1/jarvis/chat` (NDJSON), and
   reads/controls **jobs, approvals, evidence/research, memory, autonomy, and
   diagnostics** over the `/v1/cockpit/*` REST routes.
3. **Submits voice** by transcribing on-device and posting the transcript to
   `POST /v1/cockpit/voice/intake` — the audio never leaves the phone.
4. **Surfaces approvals** as owner-gated cards: high-risk actions need an
   explicit decision; there is no one-tap approve.
5. Keeps a **foreground service** (`HermesService`) with a persistent
   notification (start/stop) and a work watcher that **polls** the cockpit for
   job / approval transitions.

**Unpaired (local handoff) — the fallback:**

6. Lets you draft **tasks** and renders a **handoff prompt** with a fixed
   `## Safety requirements` block (no auth bypass, no token exfiltration, stay
   within ToS), then **copies** it to the clipboard on an explicit tap (no
   silent handoff) and optionally **opens** the official tool (Codex / Claude
   Code / ChatGPT / Claude) when *Allow external app opening* is on.
7. Surfaces an in-memory **diagnostics** log (ring buffer, 200 entries) and a
   **full reset** that clears DataStore, the encrypted token, and the task file.

## What the app explicitly does **not** do

- It does **not** call OpenAI, Anthropic, OpenRouter, or any other AI
  provider **directly**. It talks only to the Hermes cockpit gateway; the
  gateway holds the provider API keys (`~/.hermes/.env`) and makes the
  provider calls. No provider key or URL is injected at build time.
- It does **not** store provider API keys, session tokens, or cookies. The
  **only** secret it holds is the **cockpit bearer token**, in
  `EncryptedSharedPreferences` (hardware-backed master key when available).
- It does **not** auto-approve. Owner-gated actions (publish, deploy, merge,
  destructive commands) require an explicit decision in the Approvals queue.
- It does **not** hand off silently. The clipboard / deep-link handoff (the
  unpaired fallback) happens only on an explicit tap, and external-app opening
  only when *Allow external app opening* is on.

---

## Building

### Prerequisites

- **JDK 17** (Temurin recommended).
- **Android SDK** with platform `android-35` and build-tools `35.0.0`.
  Android Studio Ladybug | 2024.2.x or newer installs these
  automatically.

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

The debug build uses `applicationIdSuffix=".debug"` (so it installs
alongside any release build) and `versionNameSuffix="-debug"`.

### Unit tests

```bash
cd apps/android
./gradlew testDebugUnitTest
```

JVM unit tests live under `app/src/test/java/`. They cover the
pure-logic surfaces — `PromptBuilder`, `HermesTaskRepository`,
`HandoffLauncher`, `TermuxIntentBridge`, the safety-content
guarantee, and the backup-rules manifest assertions — plus a
**ViewModel test for every major screen** (`*ViewModelTest.kt`
next to each screen package; Robolectric where the ViewModel touches
`Context`/DataStore) and **Robolectric Compose smoke tests**
(`*SmokeTest.kt`) that render real screens on the JVM with no
emulator (`createComposeRule()` + `@GraphicsMode(NATIVE)`).

### Release AAB

You need a release signing keystore. **Do not commit it.**

```bash
keytool -genkey -v \
  -keystore hermes-release.keystore \
  -alias hermes \
  -keyalg RSA -keysize 2048 -validity 36500
```

Create `apps/android/keystore.properties` (already in `.gitignore`)
and wire signing in `app/build.gradle.kts` (left as a TODO — we don't
ship sample release-signing code so nobody accidentally checks it
in), then:

```bash
./gradlew bundleRelease
```

The signed bundle lands at
`apps/android/app/build/outputs/bundle/release/app-release.aab`.
Upload that to the Google Play Console.

### CI

`.github/workflows/android-build.yml` builds the debug APK and runs
the unit-test suite on every change under `apps/android/`. It
uploads the APK as a workflow artifact (`hermes-agent-debug-apk`)
and the test results as `android-unit-test-report`. A separate lint
job uploads `lint-results-debug.html`.

---

## First run (on device)

1. Launch **Hermes Agent**. A short splash bootstraps the theme,
   then the **Orchestrator** dashboard loads.
2. The persistent **Hermes Orchestrator Running** notification
   appears. Tap it once to come back to the app from anywhere; tap
   *Stop* to end the foreground service.
3. Tap **+** (new task) → enter a title, description, workspace
   path, and target tool → save.
4. Open the saved task → review the **Generated prompt** (it
   includes a `## Safety requirements` block that is invariant
   across targets).
5. Tap **Copy prompt**. The prompt is copied to the system
   clipboard. Paste it into Codex / Claude Code / ChatGPT / Claude
   in their official app or web client.
6. (Optional) Tap **Open tool** to launch the official app — only
   works if *Settings → Allow external app opening* is on, and even
   then each launch needs an explicit tap.

---

## Screens

| Route | Purpose |
|---|---|
| `splash` | Branding + theme bootstrap (no network calls) |
| `orchestrator` | Tool tiles, task list, service start/stop, prepare-handoff entry |
| `task_detail/{taskId}?target={target}` | Create / edit a task, render the handoff prompt, copy / mark-handed-off / delete |
| `settings` | Theme, preferred builder / reviewer, opt-in toggles (`Use API keys`, `Local-only mode`, `Allow external app opening`, `Clipboard handoff enabled`, `Show safety warnings`), full reset |
| `diagnostics` | App version, build type, last error, in-app log buffer (200 entries) |

---

## Notifications (long-running work)

Local Android notifications report when long-running work changes state —
**no FCM, no push backend.** A work watcher (`notify/`) polls the cockpit
REST endpoints (`jobs`, `approvals`, `runtime/workers`), diffs against the
last snapshot via the pure `WorkEventDetector`, and posts on transitions.

- **Events:** job started / blocked / completed / failed, approval required,
  worker needs attention, research complete, tests failed, emergency stop,
  plus the persistent voice "listening" notice.
- **Channels:** `jarvis_jobs` (default), `jarvis_approvals` (high),
  `jarvis_alerts` (high) — plus the existing `hermes_orchestrator` /
  `jarvis_voice` service channels.
- **Deep links:** tap → Approvals / Tasks / Diagnostics (or Voice), wired
  through `DeepLink.EXTRA_NAV_ROUTE` → `MainActivity` → `HermesNavHost`.
- **Polling lifetime:** the in-app poller runs only while the app is
  visible; `WorkWatchService` (foreground, `dataSync`) keeps polling for
  active work after backgrounding and **self-stops when idle**. There is no
  permanent always-on poller. Interval is the `Notification poll interval`
  setting (default 20s) with error backoff.
- **Safety:** approval notifications open the owner-gated Approvals queue
  (no one-tap approve); bodies are short, structural, and secret-redacted.

Pure logic (`WorkEventDetector`, `DeepLink`, `NotificationChannels`) is unit
tested under `app/src/test/.../notify/`. Roadmap: `MOBILE-NOTIFY-002` (SSE),
`MOBILE-NOTIFY-003` (opt-in FCM), `MOBILE-NOTIFY-004` (cockpit-job detail
screen for per-job deep links).

---

## Sentient avatar (the living body)

The cockpit now ships JARVIS Prime's **living body** — a character that
floats over your apps, physically operates the phone, and talks to you
hands-free. See [`docs/avatar/sentient-avatar-architecture.md`](../../docs/avatar/sentient-avatar-architecture.md).

- **Renderers** (`ui/screens/live/`): self-contained Compose bodies —
  animated pixel sprite (default), procedural humanoid character, orb
  fallback — selected by `DeviceCapability`. Rive/3D are documented
  drop-ins behind the same input contract.
- **Hands** (`service/JarvisAccessibilityService`): real taps/swipes,
  app launches, node-tree targeting.
- **Presence** (`service/JarvisOverlayService`): the floating overlay +
  the run/push/page-turn performance + the idle/sleep/wander life loop.
- **Voice** (`service/VoiceLoopService` + `voice/`): "Hey Jarvis" →
  STT → agent → TTS over a Bluetooth headset.
- **Create**: image/video generation and photo→avatar conversion are
  surfaced in the capability catalog (`create.*`).

## What's still rough / follow-up

- **Renderers are Compose-only.** Procedural character + animated sprite
  now; real **Rive**/3D bodies are documented drop-ins behind the same
  `AvatarInputs` contract
  ([`docs/avatar/rive-state-contract.md`](../../docs/avatar/rive-state-contract.md),
  [`res/raw/README.md`](app/src/main/res/raw/README.md)).
- **Voice engines** are interfaces with `Wiring` factory slots; the
  Porcupine/Vosk/TTS concrete impls bind in `AppContainer` as follow-up.
- **Live gateway** is wired (`AppContainer.liveJarvisChatGateway`, pure
  JDK `HttpURLConnection`) but defaults to the mock for offline-safe first
  run — flip `useLiveGateway` or bind it to a setting once the daemon runs.
- **Android build is not verified in CI here** (no SDK in the build
  container). Pure-logic units run locally via `./gradlew :app:testDebugUnitTest`.
- **Release signing.** The release build type compiles but is not
  signed by default — see "Release AAB" above.
- **Termux bridge fire-and-forget.** `TermuxIntentBridge` builds the
  RUN_COMMAND envelopes today; the actual `sendBroadcast` path,
  wake-lock, and status polling land with the cockpit-screen work
  in a follow-up phase.

## Interactive surface (v1.0)

For JARVIS Prime control without opening the full app:

- **Launcher shortcuts** (`res/xml/shortcuts.xml`) â€” long-press the
  launcher icon for **Approve** (Owner Approve flow) and **Stop JARVIS**
  (emergency stop deep-link). Both route through `MainActivity` with
  a `jarvis_action` intent extra.
- **Notification actions** on the foreground-service ongoing
  notification â€” **Owner Approve** (deep-link into the approval flow)
  and **Stop** (terminates the service).

Quick-settings tile (`TileService`) is intentionally deferred to v1.1
once the deep-link approval flow inside `MainActivity` has soaked.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the deliberate
split between this Android module and the Python core.

---

## Service intent contract

`HermesService` is a local-only foreground service (manifest declares
`android:exported="false"`, `foregroundServiceType="dataSync"`). It
can be started in two ways:

1. **From the app process** — the activity calls
   `startForegroundService(Intent(this, HermesService::class.java))`.
2. **From ADB on a development device** — useful for smoke-testing
   the service or for a future Termux bridge that wants to hand work
   off to the foreground notification.

Because the service is `exported=false`, ADB invocations must use
the debug build's component name and run on a device where the same
UID owns the app:

```bash
# Debug build component name uses the .debug applicationIdSuffix.
adb shell am start-foreground-service \
  -n com.aci.hermes.debug/com.aci.hermes.service.HermesService \
  --es hermes_workspace /storage/emulated/0/hermes-workspace \
  --es hermes_mode local_subscription_tools \
  --es hermes_agent codex \
  --ez hermes_debug true
```

Supported extras (all optional, all `String` except where noted):

| Extra | Type | Default | Notes |
|---|---|---|---|
| `hermes_workspace` | String | _none_ | Absolute path the caller would like the orchestrator to consider its workspace. Currently logged only — no runtime side-effects. |
| `hermes_mode` | String | `local_subscription_tools` | Takes precedence over the legacy `mode` extra. Free-form label. |
| `hermes_agent` | String | _none_ | Hint about which agent persona started the service (e.g. `codex`, `claude`, `cli`). Logged only. |
| `hermes_debug` | Boolean | `false` | When `true`, marks the launch as a debug invocation in `logcat`. |

Stopping the service:

```bash
adb shell am start-service \
  -n com.aci.hermes.debug/com.aci.hermes.service.HermesService \
  -a com.aci.hermes.action.STOP_ORCHESTRATOR
```

The user can also stop it from the persistent notification.

**Reality check.** These extras are intentionally *observational
only* in the current build. The service prints them via
`Log.i(HermesService, …)` so you can verify your wiring with
`adb logcat -s HermesService`. Routing them into a real Python /
CLI bridge is tracked separately and is not part of the alpha.

---

## Privacy and on-device data

- `hermes_settings.preferences_pb` — Jetpack DataStore file under
  `app_files/datastore/`. Stores theme, the four preferred-tool
  enums, and the five boolean toggles. **Excluded** from cloud
  backup and device transfer (see `res/xml/backup_rules.xml` and
  `res/xml/data_extraction_rules.xml`).
- `files/hermes_tasks.json` — task list. Contains user-typed task
  titles, descriptions, workspace paths, and any review / result
  notes the user entered. **Excluded** from cloud backup and device
  transfer for the same reasons. We treat task descriptions as
  potentially sensitive because the SAFETY_BLOCK in the prompt
  builder explicitly tells the receiving model not to act on
  pasted credentials; the in-app text the user wrote is still
  user-owned content.
- Logs in the Diagnostics ring buffer are in-memory only. They do
  not persist across restarts and are never written to disk by the
  app.

If you find one of those rules drifting from the actual data
layout, please open an issue — the rules ship as runtime
manifest-assertion tests under `app/src/test/java/.../backup/`.

<!-- ci: trigger android-build.yml so a fresh debug APK lands as a workflow artifact. -->
