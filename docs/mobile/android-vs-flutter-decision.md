# muse mobile — Android-native vs Flutter (vs everything else)

**Status:** decision recorded. Effective 2026-05-23.
**Owner:** mobile track.
**Branch the decision was made on:** `claude/android-flutter-decision-a0mPG`.

## TL;DR

- **Primary direction:** **Android-native, Kotlin + Jetpack Compose**, packaged
  as the existing module at [`apps/android/`](../../apps/android/). It is
  already in the tree, already builds, already has the right model (cockpit
  over a muse gateway, Termux intent bridge, EncryptedSharedPreferences
  for the bearer token). Phase 02 ratifies that direction rather than
  rebuilding it.
- **Fallback direction:** **Flutter**, but only if the project decides to
  ship a first-class iOS client *and* nobody volunteers to maintain a
  parallel Swift codebase. We treat Flutter as a future migration option,
  not the default.
- **Out of scope (rejected):** React Native, PWA-wrapping the existing
  dashboard, a "minimal Android shell over local muse" that re-embeds
  Python, and any hybrid that tries to keep two production UIs alive at
  the same time.

The rest of this doc shows the work behind that recommendation.

---

## 1. What we found in the tree

Before recommending anything, Phase 02 verified the current state. Key
findings:

- `apps/android/` already contains a native Kotlin + Jetpack Compose
  module. Package `com.aci.hermes`, min SDK 26, target 35, MVVM with a
  hand-rolled `AppContainer` DI. Persistence split: DataStore for
  non-secrets, EncryptedSharedPreferences for the gateway bearer token.
  See [`apps/android/docs/ARCHITECTURE.md`](../../apps/android/docs/ARCHITECTURE.md).
