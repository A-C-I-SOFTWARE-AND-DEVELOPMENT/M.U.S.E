# MUSE — Android app deep audit

Audit date: 2026-05-26
Branch: `claude/jarvis-prime-app-audit-oLDQN`
Scope: `apps/android/` (native Android cockpit) and the
`hermes_cli/jarvis_prime/` runtime it must eventually present.

This document is the read-only inspection that precedes any code
changes. The build order lives in
[`jarvis-prime-app-finish-roadmap.md`](jarvis-prime-app-finish-roadmap.md);
the line-by-line gap list in
[`jarvis-prime-app-final-gap-map.md`](jarvis-prime-app-final-gap-map.md);
the permission policy in
[`jarvis-prime-app-permission-risk-register.md`](jarvis-prime-app-permission-risk-register.md);
the Python-runtime ↔ Android-surface mapping in
[`jarvis-prime-app-research-translation-map.md`](jarvis-prime-app-research-translation-map.md).

---

## 1. One-paragraph summary

The Android module ships a working **local-only task organizer +
prompt-handoff** app under the name *Hermes Agent*. It launches a
persistent foreground service, lets the user draft tasks, generates a
structured prompt for Codex / Claude Code / ChatGPT / Claude, copies it
to the clipboard, and optionally opens the target tool's installed app
or web fallback. There is **no networking code in the app today** — no
OkHttp dependency, no HTTP client, no gateway probe, no SSE reader, no
voice intake, no approval queue, no memory transparency, no audit
ledger, no Termux RUN_COMMAND firing path. Every MUSE concept
from `docs/jarvis-prime-operating-system.md` and the Python runtime in
`hermes_cli/jarvis_prime/` (modes, gates, owner authorization,
research briefs, persona prompts, memory, awareness, self-update
proposals) is **completely absent from the Android surface**. The
gap between the shipped product and the MUSE cockpit is
therefore a rebrand + a thin presentation layer over the existing
Python runtime, not a full rewrite.

---

## 2. Confirmed app architecture (what is actually there)

### 2.1 Module layout

```
apps/android/
├── README.md                       describes a network client (drifted; see §6)
├── docs/ARCHITECTURE.md            describes the network client (drifted; see §6)
├── app/
│   ├── build.gradle.kts            applicationId com.aci.hermes, minSdk 26, target 35
│   ├── proguard-rules.pro          kotlinx.serialization keep rules
│   └── src/main/
│       ├── AndroidManifest.xml     POST_NOTIFICATIONS, FOREGROUND_SERVICE(_DATA_SYNC)
│       ├── java/com/aci/hermes/
│       │   ├── MainActivity.kt           starts service, prompts notification permission
│       │   ├── HermesApplication.kt      holds AppContainer, ensures notif channel
│       │   ├── di/AppContainer.kt        hand-rolled DI (4 VMs, 3 repos)
│       │   ├── service/HermesService.kt  foreground service + persistent notification
│       │   ├── util/LogBuffer.kt         200-entry ring buffer (in-memory)
│       │   ├── data/
│       │   │   ├── model/
│       │   │   │   ├── AiToolProfile.kt         Codex / ChatGPT / Claude Code / Claude
│       │   │   │   ├── HermesTask.kt            7 task types, 7 statuses, 5 targets
│       │   │   │   └── HermesRole.kt            labels only (Orchestrator / Builder / …)
│       │   │   ├── orchestrator/
│       │   │   │   ├── PromptBuilder.kt         9 prompt sections + safety block
│       │   │   │   ├── HermesTaskRepository.kt  JSON file in filesDir
│       │   │   │   └── HandoffLauncher.kt       clipboard + ACTION_VIEW fallback
│       │   │   ├── termux/TermuxIntentBridge.kt STUB — builders only, no fire
│       │   │   ├── cockpit/CockpitApi.kt        Phase 18 wire types — no client
│       │   │   └── preferences/SettingsRepository.kt  DataStore (no Encrypted store)
│       │   └── ui/
│       │       ├── navigation/                  Screen + NavHost (5 routes)
│       │       ├── theme/                       Hermes gold + ink palette
│       │       └── screens/                     splash / orchestrator / task_detail
│       │                                        / settings / diagnostics
│       └── res/                                 strings.xml, Theme.HermesAgent, icons
└── gradle/libs.versions.toml       no OkHttp, no Retrofit, no Hilt, no Espresso writes
```

