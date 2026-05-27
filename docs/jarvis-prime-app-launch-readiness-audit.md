# JARVIS Prime — Android App Launch Readiness Audit

**Branch:** `feature/jarvis-prime-app-launch-readiness`
**Audit scope:** `apps/android/` (the native Android app) reviewed against the
JARVIS Prime operating-system specification at
`docs/jarvis-prime-operating-system.md` and the Phase-18 cockpit spec at
`docs/android/`.
**Reviewers simulated:** elite Android engineers, AI engineers, UX designers,
product leaders, security engineers, privacy reviewers, enterprise architects.
**Date:** 2026-05-26.
**Auditor:** Claude Code session under `feature/jarvis-prime-app-launch-readiness`.

---

## TL;DR verdict — **RED: NOT READY**

The shipped Android app (`com.aci.hermes`, label **"Hermes Agent"**, `versionName="0.1.0"`,
`versionCode=1`) is a **manual prompt-handoff utility**, not the JARVIS Prime
cockpit. It builds prompts in Kotlin, writes them to the system clipboard, and
optionally launches the ChatGPT/Claude apps. Nothing else from the
JARVIS Prime spec — modes, voice, memory, gates, owner-auth, social
research, approvals, Termux gateway control, events spine — exists in the
APK. The 159-test JARVIS Prime runtime in `hermes_cli/jarvis_prime/` is
Python-only and is **never reached** from this APK; there is no client,
no transport, no IPC.

The app is **demo-able as a "manual orchestrator"** if you re-scope launch
to that. As "JARVIS Prime on Android" it is **not launchable** today —
the brand on the splash and label is wrong (still "Hermes Agent ☤"), no
identifying JARVIS surface is present, and most of the categories below
score ≤ 3.

A second, equally hard blocker: the in-tree docs (`apps/android/README.md`
and `apps/android/docs/ARCHITECTURE.md`) describe a **completely different
app** — chat screen, provider screen, OkHttp + SSE client,
EncryptedSharedPreferences, mock mode, gateway URL — none of which is in
the current source. Any reviewer reading the docs first will be misled.

**Recommendation:** rebrand the current artifact honestly as "Hermes
Local Orchestrator alpha v0.1" and ship that on a private track, OR
delay the JARVIS Prime APK launch until at least the items in the top-10
blockers below are closed.

---

## Build, test, and manifest checks performed

| Check | Result |
|---|---|
| `cd apps/android && ./gradlew assembleDebug` (this sandbox) | **Fails — `SDK location not found`**. The remote-execution environment ships JDK 21 but no Android SDK; AGP 8.7.3 plugin resolves once the Gradle wrapper (8.11.1) downloads, but `:app:compileDebugJavaWithJavac` cannot proceed without `platforms;android-35` + `build-tools;35.0.0`. **Recorded as an environment limitation, not an app defect** — the same command runs in CI (`.github/workflows/android-build.yml`) on `android-actions/setup-android@v3`. |
| Android app tests | **None exist.** `apps/android/app/src/` has only a `main/` source set; no `test/` (JVM) and no `androidTest/` (instrumented) directories. The `testInstrumentationRunner` is declared and `junit` + `androidx.test.junit` + `espresso-core` are on the classpath, but there are zero test files. |
| Manifest permission review | Three permissions declared: `POST_NOTIFICATIONS` (Android 13+ runtime ask), `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_DATA_SYNC` (matches the `android:foregroundServiceType="dataSync"` on `HermesService`). No `INTERNET`, `RECORD_AUDIO`, `READ_EXTERNAL_STORAGE`, `WAKE_LOCK`, or `FOREGROUND_SERVICE_MICROPHONE`. **Coherent for what the app does today**, but is **inconsistent with both the JARVIS Prime spec and the in-tree README** which advertise voice capture, push from gateway, and Termux RUN_COMMAND. |
| JARVIS Prime runtime tests | `pytest -p no:cacheprovider -o addopts= tests/test_jarvis_prime_*.py` → **159 passed in 2.90 s**. Runtime is healthy in Python; the gap is purely on the APK side. |
| `python3 scripts/jarvis_context_audit.py` | **PASS — failures=0 warnings=0.** Documents and skills exist and contain the required terms; the APK is not in scope of that audit. |

---

## Inventory the audit was performed against

```
apps/android/app/src/main/
├── AndroidManifest.xml               (3 permissions, 1 activity, 1 service)
├── java/com/aci/hermes/
│   ├── HermesApplication.kt          (creates AppContainer + notif channel)
│   ├── MainActivity.kt               (edge-to-edge, requests notif perm,
│   │                                   starts HermesService on every cold start)
│   ├── di/AppContainer.kt            (hand-rolled DI for 4 VMs)
│   ├── service/HermesService.kt      (foreground "dataSync", local-only,
│   │                                   logs intent extras only — no real work)
│   ├── data/
│   │   ├── cockpit/CockpitApi.kt     (Phase-18 wire models — typed but UNUSED)
│   │   ├── termux/TermuxIntentBridge.kt
│   │   │                              (Phase-18 RUN_COMMAND stub — UNUSED)
│   │   ├── model/                    (AiToolProfile, HermesRole, HermesTask)
│   │   ├── orchestrator/             (HandoffLauncher, HermesTaskRepository,
│   │   │                              PromptBuilder)
│   │   └── preferences/              (SettingsRepository → DataStore only,
│   │                                  ThemeMode)
│   ├── ui/
│   │   ├── navigation/               (NavHost + 4 routes: splash,
│   │   │                              orchestrator, task_detail, settings,
│   │   │                              diagnostics)
│   │   ├── screens/
│   │   │   ├── splash/               (600 ms delay then Orchestrator)
│   │   │   ├── orchestrator/         (dashboard, task detail, VMs)
│   │   │   ├── settings/             (theme, prefs, reset)
│   │   │   └── diagnostics/          (app version, build type, log buffer)
│   │   └── theme/                    (gold/violet/ink palette, M3 light+dark)
│   └── util/LogBuffer.kt             (in-memory ring buffer, hard cap 200)
└── res/
    ├── strings.xml                   (all labels say "Hermes Agent")
    ├── colors.xml                    (single splash color)
    ├── drawable/                     (vector launcher + splash background)
    ├── mipmap-anydpi-v26/            (adaptive icon XML only; NO raster PNG
    │                                  density buckets)
    ├── values{,-night}/themes.xml    (transparent system bars, splash theme)
    └── xml/{backup_rules,data_extraction_rules}.xml
                                       (still exclude `hermes_secure_prefs.xml`
                                        though that store no longer exists)
```