- The Android app's mental model is already a **cockpit**, not an agent
  container: see [`docs/android/hermes-apk-cockpit.md`](../android/hermes-apk-cockpit.md)
  and the cockpit API contract at
  [`docs/android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md).
- A typed Kotlin mirror of the cockpit contract is in
  [`apps/android/app/src/main/java/com/aci/hermes/data/cockpit/CockpitApi.kt`](../../apps/android/app/src/main/java/com/aci/hermes/data/cockpit/CockpitApi.kt).
- A `TermuxIntentBridge` stub exists for talking to a Termux-hosted gateway
  via `com.termux.RUN_COMMAND` instead of pure HTTP. See
  [`docs/android/termux-intent-bridge.md`](../android/termux-intent-bridge.md).
- There is **no** Flutter (`*.dart`), React Native, or Capacitor/Cordova
  code in the repo. The validation command from the task brief
  (`find ... -name *.dart`) returns nothing.
- The Python gateway in `gateway/run.py` already exposes WebSocket
  endpoints (`/api/pty`, `/api/ws`, `/api/pub`, `/api/events`) plus a
  `/v1/health` endpoint that the Android app already consumes. The
  `/v1/cockpit/*` Phase 18 routes are specced but not yet live.
- The phone-first runtime (`muse` inside Termux) is documented in
  [`docs/termux/hermes-phone-first-runtime.md`](../termux/hermes-phone-first-runtime.md)
  and is treated as the on-device backend the cockpit drives.

The headline: **muse already chose Android-native** at the code level.
Phase 02's job is to either confirm or reverse that, with reasons.

---

## 2. Criteria, in plain English

The brief calls out twelve criteria. For each, the question is "which
option makes Jeremiah's phone life easier?", not which is more
fashionable.

### 2.1 Jeremiah's phone-first workflow

Jeremiah works from an Android phone. The mobile client is the primary
interface, not a companion to a desktop UI. That means the mobile client
must:

- launch quickly,
- run for hours in the background while orchestrated jobs proceed,
- never lose a draft because the OS killed the process,
- survive flaky Wi-Fi and bedtime LTE without losing the conversation.

This is the criterion most options collapse under. PWAs and Webviews fail
the "survive backgrounding" bar; React Native passes but with caveats
around foreground services. Native Android and Flutter both pass.

### 2.2 Voice-first UX

A future voice-first cockpit needs:

- low-latency capture from the device mic (Android `AudioRecord` / Compose
  `Activity` permissions),
- streaming to the gateway (either HTTP chunked upload or WebSocket),
- streaming TTS back from the gateway,
- a "hold to talk" or "wake word" affordance that survives screen-off.

The Android SpeechRecognizer API and `AudioRecord` are first-class from
Kotlin; Flutter has solid plugins (`flutter_sound`, `speech_to_text`) but
adds a method-channel hop. React Native is similar to Flutter with more
fragmentation. PWAs cannot do background mic capture.

### 2.3 Background listening / service needs

The cockpit needs a `foregroundServiceType="dataSync"` (already declared
in [`AndroidManifest.xml`](../../apps/android/app/src/main/java/com/aci/hermes/service/HermesService.kt))
so SSE/WebSocket streams from the gateway can survive screen-off without
the OS killing the process. Native Kotlin gives direct access to this.
Flutter requires a plugin (`flutter_foreground_task` or similar) and
either way you write Kotlin for the actual service. PWAs can't.

### 2.4 Termux / local backend integration

This is the criterion that **decisively favours Android-native**.

The cockpit talks to a muse gateway over HTTP/SSE *and* fires
`com.termux.RUN_COMMAND` intents to start/stop the gateway inside the
Termux sandbox on the same device. Intents are an Android system API; the
RUN_COMMAND envelope is a Termux-specific contract. Native Kotlin
expresses this directly (see
[`TermuxIntentBridge.kt`](../../apps/android/app/src/main/java/com/aci/hermes/data/termux/TermuxIntentBridge.kt)).

In Flutter or React Native, every intent call is a method-channel hop
into Kotlin anyway. We would write *the same Kotlin code* and then a
shim on top of it. That is strictly more code, not less.

### 2.5 WebSocket / local API integration

Both native Android (OkHttp / OkHttp-SSE / kotlinx-coroutines) and
Flutter (`web_socket_channel`, `dio`) have battle-tested clients.
WebSocket is a wash on this criterion.

### 2.6 Offline queueing

The cockpit composes prompts the user wants to dispatch even when the
gateway is unreachable. Drafts and pending dispatches must persist
across process death and reboots. Both native (Room + DataStore) and
Flutter (`drift`, `hive`, `isar`) handle this fine. Wash.

### 2.7 Secure approval prompts

Every destructive cockpit action (cancel job, override validation,
approve publish, approve a destructive command from the agent) requires
an explicit on-device tap, with an extra confirmation sheet. The bearer
token for the gateway lives in EncryptedSharedPreferences with a
hardware-backed master key when available.

Native Kotlin gets this for free through `androidx.security.crypto`.
Flutter uses `flutter_secure_storage`, which transparently sits on top
of the Android Keystore — also fine, but it's a bridge.

For approvals themselves, both stacks render a confirmation dialog
equally well. The differentiator is the **storage** of the secret, and
both reach the same OS primitive in the end.

### 2.8 UI speed

Compose and Flutter both target 60+ fps on mid-range Android hardware.
Compose has a slightly stronger story on Android 14+ for predictive back
gestures and platform-correct Material 3 theming; Flutter has the
strongest story for *pixel-identical* UI across iOS and Android. For an
Android-first cockpit, Compose's tighter Android integration is the
better default.

### 2.9 Maintainability from an Android phone

Jeremiah does some development *on the phone* (Termux + the cockpit
itself). Both Kotlin and Dart can be edited from Termux; neither can
*build* a release APK on the phone without a serious workaround
(Gradle on `aarch64` in Termux works for Android-native debug builds via
the Android SDK distributed binaries; Flutter requires the full Flutter
SDK and is heavier).

Native edges this slightly because the Android SDK + Gradle path is
narrower and already documented in the repo
([`apps/android/README.md`](../../apps/android/README.md) §Building).
Flutter on Termux is possible but not a well-trodden path.

### 2.10 Ability to build with minimal friction

This is shorthand for "if a contributor clones the repo today, how fast
can they ship an APK?" Today:

- **Native:** `cd apps/android && ./gradlew assembleDebug` — minutes,
  no extra toolchain beyond JDK 17 + Android SDK.
- **Flutter:** install Flutter SDK, run `flutter create`, port screens.
  Days, plus an extra toolchain.

Switching to Flutter is a measurable schedule cost we cannot justify
without an iOS deliverable on the roadmap.

### 2.11 Future iOS possibility

This is the **only** criterion that pushes toward Flutter. If muse
ever commits to an iOS client:

- **Native path:** write a second app in Swift / SwiftUI. The cockpit
  contract is REST/SSE, so the API surface is portable.
- **Flutter path:** the same Dart codebase compiles for iOS with minor
  per-platform shims.

iOS is not on the active roadmap (Jeremiah is Android-first, and the
project's primary distribution channel for the cockpit is the F-Droid
build). When and if iOS becomes a real deliverable, Phase N+1 should
reopen this decision.

### 2.12 Integration with existing muse dashboard / TUI / backend

The cockpit's API contract
([`docs/android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md))
is the boundary. Anything that speaks HTTP+SSE with `Authorization:
Bearer` integrates. Both Kotlin and Flutter satisfy this. So does a
PWA — but the PWA path then has to re-solve background execution,
secure storage, and Termux intents from scratch, which is exactly the
point of having a native app in the first place.

The existing TUI lives in `ui-tui/` (Ink/React) and is unrelated to
the mobile client other than sharing the gateway. The "web dashboard"
served by `hermes_cli/web_server.py` is a desktop browser UI, not a
mobile UI, and is also unrelated.

---

## 3. The five options, scored

Scoring legend per criterion: ✅ good fit, 🟡 workable but requires
extra work, 🔴 doesn't satisfy the requirement.

| # | Criterion | Android native | Flutter | React Native | PWA-wrap dashboard | "Minimal Android shell + embed Python" |
|---|-----------|---------------|---------|--------------|--------------------|----------------------------------------|
| 1 | Phone-first workflow | ✅ | ✅ | ✅ | 🔴 (backgrounding) | 🟡 |
| 2 | Voice-first UX | ✅ | 🟡 (plugin) | 🟡 (plugin) | 🔴 (mic-on-bg) | 🟡 |
| 3 | Background service | ✅ | 🟡 (plugin) | 🟡 (plugin) | 🔴 | ✅ |
| 4 | Termux integration | ✅ | 🟡 (channel) | 🟡 (channel) | 🔴 | ✅ but breaks other criteria |
| 5 | WebSocket / SSE | ✅ | ✅ | ✅ | ✅ (but bg dies) | ✅ |
| 6 | Offline queueing | ✅ | ✅ | ✅ | 🟡 (IndexedDB) | ✅ |
| 7 | Secure approvals | ✅ | ✅ | ✅ | 🟡 (no Keystore) | ✅ |
| 8 | UI speed | ✅ (Compose) | ✅ | 🟡 | 🟡 | n/a |
| 9 | Maintainability from phone | ✅ | 🟡 | 🟡 | ✅ (just edit) | 🔴 |
| 10 | Build friction (today) | ✅ already builds | 🔴 not in tree | 🔴 not in tree | ✅ (just URLs) | 🔴 (Termux-coupled) |
| 11 | Future iOS | 🔴 (Swift port) | ✅ | 🟡 | ✅ | 🔴 |
| 12 | Integration with backend | ✅ (already wired) | ✅ | ✅ | ✅ | 🔴 (duplicates engine) |

Native wins 10 of 12 outright, ties 0, and is 🔴 only on **iOS** — a
criterion we are explicitly deferring.

Flutter wins on iOS portability and ties on most other axes, but it
forfeits the existing built/tested codebase and adds a method-channel
hop for the parts that actually matter on Android (Termux intents,
foreground service, voice).

The other three options each fail at least one **load-bearing** criterion
(background execution for PWA, build friction for RN, Python embedding
for the "shell + embed" option — Android sandboxes can't host CPython,
per [`apps/android/README.md`](../../apps/android/README.md) §Native
APK limitations and `apps/android/docs/ARCHITECTURE.md` §"Why not embed
a Python runtime?").

### 3.1 Hybrid options

The brief lists hybrid approaches. We evaluated three:

- **Native shell + Compose for chrome + Flutter for one feature.** Two
  build systems, two render trees, two ways to test. Rejected:
  doubles complexity for no integration win.
- **Flutter shell + a Kotlin "Termux bridge" module.** This is exactly
  what we'd do if we chose Flutter outright. It's not a separate option;
  it's "Flutter" by another name.
- **Native shell + a webview into the dashboard.** Tempting because
  `hermes_cli/web_server.py` already exists. Rejected because the
  dashboard is desktop-shaped (xterm.js, multi-pane), not phone-shaped,
  and dropping into a webview voids most of the cockpit's
  one-tap-approval, foreground-service, and Termux-intent affordances.

No hybrid wins on net.

---

## 4. The decision

**Primary direction: Android-native, Kotlin + Jetpack Compose,
continuing the existing module at [`apps/android/`](../../apps/android/).**

We pick native because:

1. The code is already in the tree, already builds, and already targets
   the right architecture (cockpit-over-gateway, no embedded Python).
2. Termux-intent integration is the load-bearing differentiator and is
   a native Android API. A Flutter path would still need this Kotlin
   code, with an extra channel on top.
3. Foreground service + EncryptedSharedPreferences + Compose UI fit the
   phone-first / voice-first / secure-approval criteria with the fewest
   abstractions.
4. Build friction today is zero — `./gradlew assembleDebug` is one
   command, documented, and on CI in `.github/workflows/android-build.yml`.
5. The cockpit's API contract is platform-agnostic, which means a
   Flutter or Swift port later is a **screen-by-screen rewrite, not a
   protocol redesign**.

**Fallback direction: Flutter.**

We treat Flutter as the fallback because:

1. It is the only option that gives us iOS later without writing a
   parallel Swift codebase.
2. Its plugin ecosystem on Android is solid enough that the criteria we
   care about (background service, secure storage, voice) are all
   reachable, just with a layer of indirection.
3. If the team ever decides to ship iOS as a first-class client, Flutter
   becomes the rational unification. The cockpit's REST/SSE contract is
   designed to keep that migration possible.

### 4.1 What "primary" and "fallback" mean operationally

- New cockpit features are built in `apps/android/` (Kotlin) **until and
  unless** the project commits to an iOS deliverable.
- The cockpit contract in `docs/android/hermes-apk-api-contract.md`
  stays the single source of truth, regardless of front-end stack.
- A migration to Flutter is gated on a written go/no-go: see §6.

---

## 5. What we are *not* doing

Spelling these out so we don't relitigate them:

- **Not embedding CPython in the APK.** Android sandboxes can't host
  the toolchain CPython needs for extensions. The on-device backend
  path is "APK + Termux gateway", not "APK with embedded Python." See
  [`apps/android/docs/ARCHITECTURE.md`](../../apps/android/docs/ARCHITECTURE.md)
  §"Why not embed a Python runtime?".
- **Not wrapping the desktop dashboard.** It is desktop-shaped. The
  cockpit is its own UI, not a viewport into the desktop one.
- **Not introducing React Native.** No advantage over the two finalists,
  worse Android integration than native, worse iOS portability than
  Flutter.
- **Not freezing the existing app.** Phase 02 confirms the existing
  module is the cockpit going forward; the Phase 18 cockpit screens
  (Prompt Command Center, Worker Dashboard, Job Folder Browser, Diff
  and Merge Review, Validation Gate, GitHub Publisher, Termux Control
  Panel, Logs and Events) land into that same module.

---

## 6. When to reopen the decision

Reopen this decision **only if** at least one of these is true:

- iOS becomes a committed deliverable with a named maintainer.
- A second platform (desktop tablet, ChromeOS) becomes a committed
  deliverable that meaningfully changes the cross-platform calculus.
- The native Android module hits a structural blocker (Google Play
  policy, JVM/Compose regression) that can't be worked around in
  Kotlin.

Routine annoyances (a specific OkHttp bug, a flaky Gradle plugin)
don't qualify. Reopen costs are high — we'd lose the cockpit module's
existing wiring and rewrite Phase 18 screens in a new stack.

---

## 7. Cross-references

- [`apps/android/README.md`](../../apps/android/README.md) — how to
  build and run the existing app.
- [`apps/android/docs/ARCHITECTURE.md`](../../apps/android/docs/ARCHITECTURE.md)
  — module-by-module description of the existing Kotlin module.
- [`docs/android/hermes-apk-cockpit.md`](../android/hermes-apk-cockpit.md)
  — Phase 18 cockpit spec, which this decision is consistent with.
- [`docs/android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md)
  — cockpit ↔ gateway wire format.
- [`docs/android/termux-intent-bridge.md`](../android/termux-intent-bridge.md)
  — the on-device intent path.
- [`docs/termux/hermes-phone-first-runtime.md`](../termux/hermes-phone-first-runtime.md)
  — the Termux runtime the cockpit drives.
- [`docs/mobile/hermes-mobile-architecture.md`](hermes-mobile-architecture.md)
  — the concrete architecture this decision implies.
- [`docs/mobile/hermes-mobile-backend-contract.md`](hermes-mobile-backend-contract.md)
  — the wire format the mobile client expects.
- [`docs/mobile/hermes-app-module-plan.md`](hermes-app-module-plan.md)
  — what changes land in `apps/android/` to execute this decision.