41 source files total under `app/src/`. **Zero** test files under
`src/test/` or `src/androidTest/` (the directories don't exist — see
§9). The CI workflow runs `assembleDebug` and `lintDebug` but no test
target, because there is nothing to run.

### 2.2 Process model

- `MainActivity.onCreate`
  - `enableEdgeToEdge()`
  - `startHermesOrchestrator()` →
    `ContextCompat.startForegroundService(HermesService)` with extras
    `launch_source=app_start`, `mode=local_subscription_tools`.
  - `maybeRequestNotificationPermission()` — fires
    `RequestPermission(POST_NOTIFICATIONS)` on every launch where it
    isn't already granted (Android 13+). Result is dropped.
  - `setContent { HermesTheme { HermesNavHost(container) } }`.
- `HermesService.onStartCommand`
  - Reads observational extras (`hermes_workspace`, `hermes_mode`,
    `hermes_agent`, `hermes_debug`); logs them; **does nothing else
    with them** (per README "Reality check" callout).
  - Posts a low-importance persistent notification with title
    *"Hermes Orchestrator Running"*, body *"Hermes is coordinating
    your local AI workflow"*, and a *Stop* action.
  - Calls `startForeground(NOTIFICATION_ID, notification,
    FOREGROUND_SERVICE_TYPE_DATA_SYNC)` on API 34+.
- All UI lives in the same process; ViewModels are constructed by
  `AppContainer.<screen>VmFactory()`; there is no Hilt or Koin.

### 2.3 Data flow

```
Compose Screen ──StateFlow──▶ ViewModel ──suspend──▶ Repository ──File I/O──▶ filesDir
                                  │
                                  ├──▶ HandoffLauncher → ClipboardManager / ACTION_VIEW
                                  └──▶ HermesService (start / stop)
```

There is no second arrow leaving the device. The dashed "gateway"
arrow in `docs/ARCHITECTURE.md` does not exist in code.

### 2.4 Persistence

- `DataStore<Preferences>` — name `hermes_settings`. Keys:
  `theme_mode`, `onboarded`, `preferred_builder`, `preferred_reviewer`,
  `use_api_keys`, `local_only_mode`, `allow_external_app_opening`,
  `clipboard_handoff_enabled`, `show_safety_warnings`.
- `HermesTaskRepository` — single JSON envelope (`hermes_tasks.json`)
  in `filesDir`. Tmp-file-rename atomic write. No SQL, no Room.
- `LogBuffer` — in-memory only, hard-capped at 200 entries.
- `EncryptedSharedPreferences` — **not present** in code. The
  `apps/android/README.md` claim that tokens are stored in
  `hermes_secure_prefs.xml` and the `data_extraction_rules.xml` /
  `backup_rules.xml` exclusion for that file are leftover from a prior
  surface; the Kotlin reference was removed when Chat/Provider was
  retired (`SettingsRepository.kt:20-21` comment confirms).

---

## 3. Screens that exist today

Source of truth: `apps/android/app/src/main/java/com/aci/hermes/ui/navigation/Screen.kt`.

| Screen     | Composable           | Role                                                                                          |
|------------|----------------------|-----------------------------------------------------------------------------------------------|
| Splash     | `SplashScreen`       | Caduceus glyph + "Hermes Agent" label + spinner; 600 ms delay then pops into Orchestrator.    |
| Orchestrator | `OrchestratorScreen` | Dashboard: service status card, AI tool cards (×4), task list, optional safety banner.        |
| TaskDetail | `TaskDetailScreen`   | Title / description / workspace / type / target / status / notes; prompt preview; copy/open.  |
| Settings   | `SettingsScreen`     | Theme + preferred builder/reviewer + 5 toggles + about + reset all.                           |
| Diagnostics | `DiagnosticsScreen` | App version + build type + last error + scrollable log buffer with copy / clear / refresh.    |

The README's *Screens* table — splash / setup / provider / chat /
status / settings / diagnostics — is stale. Setup, provider, chat,
and status do not exist in code. The shipped Orchestrator screen has
no equivalent row in the README table.

## 4. Routes that exist today