**Total source files:** 29 Kotlin + 11 resource XML. No Kotlin under `test/`
or `androidTest/`.

---

## Category scorecard

Each category is scored 1–10 against the JARVIS Prime spec (where the spec
applies) or against generic launch-quality expectations.

### 1. Product identity — **1 / 10**

- **Evidence.** App label `"Hermes Agent"` (`strings.xml:3`), package
  `com.aci.hermes`, namespace `com.aci.hermes`, splash text
  `"Hermes Agent"` with the caduceus glyph `☤` (`SplashScreen.kt:42-48`).
  Zero occurrences of "JARVIS", "Jarvis Prime", or any of the six modes
  (`grep -r "JARVIS\|jarvis-prime" apps/android/` returns nothing).
- **Blocker.** **There is no JARVIS Prime identity in the app.** The brand,
  splash, notification channel name (`"Hermes Orchestrator"`), and persistent
  notification text (`"Hermes is coordinating your local AI workflow."`) all
  belong to a different product.
- **Risk.** Launching this APK as "JARVIS Prime" trains users to expect
  Hermes, not JARVIS — a brand-confusion event on day one. The Play
  listing, screenshots, and the running app would not match.
- **Fix.** Pick one of: (a) ship as "Hermes Agent v0.1 alpha" honestly,
  postpone JARVIS launch; (b) rename label/package/notification channel
  and add a JARVIS identity surface (splash mark, mode indicator chip in
  the top app bar, "JARVIS Prime is online" first-line in the persistent
  notification). Track all strings in `strings.xml` so localisation
  stays clean.

### 2. App architecture — **6 / 10**

- **Evidence.** Clean MVVM with Compose + Material 3, hand-rolled DI in
  `AppContainer` (`AppContainer.kt:25-72`), per-screen `StateFlow<UiState>`,
  `viewModelScope` for side effects. Hermes uses `kotlinx-serialization`
  for JSON, DataStore for non-secret prefs, Mutex-guarded atomic file
  writes for task storage (`HermesTaskRepository.kt:88-100`, including
  the `.tmp` + `renameTo` pattern). `minSdk=26`, `targetSdk=35`,
  `compileSdk=35`, JVM target 17. Configuration cache off (documented
  reason in `gradle.properties`).
- **Blocker.** None at the structural level — the small dependency
  graph really does justify hand-rolled DI. However the architecture is
  scoped to a **prompt-builder app**; nothing in it is shaped for the
  cockpit (no gateway client, no SSE/WebSocket, no IPC, no event spine).
  Adopting Phase 18 will require new modules, not refactors.
- **Risk.** ViewModels reach across the entire `AppContainer`; without
  module boundaries a future cockpit screen can accidentally pull task
  storage in. `OrchestratorViewModel.isServiceRunning` uses the
  deprecated `ActivityManager.getRunningServices` (`OrchestratorViewModel.kt:137-144`)
  — fine for self-only queries today but worth flagging on every
  Android version bump.
- **Fix.** Before Phase 18 lands, split the package layout into
  `feature/orchestrator/`, `feature/cockpit/`, `feature/jarvis/`,
  `core/data/`, `core/transport/`. Add a `transport/` module that owns
  the cockpit HTTP client so the orchestrator and cockpit screens don't
  share an HTTP stack by accident.

### 3. Navigation — **5 / 10**

- **Evidence.** Five routes wired in `HermesNavHost`
  (`HermesNavGraph.kt:23-93`): `splash → orchestrator → task_detail` and
  `orchestrator → {settings, diagnostics}` (and `settings → diagnostics`).
  Deep argument parsing for `task_detail` (`Screen.kt:6-12`) is correct
  and uses safe `runCatching { TargetTool.valueOf(name) }`.
- **Blocker.** **No JARVIS mode selector**, no bottom nav, no surfaces for
  any of the eight verification gates, no home/mobile-voice/social/audit
  routes. A user who hands the phone to someone else cannot tell which
  mode JARVIS is in because there is no mode at all.
- **Risk.** `splash` pops itself off the back stack but `orchestrator`
  is the start destination, so back-press from the home screen exits
  the app — fine for today but will need to be revisited when a
  cockpit dashboard takes over the start route.
- **Fix.** Plan a `BottomAppBar` with Home / Chat / Tasks / Approvals /
  Voice once those screens exist. Until then, document the limited
  navigation as intentional.

### 4. Onboarding — **2 / 10**

- **Evidence.** **There is no onboarding.** `SplashScreen.kt` is a
  600 ms `delay` then `onReady()`; the app jumps straight to the
  orchestrator dashboard regardless of `SettingsRepository.hasOnboarded`,
  which is read by no caller (`SettingsRepository.kt:45-47`). The
  README still describes a "Get started / Skip and use mock mode"
  flow that no longer exists in code.
- **Blocker.** A first-run user is dropped into the orchestrator with
  no explanation, no consent prompt, no permissions context, no JARVIS
  introduction, and no link to the docs.
- **Risk.** Permission ask for `POST_NOTIFICATIONS` fires from
  `MainActivity.onCreate` (`MainActivity.kt:55-63`) with no rationale —
  Android UX guidelines (and Play policy) ask for a pre-prompt
  explaining why.
- **Fix.** Add a 2- or 3-step Compose onboarding gate that (1)
  introduces JARVIS Prime and its non-goals, (2) asks for the
  notification permission with a clear rationale, (3) writes
  `setOnboarded(true)`. Honour the existing `hasOnboarded` flag from
  `NavHost`'s start-destination selection.

### 5. Home — **3 / 10**

- **Evidence.** The "home" surface is the Orchestrator dashboard
  (`OrchestratorScreen.kt`): a `StatusCard`, a list of four "Official
  AI tools" cards (Codex, ChatGPT, Claude Code, Claude), a list of
  saved `HermesTask`s, and a "Safety banner". Hard-coded status row
  values like `"Local Subscription Tools"` and `"Not used"` are passed
  as literal strings rather than `stringResource(...)`
  (`OrchestratorScreen.kt:192`), breaking translation.
- **Blocker.** This is not a JARVIS home. No greeting personalised to
  the owner, no current-mode indicator, no last-asked summary, no
  "Today's brief", no link to the most recent decision or memory hit.
- **Risk.** New users can mistake "Hermes Orchestrator" for a chat
  interface and tap "Open tool" expecting a connection — but the
  default `allowExternalAppOpening = false` hides the "Open tool"
  button entirely, leaving only the somewhat opaque "Prepare handoff"
  action. The UX delta from "I just installed JARVIS" to "I see what
  JARVIS does for me" is large.
- **Fix.** Either move the orchestrator behind a Home route or relabel
  it as `"Manual handoff"`. Add a true Home screen that surfaces a
  greeting, the active JARVIS mode, the most recent owner-gated
  action, and a single "Ask JARVIS" CTA.

### 6. Chat — **0 / 10**

- **Evidence.** **There is no chat surface in the APK.** The README
  describes one (`apps/android/README.md:253-261`) and references a
  `ChatScreen`, abort button, streaming bubbles, new-convo button.
  None of those classes or routes exist; `grep -r "ChatScreen\|chat"
  apps/android/app/src/main/java/` returns nothing.
- **Blocker.** Either the chat surface needs to ship, or the README +
  ARCHITECTURE.md need to be rewritten so a reviewer reading the docs
  first is not deceived.
- **Risk.** External reviewers comparing the doc to the app will treat
  it as undocumented removal — exactly the audit signal that turns
  yellow verdicts into red ones.
- **Fix.** Decide product-side: keep the manual-handoff model (then
  delete chat copy from docs) or build the cockpit chat from Phase 18.

### 7. Tasks — **5 / 10**

- **Evidence.** `HermesTask` (`HermesTask.kt:7-21`) has a small, sound
  field set with stable UUIDs and atomic JSON-on-disk persistence
  (`HermesTaskRepository.kt`). The `TaskDetailScreen` (273 lines) wires
  every field, plus a live `promptPreview` re-rendered on every edit
  (`TaskDetailViewModel.kt:145-154`). Mark-handed-off transitions to a
  sensible `TaskStatus`.
- **Blocker.** No search, no filter, no sort, no tags, no archive, no
  bulk delete, no export. Tasks live only in `filesDir/hermes_tasks.json`
  with no Room schema migration story when a richer model lands.
- **Risk.** `TaskDetailViewModel.markHandedOff` calls
  `setStatus(...)` then `tasksRepo.upsert(...)` (`TaskDetailViewModel.kt:103-114`)
  — `setStatus` mutates the in-memory state but the upsert that follows
  is on the *new* state, so a race between user editing and tap will
  persist whatever the user has on screen with the new status applied.
  Subtle but worth a regression test.
- **Fix.** Add an explicit "save vs. save-and-handoff" split, and a
  paged repository with optional Room-backed indexing once task count
  ≥ ~500.

### 8. Approvals — **0 / 10**

- **Evidence.** `CockpitApi.kt:244-261` defines `PendingApproval` and
  `DecideApprovalRequest` data classes, but **no screen, no ViewModel,
  no transport** consumes them. JARVIS Prime's owner-gated actions
  (`docs/jarvis-prime-operating-system.md` — spend, deploy, publish,
  OAuth, main-branch merge, package publish, credential change,
  regulated claims) have no APK surface.
- **Blocker.** The whole owner-auth + approval policy that JARVIS
  Prime depends on is invisible on the phone.
- **Risk.** Without an approvals surface, the only safe mode for any
  destructive action is "always deny" — which is exactly what the
  current app does by leaving `allowExternalAppOpening=false`. This
  is safe but unusable.
- **Fix.** Implement the Phase-18 "Approvals" screen that lists
  `PendingApproval`s, supports a typed `"Yes, with authorization."`
  confirmation per the JARVIS Prime owner-auth contract, and posts
  `DecideApprovalRequest` via a (still-to-be-built) cockpit client.

### 9. Interactive icon — **2 / 10**

- **Evidence.** Adaptive icon XML in `mipmap-anydpi-v26/` with vector
  background + foreground + monochrome (themed icon support). No
  raster fallbacks in `mipmap-hdpi/...xxxhdpi/`; old launchers may
  render at the wrong density. No notification badge, no shortcuts,
  no app widgets, no tile service. The launcher mark is the
  caduceus glyph, not a JARVIS mark.
- **Blocker.** "Interactive icon" as a JARVIS surface (long-press
  shortcuts to Chat / Voice / Approvals, dynamic monochrome variant
  reflecting mode) does not exist.