Source of truth: `apps/android/app/src/main/java/com/aci/hermes/ui/navigation/Screen.kt`.

| Route                                  | Args                                | Notes                                                                                  |
|----------------------------------------|-------------------------------------|----------------------------------------------------------------------------------------|
| `splash`                               | —                                   | Start destination; pop-up-to itself on navigate.                                       |
| `orchestrator`                         | —                                   | Dashboard; entry hub.                                                                  |
| `task_detail/{taskId}?target={target}` | `taskId` string, `target` nullable  | `taskId="new"` opens a draft; `target` seeds `TargetTool` for new tasks.               |
| `settings`                             | —                                   | Pushed from Orchestrator top-bar.                                                      |
| `diagnostics`                          | —                                   | Pushed from Orchestrator overflow or Settings.                                         |

There are no deep links registered in the manifest beyond
`MAIN`/`LAUNCHER` on `MainActivity`. No NavDeepLinkRequest, no nav
graph for approvals, no per-task notification deep link.

## 5. App naming that exists today

| Surface                                                   | Value                               |
|-----------------------------------------------------------|-------------------------------------|
| `applicationId`                                           | `com.aci.hermes`                    |
| Debug applicationId suffix                                | `.debug`                            |
| Kotlin package root                                       | `com.aci.hermes`                    |
| Gradle root project name                                  | `HermesAgent`                       |
| App display label (`strings.xml`)                         | `Hermes Agent`                      |
| Splash text (`SplashScreen.kt:46`)                        | `Hermes Agent`                      |
| Theme parent style                                        | `Theme.HermesAgent`                 |
| Foreground service notification title                     | `Hermes Orchestrator Running`       |
| Foreground service notification body                      | `Hermes is coordinating your local AI workflow.` |
| Foreground service stop action constant                   | `com.aci.hermes.action.STOP_ORCHESTRATOR` |
| Notification channel id                                   | `hermes_orchestrator`               |
| Notification channel display name                         | `Hermes Orchestrator`               |
| Task repository file                                      | `hermes_tasks.json`                 |
| DataStore name                                            | `hermes_settings`                   |
| Top bar title (Orchestrator)                              | `Hermes Orchestrator`               |
| Safety banner body                                        | "Hermes does not bypass OpenAI or Anthropic…" |
| Diagnostic copy label                                     | `Hermes prompt`                     |
| README headline                                           | `Hermes Agent — Android (native companion app)` |
| Architecture doc                                          | `Hermes Agent Android module`       |

There is **zero** use of the strings `MUSE`, `MUSE`, or
`MUSE` anywhere under `apps/android/`. Confirmed via
`grep -ri "jarvis" apps/android/` returning nothing.

## 6. What still says "Hermes Agent"

Everything user-visible and most internal surface. Specifically: the
APK label, every string resource, every notification, every Composable
title, every package import, the README, the architecture doc, the
build-time gradle docstring, the icon caption (caduceus
mythologically tied to Hermes), the persistent service tag
(`HermesService`), and the `com.aci.hermes.action.STOP_ORCHESTRATOR`
intent action. The Gradle project name is also `HermesAgent`.

The two doc files that contradict the code (`apps/android/README.md`
and `apps/android/docs/ARCHITECTURE.md`) **still describe a network
client** with `/v1/health`, `/v1/chat` SSE, EncryptedSharedPreferences,
OkHttp, and a chat/provider/status screen stack. None of that exists
in the codebase. Treat both files as stale fiction until the MUSE
Prime build replaces them.

## 7. What can safely become MUSE

Safe to change in the first wave (no external contracts depend on
these — purely user-visible labels):

- `strings.xml` → `app_name`, all `orchestrator_*` titles and bodies,
  the safety banner, the diagnostics labels.
- `SplashScreen.kt:46` — the visible "Hermes Agent" headline.
- `Theme.HermesAgent` style name (rename to `Theme.JarvisPrime`;
  manifest references update in lockstep).
- `themes.xml` style names.
- Notification title / body / channel display name (channel **id**
  must stay or migrate carefully — see §8).
- README / ARCHITECTURE.md rewrite (see [research-translation map](jarvis-prime-app-research-translation-map.md)).
- New launcher icon — current caduceus is a Hermes glyph; replace
  with a MUSE mark.
- Foreground service display title (the user-visible text on the
  notification, not the Java class name).