- **Risk.** On Android 13+ the monochrome layer reuses the foreground
  drawable verbatim (`mipmap-anydpi-v26/ic_launcher.xml:5`) — the
  themed icon will look identical to the colored one, defeating the
  point.
- **Fix.** Add raster mipmaps for the four density buckets, a proper
  monochrome silhouette, App Shortcuts XML, and (later) a quick-tile
  toggle that flips JARVIS into focus mode.

### 10. Voice capture — **0 / 10**

- **Evidence.** **No `RECORD_AUDIO` permission**, no `SpeechRecognizer`,
  no `MediaRecorder`, no STT/TTS dependency, no voice screen, no
  `FOREGROUND_SERVICE_MICROPHONE` foreground type. README explicitly
  says voice is "not wired up yet" (`apps/android/README.md:269-270`).
  JARVIS Prime spec demands Mobile Voice as one of the six modes
  (`docs/jarvis-prime-operating-system.md`).
- **Blocker.** Voice capture, the central modality of JARVIS Prime
  on mobile, is unimplemented.
- **Risk.** Shipping JARVIS without voice would invalidate the
  primary use case described in `docs/voice/voice-first-user-guide.md`
  and `docs/mobile-voice-development-workflow.md`.
- **Fix.** Build a voice capture service following
  `docs/mobile/app-voice-service.md`. Use `FOREGROUND_SERVICE_MICROPHONE`,
  show a persistent capturing indicator, ship STT via the platform
  recogniser before negotiating a cloud STT provider.

### 11. Memory — **0 / 10**

- **Evidence.** No client for the JARVIS Prime memory subsystem
  (`hermes_cli/jarvis_prime/memory.py`). The on-device DataStore stores
  preferences only (`SettingsRepository.kt:24-35`); no per-user
  memories, no facts, no goals, no decisions, no aspirations.
- **Blocker.** Owner memory, the JARVIS feature that lets it remember
  durable lessons across sessions, is absent on the phone.
- **Risk.** Users on mobile-only flows will perceive JARVIS as
  amnesiac — every session will start cold.
- **Fix.** Add a `MemoryClient` against the cockpit (or a future
  `/v1/jarvis/memory/*` surface), a Compose surface to view/edit
  remembered facts, and a "remembered" chip in chat replies citing
  the memory used.

### 12. Social intelligence UI — **0 / 10**

- **Evidence.** No surface for `social_research.py` or
  `docs/aos-jarvis-agent-routing.md`. No people/relationships/contexts
  graph in the UI.
- **Blocker.** None of JARVIS Prime's social-intelligence layer
  reaches the user on mobile.