- Splash glyph (`☤`) — replace with the MUSE mark.

## 8. What must remain "Hermes" internally for compatibility

Treat each of these as **internal contract** and only change with a
documented migration:

| Identifier                                  | Why it must stay (or stay with migration)                                              |
|---------------------------------------------|----------------------------------------------------------------------------------------|
| `applicationId = "com.aci.hermes"`          | Changing the package id makes the new APK a different app — users have to uninstall the old one, lose all tasks. If we ever change it, plan a one-time migration + uninstall toast. Recommended: keep `com.aci.hermes` as the package id and ship the display label as "MUSE". |
| `com.aci.hermes` Kotlin package roots       | Renaming is mechanical but blast-radius is the entire `apps/android/` source tree and the ProGuard keep rules in `proguard-rules.pro`. Defer until everything else is green. |
| `com.aci.hermes.action.STOP_ORCHESTRATOR`   | Documented in `apps/android/README.md` §"Service intent contract" for ADB / Termux integration. External callers will break. |
| `EXTRA_HERMES_*` intent extras              | Same as STOP_ORCHESTRATOR — README's "Service intent contract" is a public contract. |
| Notification channel id `hermes_orchestrator` | Channels are user-modifiable settings; renaming creates a duplicate channel and re-imports user importance settings. Keep id; change display name only. |
| `hermes_tasks.json` filename                | On-disk file in `filesDir` carrying the user's task history. If the rename happens, write a one-shot migration on first launch and keep a no-op fallback for one release. |
| `hermes_settings` DataStore name            | Same as above — user prefs are stored under this name. |
| `HermesService` Java class name             | Used in the foreground service component name and quoted in the README for ADB launches. Renaming the class also renames the component, breaks ADB launches. |
| `HermesTaskRepository` etc.                 | Pure internal — safe to rename but every callsite under `ui/screens/orchestrator/` has to update. Low value before the cockpit work lands. |

## 9. Gateway / connection features

### 9.1 What exists in code

- `data/cockpit/CockpitApi.kt` — `@Serializable` Kotlin data classes
  mirroring the Phase 18 wire format
  (`RuntimeStatus`, `DispatchJobRequest`, `DiffSnapshot`,
  `ValidationGate`, `PendingApproval`, `EventBatch`, …) and two
  enums (`JobStatus`, `PublishState`).
- `data/termux/TermuxIntentBridge.kt` — `buildHermesIntent(…)`,
  `buildOpenJobFolderIntent(…)`, `buildOpenTermuxIntent()`,
  `isTermuxInstalled()`. **No `fire(…)` method**, no
  `startService`, no permission probe. Comment at top labels it a
  "Phase 18 cockpit ↔ Termux intent bridge — stub."
- `HandoffLauncher` — clipboard copy + `ACTION_VIEW` fallback for
  ChatGPT / Codex / Claude web URLs. This is the only outbound
  pathway from the app today.

### 9.2 What is documented but not wired

- `BuildConfig.DEFAULT_GATEWAY_URL` — documented in
  `apps/android/gradle.properties:14-32` and in the README, but the
  `build.gradle.kts` has **no `buildConfigField` declaration** that
  defines it. Anything reading `BuildConfig.DEFAULT_GATEWAY_URL`
  today would fail to compile.
- `/v1/health` probe — documented in README §"Connection state
  model" and ARCHITECTURE.md §6. No probe code exists.
- `/v1/chat` SSE stream — documented in ARCHITECTURE.md §6. No SSE
  reader exists; OkHttp-SSE is not a declared dependency.
- All `/v1/cockpit/*` routes from `docs/android/muse-apk-api-contract.md`
  (`workers`, `jobs`, `files/tree`, `files/snapshot`, `diff`,
  `validation`, `publish/preview`, `publish`, `approvals`,
  `events`).
- `RECORD_AUDIO` + `foregroundServiceType="microphone"` — referenced
  by `docs/mobile/muse-app-module-plan.md` §"Voice layer plan" but
  **not declared** in the manifest. Aligned with §15.
- `EncryptedSharedPreferences` for the gateway bearer token —
  referenced by `data_extraction_rules.xml` and `backup_rules.xml`
  exclusions, but the Kotlin code that wrote to that file no longer
  exists.

## 10. Local orchestrator features

What ships today in the *Hermes Orchestrator* (local) flow:

| Feature                          | Status         | File                                                                 |
|----------------------------------|----------------|----------------------------------------------------------------------|
| Foreground service               | Working        | `HermesService.kt`                                                   |
| Service start on app launch      | Working        | `MainActivity.kt:32`                                                 |
| Service start/stop from UI       | Working        | `OrchestratorViewModel.kt:78,89`                                     |
| Persistent notification          | Working        | `HermesService.buildNotification`                                    |
| Notification *Stop* action       | Working        | `HermesService.onStartCommand:48`                                    |
| Task list dashboard              | Working        | `OrchestratorScreen.kt:148`                                          |
| Per-task editor                  | Working        | `TaskDetailScreen.kt`                                                |
| 7 task types / 7 statuses        | Working        | `HermesTask.kt:24-35`                                                |
| Target-tool selection            | Working        | `HermesTask.kt:38`                                                   |
| Prompt builder (9 sections)      | Working        | `PromptBuilder.kt`                                                   |
| Safety section invariant         | Working        | `PromptBuilder.SAFETY_BLOCK`                                         |
| Clipboard copy                   | Working        | `HandoffLauncher.copyPrompt`                                         |
| Optional external-app launch     | Working        | `HandoffLauncher.openOfficialTool`                                   |
| Tool catalogue (4 profiles)      | Working        | `DefaultToolProfiles`                                                |
| JSON envelope persistence        | Working        | `HermesTaskRepository.kt`                                            |
| Settings & toggles               | Working        | `SettingsRepository.kt`                                              |
| Reset-all dialog                 | Working        | `SettingsScreen.kt:177`                                              |
| Theme follow-system / dark / light | Working      | `SettingsRepository.themeMode`                                       |
| Diagnostics log buffer           | Working        | `LogBuffer.kt` / `DiagnosticsScreen.kt`                              |
| Last-error surface               | Working        | `LogBuffer._lastError` → `DiagnosticsUiState.lastError`              |

What is documented but **not** shipped on the local path:

- Per-task hand-off proof (no record of when/where the prompt was
  pasted).
- Result ingestion (no "paste back the model's reply" return path).
- Re-handoff cycle (no "did the worker fail, retry with reviewer"
  flow — has to be edited manually).
- Multi-target chained handoff (build → review → audit chain).

## 11. Task features that exist today

- 7 types (`BUILD`, `REVIEW`, `AUDIT`, `DEBUG`, `REFACTOR`,
  `RESEARCH`, `PLANNING`).
- 7 statuses (`DRAFT`, `READY_FOR_HANDOFF`, `HANDED_TO_CODEX`,
  `HANDED_TO_CLAUDE`, `IN_REVIEW`, `NEEDS_REVISION`, `COMPLETE`).
- 5 targets (`CODEX`, `CHATGPT`, `CLAUDE_CODE`, `CLAUDE`, `MANUAL`).
- One UUID per task; created/updated timestamps; review/result/next-action notes.
- Order: newest first by insertion (`upsert` prepends for new ids).
- Workspace path stored as free-form string (no `DocumentFile`/SAF).
- No tag/label, no priority, no due date, no parent/child link, no
  PR url, no commit sha, no per-task evidence list.

## 12. Approval features that are missing