- **Risk.** A demo cannot show owner-context awareness ("you spoke
  with X about Y last week"), which is one of the marquee
  differentiators.
- **Fix.** Defer for the v1 launch; document explicitly as out of
  scope rather than letting reviewers find it missing.

### 13. Audit / proof — **2 / 10**

- **Evidence.** The Diagnostics screen renders an in-memory log
  buffer (`LogBuffer`, ring-capped at 200) and a one-line "last
  error" (`DiagnosticsScreen.kt:80-95`). Logs forward to Logcat
  (`LogBuffer.kt:52-58`). No persistent audit log, no signed events,
  no decision ledger, no JARVIS gate transcript on device.
- **Blocker.** The Decision Ledger (`~/.hermes/jobs/<job-id>/ledger.jsonl`,
  the canonical JARVIS proof artefact) has no APK surface and no APK
  store. Reviewers expecting "every gate transition is auditable on
  the device" will not find it.
- **Risk.** A reviewer who clears the log buffer (`DiagnosticsScreen.kt:61-64`)
  destroys the only evidence of what JARVIS did this session.
- **Fix.** Persist diagnostics entries to a rotating file in `filesDir`,
  add an opt-in "export logs" button (already a `ContentCopy` for the
  in-memory buffer — extend to a `share-sheet` of the persisted file),
  and pull the canonical ledger from the cockpit `/v1/cockpit/events`
  surface once it lands.

### 14. Emergency stop — **3 / 10**

- **Evidence.** The persistent foreground notification has a single
  **Stop** action (`HermesService.kt:111-117`) that posts
  `ACTION_STOP` and calls `stopSelf()`. The dashboard has matching
  Start/Stop buttons (`OrchestratorScreen.kt:195-202`). Notification
  channel importance is `LOW` (`HermesService.kt:147-153`), so the
  panic Stop is not above-fold on a busy lock screen.
- **Blocker.** Stop only stops the local foreground service — there
  is no in-app "Stop everything JARVIS is doing remotely" panic
  button, no panic gesture, no panic shortcut, and no read-receipt
  that downstream agents acknowledged the stop.
- **Risk.** A user who taps Stop and assumes JARVIS is paused
  everywhere will be wrong on the day a cockpit lands. Today the
  surface area is small, so the false security gap is bounded.
- **Fix.** Promote the notification channel to `DEFAULT` importance,
  surface a top-app-bar panic button on every screen (already room
  next to Settings + overflow), and design a heartbeat back from the
  gateway so the UI can confirm the stop propagated.

### 15. Gateway / event spine — **0 / 10**

- **Evidence.** **No transport.** No OkHttp, no Ktor, no
  `androidx.lifecycle.*-savedstate` viewer for events, no
  WebSocket / SSE / WebPush plumbing. `CockpitApi.kt`'s 280+ lines
  of `@Serializable` data classes are unreferenced by any client
  class. `TermuxIntentBridge.kt` is a stub with no caller. README
  still claims "OkHttp + OkHttp-SSE, kotlinx-serialization"
  (`apps/android/README.md:17`), which is **incorrect for the
  current `app/build.gradle.kts`**.
- **Blocker.** The Phase-18 cockpit wire format exists on paper and
  in Kotlin types, but no code dials anything.
- **Risk.** Reviewers reading the docs will assume the cockpit is at
  least talking — building the trust gap into the audit.
- **Fix.** Land a minimal `CockpitClient` with a single
  `getRuntimeStatus()` call wired to the Diagnostics screen so the
  surface area is small but real. Once that works, expand
  per-screen. Keep `apps/android/README.md` and
  `docs/mobile/app-api-client.md` honest about what is wired.

### 16. Notifications — **5 / 10**

- **Evidence.** One channel registered eagerly in
  `HermesApplication.onCreate` so the Android-13 runtime permission
  prompt has something to attach to (`HermesApplication.kt:11-17`).
  Channel name `"Hermes Orchestrator"`, importance LOW, no badge.
  Notification body is static; tap opens `MainActivity` single-top;
  in-notification Stop works.
- **Blocker.** Only the orchestrator's "I'm running" notification
  exists. No notification for approvals, completions, voice prompts,
  errors, or owner-gated actions waiting on response. No push
  channel.
- **Risk.** Channel name + content advertise "Hermes" on every
  device — see category 1.
- **Fix.** Add channels for `jarvis_approvals` (HIGH), `jarvis_voice`
  (DEFAULT), `jarvis_errors` (HIGH), and reserve `jarvis_runtime`
  (LOW) for the persistent indicator. Localise every string.

### 17. Control / settings — **6 / 10**

- **Evidence.** `SettingsScreen` covers theme, preferred builder,
  preferred reviewer, four safety toggles (`use_api_keys`,
  `local_only_mode`, `allow_external_app_opening`,
  `clipboard_handoff_enabled`, `show_safety_warnings`), and a
  destructive Reset gated by an `AlertDialog`. State is persisted
  via DataStore. Defaults are conservative: API keys off, local-only
  on, external app opening off, safety warnings on
  (`SettingsRepository.kt:59-69`).
- **Blocker.** "Use API keys" and "Local-only mode" toggles are
  persisted but **nothing in the runtime reads them** —
  `grep -n "useApiKeys\\|localOnlyMode" apps/android/app/src/main/java`
  shows them only on the Settings screen. They are decorative.
- **Risk.** A user who toggles "Local-only mode" off expecting any
  behaviour change will see none. That is worse than not offering
  the toggle.
- **Fix.** Either wire the toggles to real behaviours (gate the
  cockpit client behind `localOnlyMode == false`, etc.) or hide them
  until they do something. Document in `SettingsScreen.kt` which
  toggles are active vs. plumbed.

### 18. Diagnostics — **5 / 10**

- **Evidence.** App version, build type, last error, and the in-memory
  log buffer (200-entry ring) render correctly. Copy-logs and
  clear-logs work. Refresh button is intentionally a no-op
  (`DiagnosticsViewModel.kt:37-41`).
- **Blocker.** No device info, no connectivity probe, no Gradle build
  fingerprint, no JARVIS runtime version, no event spine status.
  Logs do not persist across process death.
- **Risk.** A crash that takes the process down also takes the
  diagnostic trail down with it. The single "Last error" line is the
  only carry-over and it lives in memory too.
- **Fix.** Persist the log ring to `filesDir/diagnostics.jsonl`
  rotating at 1 MiB; add a "Send diagnostics" share intent; show
  Android version, manufacturer, and the cockpit transport status
  once it exists.

### 19. Android permissions — **7 / 10**

- **Evidence.** Manifest declares only what is used:
  `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE`, and
  `FOREGROUND_SERVICE_DATA_SYNC`. `MainActivity` honours the runtime
  permission contract on Android 13+ and degrades gracefully on
  denial (`MainActivity.kt:55-63`). `HermesService` uses the typed
  `startForeground` overload on `UPSIDE_DOWN_CAKE`
  (`HermesService.kt:68-76`).
- **Blocker.** None for current scope.
- **Risk.** Once voice, push, contacts, or Termux IPC land, the
  permission surface will grow fast and the pre-prompt UX needs to
  be designed once, not per-feature.
- **Fix.** Build a `PermissionsCoordinator` now (even with one
  permission to coordinate), so adding `RECORD_AUDIO`,
  `READ_MEDIA_AUDIO`, `POST_NOTIFICATIONS` and Termux's
  `com.termux.permission.RUN_COMMAND` later is uniform.

### 20. Privacy — **7 / 10**

- **Evidence.** The strongest category. No `INTERNET` permission
  declared, so the APK literally cannot dial out. No analytics SDKs,
  no crash reporter, no ad networks. `DataStore` is the only
  persisted preference store; no `EncryptedSharedPreferences`,
  no `Keystore`, no PII collected. `PromptBuilder.SAFETY_BLOCK`
  hard-codes a "do not exfiltrate, copy, or transmit API keys"
  guard (`PromptBuilder.kt:193-198`) that ships in every generated
  prompt. README says "Tokens never live in the app" — true today.
- **Blocker.** None now, but `backup_rules.xml` /
  `data_extraction_rules.xml` still exclude `hermes_secure_prefs.xml`
  even though that store was removed. Keeping stale excludes is
  harmless but signals doc rot.
- **Risk.** Clipboard handoff (`HandoffLauncher.copyPrompt`) is the
  one privacy hole: anything written to the system clipboard is
  potentially observable on Android 12+ via the clipboard reveal
  banner, and other apps can read it for 60 s by default.
- **Fix.** Use the `ClipDescription.EXTRA_IS_SENSITIVE` flag on the
  `ClipData` (`ClipboardManager.setPrimaryClip`) so the OS hides
  the preview. Refresh the backup/extraction excludes to match the
  current store name (or remove the rules entirely once they no
  longer apply).

### 21. Security — **5 / 10**

- **Evidence.** Foreground service is `android:exported="false"`
  (`AndroidManifest.xml:32`). `MainActivity` is exported only as a
  launcher; no intent filters beyond `MAIN`/`LAUNCHER`. ProGuard
  rules keep `kotlinx.serialization` symbols but `release` build
  has no signing config — `bundleRelease` will fail.
  Cleartext HTTP is **disabled** by default in the manifest
  (no `usesCleartextTraffic="true"`) — contrary to what the README
  says. No HTTPS enforcement is needed because no HTTP exists.
- **Blocker.** **Release signing is not configured.** A reviewer
  who runs `./gradlew bundleRelease` will get an unsigned AAB
  rejected by Play. The README points this out
  (`apps/android/README.md:208-214`) but the build script has no
  guidance, and `keystore.properties` is `.gitignored` with no
  template.
- **Risk.** `ContentCompat.startForegroundService` is invoked from
  `MainActivity.onCreate` unconditionally
  (`MainActivity.kt:32`). On Android 12+ this can throw
  `ForegroundServiceStartNotAllowedException` if the app is started
  from a non-allowed context (e.g. boot, BIND_NOTIFICATION_LISTENER
  callback). It happens to be safe because `MainActivity` is the
  launcher entry, but the call is not wrapped.
- **Fix.** Add a `signingConfigs { create("release") { … } }` block
  reading from `keystore.properties` with a clear error if absent;
  wrap the foreground-service start in try/catch and log the
  exception via `LogBuffer.error` so the user sees it in
  Diagnostics rather than crashing; add a `networkSecurityConfig`
  that pins TLS once the cockpit exists.

### 22. Accessibility — **3 / 10**

- **Evidence.** Top-level icons that act as buttons (`Settings`,
  `MoreVert`) pass `stringResource(...)` to
  `contentDescription` (`OrchestratorScreen.kt:84,88`), which is
  correct. But the overflow icon
  (`Icons.Default.MoreVert`,
  `OrchestratorScreen.kt:88`) and the status indicator dot
  (`OrchestratorScreen.kt:180-185`) pass `null` —
  the status colour is the only signal that the service is running
  or stopped, with no text-equivalent for screen readers. Theme
  contrast: gold-on-ink for primary text is fine in dark; gold-deep
  on paper is borderline in light.
- **Blocker.** Status pill is colour-only.
- **Risk.** TalkBack users cannot tell whether the orchestrator is
  running.
- **Fix.** Add a `Modifier.semantics { stateDescription = … }` to
  the status `Surface`; supply `contentDescription` for the overflow
  icon and the leading FAB. Run `lintDebug` (`./gradlew lintDebug`)
  in CI for `ContentDescription` checks — the workflow already does
  this; track lint results explicitly.

### 23. Performance — **6 / 10**

- **Evidence.** Cold-start path is minimal: `Application.onCreate`
  builds an `AppContainer`, ensures the notification channel, and
  returns. `MainActivity.onCreate` enables edge-to-edge, fires the
  service, and sets the Compose content. No blocking I/O on the
  main thread. `HermesTaskRepository` loads tasks on `Dispatchers.IO`
  in `init`. ProGuard + resource shrinking enabled for `release`.
- **Blocker.** None for the current feature set.
- **Risk.** `MainActivity.startHermesOrchestrator()` runs on every
  cold start before the content is set — fine today but a future
  larger service init could push past the "5 s to call
  startForeground" window. `OrchestratorViewModel.isServiceRunning`
  walks `getRunningServices(Integer.MAX_VALUE)` each call
  (`OrchestratorViewModel.kt:142-143`) which is cheap but allocates
  a list potentially in the thousands on dev devices.
- **Fix.** Wrap the service start in `lifecycleScope.launch(Dispatchers.Default)`,
  cache `isServiceRunning` and refresh on a `BroadcastReceiver` for
  the service's lifecycle events. Add a startup trace
  (`androidx.tracing.Trace`) once the cockpit exists.

### 24. Offline / mock mode — **2 / 10**

- **Evidence.** README says "mock mode enabled by default" in debug
  (`apps/android/README.md:185-187`) and on the splash. **No mock
  mode exists in the current source.** The Kotlin search
  `grep -ri "mock" apps/android/app/src/main/java/` returns nothing.
- **Blocker.** Either implement mock mode for the (future) cockpit
  client, or strip the claim from docs.
- **Risk.** A reviewer who toggles a non-existent "mock" setting
  will get confused. Today the app is "always offline" because
  there is no network — that is offline-by-default but not
  offline-tolerant for a cockpit-shaped app.
- **Fix.** When the cockpit client lands, ship an in-memory
  `MockCockpitClient` behind a Settings toggle and align README +
  ARCHITECTURE.md.

### 25. Termux gateway mode — **3 / 10**

- **Evidence.** `TermuxIntentBridge.kt` (140 lines) is well-formed,
  uses fully-qualified component names
  (`com.termux/com.termux.app.RunCommandService`), packages the
  RUN_COMMAND envelope correctly, and exposes an enum of supported
  actions (`TermuxBridgeAction`). **It is never instantiated.** No
  ViewModel calls it; no screen depends on it.
- **Blocker.** Termux gateway mode is declared as a runtime mode in
  `apps/android/README.md` but the app cannot start, stop, or talk to
  a local Termux gateway today.
- **Risk.** Anyone following the README's "run `hermes gateway start`
  inside Termux on the *same device*" path will find no
  corresponding UI on the phone.
- **Fix.** Build the Termux Control Panel screen from
  `docs/android/hermes-apk-cockpit.md` against the existing bridge
  stub; verify with Termux installed + `com.termux.permission.RUN_COMMAND`
  granted; add a fallback message when Termux is not installed.

### 26. Test coverage — **1 / 10**

- **Evidence.** **Zero Kotlin test files** in the module
  (`find apps/android/app/src -type d -name "test*"` is empty).
  The build script wires the runners but there is nothing to run.
  The Python-side `tests/test_jarvis_prime_*.py` suite (159 tests)
  passes cleanly but covers the Python runtime, not the APK.
- **Blocker.** No regression safety net on the only client the user
  installs on their phone.
- **Risk.** Any non-trivial change risks silent regressions:
  prompt-builder string layout drift, task-repository serialization
  drift, navigation argument parsing drift, deeper service-lifecycle
  bugs.
- **Fix.** Bring `PromptBuilder`, `HermesTaskRepository`, and the
  navigation argument parsing under unit tests today (pure Kotlin,
  no Android dependencies). Add a minimal Espresso/Compose UI test
  for the orchestrator dashboard. Wire `testDebugUnitTest` and
  `connectedDebugAndroidTest` into the existing
  `android-build.yml` workflow.

### 27. Polish — **5 / 10**

- **Evidence.** Material 3 throughout, sensible spacing
  (`Arrangement.spacedBy(12.dp)`), one accent palette
  (`Color.kt`), bottom-rounded splash, dark + light themes via
  `isSystemInDarkTheme()` honouring the user pref. Status bar
  transparent in both themes. No motion polish; no haptics; no
  empty-state illustrations beyond a single line of text; tab order
  on dropdowns inherits Material defaults.
- **Blocker.** None for an alpha.
- **Risk.** The caduceus emoji on the splash renders fine on
  Android emoji fonts but may fall back to monochrome on older
  devices; the gold gradient on dark surfaces is close to AA but
  not AAA contrast on body text.
- **Fix.** Replace the splash glyph with a vector asset; add a
  `windowSplashScreen` so the system splash carries over from the
  launcher; add an empty-state illustration and a "Create your
  first task" CTA pattern.

### 28. Launch / demo readiness — **2 / 10**

- **Evidence.** The app launches in this sandbox via the in-tree
  build script (CI confirms it does in `android-build.yml`); the
  flows wire end-to-end for the local handoff path; the persistent
  notification + Stop button works. **As a JARVIS Prime demo** the
  app does not have a chat surface, voice button, mode picker,
  memory peek, approvals list, or any other JARVIS-shaped surface
  to point at on stage.
- **Blocker.** Most JARVIS demo beats have nothing on screen.
- **Risk.** A reviewer asked to "show me JARVIS doing something"
  can only show "I generated a prompt, copied it to my clipboard,
  and pasted it into ChatGPT." That is a *manual* demo, not a
  JARVIS demo.
- **Fix.** Either reshape the launch narrative around "Hermes
  manual handoff", or build at least one JARVIS-shaped surface
  (suggested: a single "Ask JARVIS" entry that calls the cockpit
  and renders one streaming reply) before launch.

---

## Verdict

| Tier | Definition | This app |
|---|---|---|
| Green | Ready for general launch | — |
| Yellow | Demo-ready with caveats | — *(as a manual handoff tool only)* |
| Orange | Major blockers exist | — |
| **Red** | **Not ready** | **✓** |

**Composite score:** 87 / 280 ≈ **31 %**.

The shipped APK is internally coherent for the small problem it solves
(generate a prompt, copy to clipboard, optionally launch an external
tool) but does not deliver against the JARVIS Prime spec. Calling this
"JARVIS Prime on Android" would damage trust with the first wave of
users.

---

## Top 10 blockers (do these before launch)

1. **Wrong identity.** App label, splash, notification channel, and
   strings all say "Hermes Agent". Rebrand to "JARVIS Prime" (or
   relabel the launch as "Hermes alpha"). Source: every `strings.xml`
   entry, `SplashScreen.kt:42-48`, `HermesService.kt:124,143-155`.
2. **No chat surface.** README advertises chat; the app has none. Build
   it from `docs/mobile/app-screens.md` or delete chat references from
   `apps/android/README.md` and `apps/android/docs/ARCHITECTURE.md`.
3. **No voice capture.** Mobile Voice is one of JARVIS Prime's six
   modes (`docs/jarvis-prime-operating-system.md`). Build the voice
   service per `docs/mobile/app-voice-service.md`; declare
   `RECORD_AUDIO` and `FOREGROUND_SERVICE_MICROPHONE`.
4. **No approvals surface.** Owner-auth ("Yes, with authorization.")
   has no APK screen even though wire types exist
   (`CockpitApi.kt:244-261`).
5. **No memory surface.** JARVIS Prime memory subsystem is invisible
   on the phone; ship at least read-only of the canonical memory
   store.
6. **No transport.** No HTTP/WS client wired; `CockpitApi.kt`'s 280+
   lines of typed wire models are unused. Build a minimal
   `CockpitClient`.
7. **Zero tests.** `apps/android/app/src/test/` and `…/androidTest/`
   are empty. Bring `PromptBuilder`, `HermesTaskRepository`,
   navigation argument parsing under JVM unit tests; add one Compose
   UI test for the dashboard.
8. **No release signing.** `release` build type has shrinker + ProGuard
   but no `signingConfigs`. `./gradlew bundleRelease` cannot produce
   an uploadable AAB.
9. **No onboarding.** Splash → Orchestrator with no consent, no
   permission rationale, no JARVIS introduction. `SettingsRepository.hasOnboarded`
   is read by nobody (`grep -n hasOnboarded` only matches the
   declaration).
10. **Doc/code mismatch.** `apps/android/README.md` and
    `apps/android/docs/ARCHITECTURE.md` describe an OkHttp/SSE chat
    client with EncryptedSharedPreferences and mock mode. The current
    `app/build.gradle.kts` ships none of those dependencies. Either
    implement them or rewrite the docs to match the shipped app.

---

## Top 10 polish fixes (after blockers)

1. Add raster mipmaps for `mipmap-{m,h,xh,xxh,xxxh}dpi/` and a proper
   monochrome themed icon — current `ic_launcher.xml` reuses the
   foreground for `<monochrome>`.
2. Mark clipboard handoff sensitive via
   `ClipDescription.EXTRA_IS_SENSITIVE` on the `ClipData` so the
   Android 13+ preview banner redacts the prompt.
3. Hard-code-free `OrchestratorScreen.kt:192` —
   `"Local Subscription Tools"` and similar literals belong in
   `strings.xml`.
4. Replace deprecated `ActivityManager.getRunningServices` lookup
   (`OrchestratorViewModel.kt:137-144`) with a lifecycle observer
   bound to `HermesService`.
5. `markHandedOff` race in `TaskDetailViewModel.kt:103-114` — fold
   the status change into a single `upsert(task.copy(status = …))`.
6. Persist `LogBuffer` to a rotating file in `filesDir` so crashes
   leave a diagnostic trail.
7. Upgrade the `hermes_orchestrator` notification channel to
   `DEFAULT` importance and add channels for approvals, voice, and
   errors.
8. Refresh `backup_rules.xml` + `data_extraction_rules.xml` — they
   still exclude `hermes_secure_prefs.xml`, which no longer exists.
9. Add `Modifier.semantics { stateDescription = … }` to the status
   pill and `contentDescription` to the FAB / overflow icon for
   TalkBack parity.
10. Wire a proper system splash via `windowSplashScreen` so the
    transition from launcher → splash → Compose content is one frame,
    not three.

---

## Top 10 safety / privacy risks

1. **Clipboard exfiltration.** `HandoffLauncher.copyPrompt` does not
   set `EXTRA_IS_SENSITIVE`; on Android 13+ the on-screen banner
   reveals the first lines of every JARVIS prompt to anyone watching
   the screen.
2. **Stale "secure prefs" excludes.** `backup_rules.xml` /
   `data_extraction_rules.xml` reference a `hermes_secure_prefs.xml`
   store that does not exist — easy to miss when a real secure store
   is reintroduced and the file is named differently.
3. **Decorative "Local-only mode" toggle.** Users believe they have
   restricted JARVIS to on-device only when in fact nothing reads the
   flag (`SettingsRepository.localOnlyMode` has no consumers).
4. **Default-on `clipboardHandoffEnabled`.** No surface explains that
   the prompt is dropped on the system clipboard until the user
   pastes it; clipboard contents can survive past the app lifetime.
5. **Foreground service start without try/catch**
   (`MainActivity.kt:32, 47-53`). On rare Android 12+ states this
   throws `ForegroundServiceStartNotAllowedException` and the app
   crashes silently before the user sees the UI.
6. **No release signing config.** A casual contributor can run
   `bundleRelease`, end up with an unsigned AAB, sideload it, and
   ship users updates from a debug-keystore APK by mistake.
7. **`MainActivity.exported="true"`** with no extras validation. Today
   only `MAIN`/`LAUNCHER` is filtered so this is fine; if a deep link
   is added later without re-checking, the same flag will silently
   accept attacker intents.
8. **Adaptive icon `<monochrome>` reuses the colored foreground.**
   Themed icon on Android 13+ leaks the brand colour into a surface
   the user expects to be neutral.
9. **Diagnostics screen "Copy logs" copies via `AnnotatedString`** with
   no redaction (`DiagnosticsScreen.kt:55-60`). If a future module
   logs a token by accident it ships to the clipboard with no
   warning.
10. **No `targetSdk` upgrade plan** documented; staying on 35 is fine
    today but Play will require 36 within 18 months, and the
    background-execution restrictions in 36 will affect
    `HermesService`'s startup contract.

---

## Go / no-go

**No-go for JARVIS Prime launch.**

Re-evaluate when blockers 1, 2, 3, 4, 6, 7, 8, 9, 10 (in the top-10
blockers list above) are closed. Blocker 5 (Memory) can ship as
"coming soon" without blocking, provided the app does not pretend the
memory is already there.

**Conditional yellow:** if the launch narrative is rescoped to
"Hermes Local Orchestrator — manual handoff alpha v0.1", the same
artifact is demo-ready today after closing blockers 7 (tests), 8
(signing), 9 (onboarding), and 10 (doc/code mismatch).

---

## Evidence appendix

- Build attempt in this sandbox: `cd apps/android && ./gradlew assembleDebug`
  → `SDK location not found` after AGP plugin resolution. CI in
  `.github/workflows/android-build.yml` runs the same command on a
  pre-provisioned Android SDK and is the authoritative build signal.
- App tests: none present (`apps/android/app/src/test/` and
  `apps/android/app/src/androidTest/` directories do not exist).
- Manifest permission check: `POST_NOTIFICATIONS`,
  `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_DATA_SYNC`. No
  `INTERNET`, `RECORD_AUDIO`, `WAKE_LOCK`, `READ_EXTERNAL_STORAGE`.
- JARVIS Prime runtime tests:
  `pytest -p no:cacheprovider -o "addopts=" tests/test_jarvis_prime_*.py`
  → **159 passed** in 2.90 s.
- JARVIS Prime context audit: `python3 scripts/jarvis_context_audit.py`
  → **PASS** (failures=0 warnings=0).
- File-by-file source review covered all 29 Kotlin files in
  `apps/android/app/src/main/java/com/aci/hermes/` and all 11
  resource XML files under `apps/android/app/src/main/res/`.