The Phase 18 spec (`docs/android/muse-apk-api-contract.md` §3.8
*Pending approvals*) and the user guide
(`docs/mobile/mobile-app-guide.md` §"How approvals work on the
lockscreen") describe a full approval pipeline. The Android app has
**none** of it:

- No `ApprovalGateScreen` Composable.
- No `Approvals` route in `Screen.kt`.
- No `PendingApproval` UI rendering (the data class exists in
  `CockpitApi.kt` but is unused).
- No notification per pending approval — the only notification is the
  always-on foreground service.
- No notification action buttons for *Approve* / *Deny* / *Defer*.
- No "high-risk approvals deferred while driving" guard.
- No `decide` POST path.
- No owner-authorization phrase (`Yes, with authorization.`) — the
  Python runtime enforces this in `hermes_cli/jarvis_prime/owner_auth.py`
  but the Android app never asks.
- No spend-money / publish-publicly / OAuth / deploy gate equivalents.

## 13. Memory transparency features that are missing

The MUSE runtime carries first-class memory
(`hermes_cli/jarvis_prime/memory.py` — `MemoryRecord`, `MemoryStore`,
JSONL journal, deduplication, expiry). On Android:

- No memory view screen.
- No fact list with source / created-at / expires-at.
- No "save this as durable memory" affordance.
- No "forget this fact" affordance.
- No memory expiry visibility.
- No personality / preferences view.
- No goals / aspirations view.
- No memory rules surfacing (what gets saved, what doesn't).
- `LogBuffer` is the closest analogue and is ephemeral by design.

## 14. Audit / proof features that are missing

The MUSE gate set (`hermes_cli/jarvis_prime/gates.py` —
`Gate`, `GateOutcome`, `GateResult`, `GateSummary`, eight gates from
`docs/jarvis-verification-gates.md`) produces structured outcomes the
cockpit could render. On Android:

- No verification gates panel.
- No decision ledger reader (the orchestrator writes
  `~/.hermes/jobs/<job-id>/ledger.jsonl` but nothing on the phone
  surfaces it).
- No PR-ready summary view.
- No diff view.
- No rollback path display.
- No "evidence required" list per task.
- No "tests run / not run" badge.
- No proof export (PDF / share-sheet) for compliance evidence.

## 15. Interactive icon features that are missing

- No app shortcuts (`<shortcuts>` XML).
- No quick settings tile.
- No home-screen widget.
- No app dynamic shortcut (`ShortcutManager.setDynamicShortcuts`).
- No conversation shortcut / notification bubble.
- No per-screen FAB beyond *New task*.
- Notification has one action (*Stop*) and one default content
  intent (open app). No *Approve* / *Defer* / *Open task* /
  *Open job folder in Termux* / *Open PR* actions.
- No app icon badging via `setShowBadge` — explicitly disabled
  (`HermesService.kt:154`).

## 16. Voice features that are missing

The voice-first architecture is fully designed
(`docs/voice/voice-first-architecture.md`, `docs/voice/driving-mode-safety.md`,
`docs/mobile/app-voice-service.md`, `docs/mobile-voice-development-workflow.md`)
and the Python intake works (Phase 19). On Android:

- No `RECORD_AUDIO` permission declared.
- No `MICROPHONE` foreground service type.
- No `AudioRecord` or `MediaRecorder` usage.
- No mic permission prompt path.
- No push-to-talk button.
- No wake-event capture.
- No driving-mode toggle (and no high-risk-approval auto-deferral
  while driving).
- No TTS readback.
- No transcript intake screen.
- No voice-mode awareness in any ViewModel (the MUSE
  `MOBILE_VOICE_FORMAT` persona prompt is unused).

## 17. Notification behavior that exists today

- Channel id `hermes_orchestrator`, importance `LOW`, show-badge
  off, description "Persistent indicator that Hermes is coordinating
  local AI workflows."
- One notification posted: title *"Hermes Orchestrator Running"*,
  body *"Hermes is coordinating your local AI workflow."*, ongoing,
  alert-only-once, priority LOW.
- Content intent: opens MainActivity, single-top.
- Single action: *Stop* → `ACTION_STOP` → `stopSelf()`.
- No per-event notifications.
- No grouping / inbox style.
- No notification updates (the same ongoing notification stays for
  the life of the service).

## 18. Notification permission on startup

**Yes.** `MainActivity.onCreate` calls
`maybeRequestNotificationPermission()` (lines 55-63). On Android 13+
(TIRAMISU), if the permission is not already granted, it fires
`requestNotificationPermission.launch(POST_NOTIFICATIONS)`
unconditionally, every cold start where it hasn't been granted. The
result callback is a no-op comment — denial is not retried, but the
prompt comes back the next time the user launches the app.

Reason it's wired this way: the service is started in `onCreate`
**before** the prompt is launched, so the persistent notification can
appear immediately if the user grants the permission. On denial, the
service still runs (foreground service type `DATA_SYNC` does not
require POST_NOTIFICATIONS to *exist*, only to *display* on Android
13+); the user just won't see the notification.

Implication for MUSE: the current flow is intentional but
abrupt. The MUSE cockpit should keep the permission request
but route it through onboarding so the user understands *why* the
persistent notification matters before being asked.

## 19. Android permissions currently declared

`apps/android/app/src/main/AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
```

That is the complete list. There is **no** `INTERNET` permission
declared. The compiler / linker would normally inject `INTERNET` when
HTTP code is present; the absence is a strong second confirmation
that no networking code is currently in the app.

Also absent (good): no `RECORD_AUDIO`, no `READ_CONTACTS`, no
`READ_SMS`, no `CALL_PHONE`, no `READ_PHONE_STATE`, no
`ACCESS_FINE_LOCATION`, no `ACCESS_BACKGROUND_LOCATION`, no
`SYSTEM_ALERT_WINDOW`, no `BIND_DEVICE_ADMIN`, no
`REQUEST_INSTALL_PACKAGES`, no `RECEIVE_BOOT_COMPLETED`, no
`POST_NOTIFICATIONS` on a non-foreground use case, no
`READ_EXTERNAL_STORAGE` / `WRITE_EXTERNAL_STORAGE`, no
`MANAGE_EXTERNAL_STORAGE`, no `<queries>` block.

## 20. Permissions that must NOT be added

Tracked in detail in
[`jarvis-prime-app-permission-risk-register.md`](jarvis-prime-app-permission-risk-register.md).
Headline list: `READ_CONTACTS`, `READ_SMS`, `RECEIVE_SMS`,
`CALL_PHONE`, `READ_PHONE_STATE`, `READ_CALL_LOG`,
`ACCESS_FINE_LOCATION` (and background), `BODY_SENSORS`,
`READ_EXTERNAL_STORAGE` / `WRITE_EXTERNAL_STORAGE`,
`MANAGE_EXTERNAL_STORAGE`, `SYSTEM_ALERT_WINDOW`,
`BIND_DEVICE_ADMIN`, `BIND_ACCESSIBILITY_SERVICE`,
`PACKAGE_USAGE_STATS`, `QUERY_ALL_PACKAGES`,
`REQUEST_INSTALL_PACKAGES`, `RECEIVE_BOOT_COMPLETED`,
`SCHEDULE_EXACT_ALARM`, `MANAGE_OWN_CALLS`, `RECORD_AUDIO`
in background, `CAMERA`, anything Play Console flags as a
sensitive permission requiring a declared use case.

The only permissions that *will* need to be added for MUSE
cockpit milestones (in roughly this order):

- `INTERNET` — gateway calls.
- `ACCESS_NETWORK_STATE` — surface offline state cleanly.
- `RECORD_AUDIO` — voice intake (Mobile Voice Mode), behind a feature
  flag and lazy-requested only when the user opts in.
- `FOREGROUND_SERVICE_MICROPHONE` — only while actively capturing
  audio; the existing `dataSync` type stays the default.
- `<queries>` for Termux packages
  (`com.termux`, `com.termux.files`) so `getLaunchIntentForPackage`
  returns non-null on Android 11+. Already implied by
  `TermuxIntentBridge` but not yet declared.

## 21. Tests that exist today

**None.** There is no `apps/android/app/src/test/` directory, no
`apps/android/app/src/androidTest/` directory, no Robolectric set-up,
no Espresso instrumented test, no Compose UI test, no JUnit class
file. `build.gradle.kts:93-96` declares the dependencies (`junit`,
`androidx-test-junit`, `androidx-test-espresso-core`) but there are
zero test sources to compile against them.

CI runs `assembleDebug` + `lintDebug`. There is no
`test` / `connectedAndroidTest` step. A regression in MVP behavior
will only be caught at runtime.

The Python-side MUSE runtime is the opposite — 159 tests pass
in `tests/test_jarvis_prime_*.py` (see §23).

## 22. Tests that are missing (minimum we'd want before MUSE ships)

Unit (JVM):

- `PromptBuilder.build` — happy paths for each `TargetTool`,
  invariant safety block, blank-title behavior, workspace null
  handling.
- `HermesTaskRepository` — upsert / setStatus / delete / deleteAll;
  file round-trip; envelope versioning forward compatibility.
- `SettingsRepository` — default values, persist round-trip,
  `resetAll` clears everything.
- `HandoffLauncher.copyPrompt` (Robolectric) — ClipboardManager
  interaction.
- `Screen.TaskDetail.forNew(target)` — URL encoding for the optional
  query arg.
- `LogBuffer` — ring-buffer cap, `lastError` flow, atomic update
  under concurrent calls.

Instrumented / Compose:

- `OrchestratorScreen` empty state vs populated state.
- `TaskDetailScreen` field round-trip.
- `SettingsScreen` toggle persistence visual.
- `DiagnosticsScreen` log display + copy button.
- Notification permission flow on Android 13+ (Espresso + UI
  Automator).
- Foreground service start / stop end-to-end.

MUSE cockpit features (additive):

- Gate display per task / job.
- Approvals list + decide.
- Owner-authorization phrase capture.
- Voice intake permission gating.
- Memory view list + forget.
- Mode-aware persona prompt selection (six modes).

## 23. Build / test status (this audit run)

- `python3 -m pytest tests/test_jarvis_prime_*.py -q` — **159 passed
  in 2.91 s** (13 test files, runtime / modes / persona / gates /
  memory / router / reasoning / research / epistemics / owner_auth /
  onboarding / self_update / communication_style / social_research).
- `cd apps/android && ./gradlew assembleDebug` — **fails** in this
  remote environment. Two reasons:
  1. Android SDK not installed (`ANDROID_HOME` unset);
     plugins downloaded successfully but
     `:app:compileDebugJavaWithJavac` requires
     `local.properties` or `ANDROID_HOME`.
  2. Outbound network is allowed for Gradle plugin resolution but
     not configured for an Android SDK install in this container.
  The CI workflow at `.github/workflows/android-build.yml` runs
  `./gradlew assembleDebug` successfully on a runner with
  `android-actions/setup-android@v3` — that is the canonical build.

- `./gradlew lintDebug` — not attempted here for the same
  SDK-absent reason; runs on CI.
- No Android unit or instrumented tests exist to run (§21).

## 24. Top 20 gaps (one-line each — full detail in the gap map)

1. App branding still says "Hermes Agent" everywhere user-visible.
2. README and ARCHITECTURE.md describe a network client that doesn't
   exist in code — major documentation drift.
3. No HTTP client in the app (no OkHttp dep, no `INTERNET` permission,
   no gateway probe).
4. `BuildConfig.DEFAULT_GATEWAY_URL` referenced in docs but not
   declared in `build.gradle.kts`.
5. `TermuxIntentBridge` is a stub — no fire path, no permission probe,
   no result capture.
6. `CockpitApi.kt` defines all Phase 18 wire types but no client
   uses them.
7. No tests exist in `apps/android/app/src/test/` or `androidTest/`.
8. Splash glyph is the Hermes caduceus — needs MUSE mark.
9. No approval queue UI / no per-approval notification.
10. No memory transparency surface (memory store unused on Android).
11. No verification-gate display (gates module unused on Android).
12. No mode awareness (the six MUSE modes are not represented
    in the UI or settings).
13. No owner-authorization phrase capture.
14. No voice intake / driving-mode toggle.
15. Notification permission prompt fires unconditionally on startup —
    no onboarding rationale screen.
16. No app shortcuts / quick tiles / widgets / per-event notification
    actions.
17. Task model has no PR url, no commit sha, no evidence list, no
    parent link.
18. `EncryptedSharedPreferences` claimed in docs / backup rules but
    removed from code — `backup_rules.xml` / `data_extraction_rules.xml`
    reference a file that no longer exists.
19. `HermesService` extras are observational only — no actual hand-off
    to the Python runtime via Termux / loopback.
20. Foreground notification has only one action (*Stop*) and never
    updates — no per-job, per-approval, or driving-mode state shown.

## 25. Blockers

None of the gaps above are blockers in the literal sense — the app
compiles, the CI runs, the Python runtime is healthy. The two items
that need a decision before Wave 1 lands:

- **Display name vs package id.** MUSE can ship as the
  *user-visible* label without changing `com.aci.hermes`. Recommended
  to keep the package id for the first three waves; revisit only if
  the Play Store listing strategy requires a different id.
- **Notification channel migration.** Renaming the channel display
  name is safe; renaming the channel **id** orphans the user's
  importance setting. Recommendation: keep `hermes_orchestrator` as
  the channel id, change display name to "MUSE".

The blocker register lives in the
[roadmap](jarvis-prime-app-finish-roadmap.md#blockers).
