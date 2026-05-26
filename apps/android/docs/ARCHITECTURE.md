# Architecture — Jarvis Prime Android

This document describes the Jarvis Prime mobile app — the Android body
of the Jarvis Prime operating partner. The phone is the command
center, the app is the body, the interactive icon is the visible
presence, the gateway is the brain, and workers run outside this
process.

The app lives at `apps/android` (do not move it). Package is
`com.aci.hermes` (preserved for compatibility with existing intents,
foreground service registrations, and ADB scripts). The user-facing
identity is Jarvis Prime; legacy Hermes naming is preserved only
where renaming would break a wire contract.

## Module layout

```
apps/android/
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/aci/hermes/
│       │   ├── HermesApplication.kt              # process-wide DI host
│       │   ├── MainActivity.kt                   # quiet entry — no auto-prompts
│       │   ├── di/AppContainer.kt                # hand-rolled DI
│       │   ├── safety/                           # Permission Kernel + Emergency Stop
│       │   ├── conversation/                     # Conversation Engine + Store
│       │   ├── data/memory/                      # Memory Tree + Repository
│       │   ├── gateway/                          # Gateway client + state
│       │   ├── workers/                          # Worker Execution Lane
│       │   ├── events/                           # Event Spine
│       │   ├── approvals/                        # Approval queue + Proof Engine
│       │   ├── audit/                            # Audit Log (append-only, persisted)
│       │   ├── voice/                            # Hold-to-talk capture
│       │   ├── social/                           # Social Intelligence (summariser)
│       │   ├── service/HermesService.kt          # foreground service (gateway watch)
│       │   └── ui/
│       │       ├── theme/                        # Jarvis palette + Material 3
│       │       ├── components/                   # Interactive icon + Emergency stop bar
│       │       ├── permissions/                  # Education sheet + Router
│       │       ├── navigation/                   # NavHost + route sealed class
│       │       └── screens/                      # one folder per screen, each with VM
│       └── res/                                  # strings, themes, backup rules
├── docs/
└── gradle/
```

## Jarvis Prime modules

| Module | What it owns | Where |
|---|---|---|
| Permission Kernel | Single point for every Android runtime permission. Sealed `NextStep` API. The Activity is a thin bridge — never calls the OS dialog directly. | `safety/` |
| Emergency Stop | Always-reachable controller. Listener fan-out, idempotent engage, exception-isolated. | `safety/EmergencyStop.kt` |
| Memory Tree | The owner-visible record of what Jarvis Prime remembers. Pinned-promotion-on-forget so important memories survive their parent. | `data/memory/` |
| Conversation Engine | Cold-flow boundary between UI and runtime. Built-in key redaction. Mock provider for offline. | `conversation/` |
| Gateway | Narrow client for the off-device runtime. Mock client by default; real OkHttp client lands in a follow-up. | `gateway/` |
| Worker Lane | Per-worker rollup with health (OFFLINE / IDLE / QUEUED / WORKING). | `workers/` |
| Event Spine | In-process append-only bus. Bounded buffer; severity rollup. | `events/` |
| Approvals + Proof Engine | Tier-aware confirmation flow (RISKY 1 / SERIOUS 2 / CRITICAL 2 + impact + rollback). Proof Engine renders what the owner sees at decision time; the same text is written into the audit log. | `approvals/` |
| Audit Log | Append-only, persisted under `<filesDir>/jarvis_audit/audit.jsonl`. Subscribes to the Event Spine at construction. | `audit/` |
| Voice | Phase-1 hold-to-talk only. Lifecycle controller (IDLE → ARMED → CAPTURING → ENDED). | `voice/` |
| Interactive Icon | The visible presence. Five states: IDLE, LISTENING, WORKING, ALERT, CRITICAL. | `ui/components/JarvisInteractiveIcon.kt` |
| Social Intelligence | Read-only summariser that fuses memory + conversation into a one-line dashboard sentence. | `social/` |

## MVVM pattern

Each screen is `<Name>Screen.kt` (Composable) + `<Name>ViewModel.kt`.
The ViewModel:

- Holds a single `StateFlow<UiState>` data class.
- Mutates state via `_state.update { it.copy(...) }`.
- Exposes side-effecting methods that launch inside `viewModelScope`.

ViewModels are constructed by `AppContainer.<screen>VmFactory()` and
handed to `androidx.lifecycle.viewmodel.compose.viewModel(factory = ...)`.
There's no Hilt because the dependency graph is small enough that the
indirection costs more than the wiring.

## Phase 1 safety rules

These are enforced by the code, not just policy. Tests in
`safety/`, `approvals/`, and `voice/` lock them down:

1. No SMS permission. (`JarvisPermission.phase1Banned` asserts.)
2. No Call Log permission. (Same.)
3. No overlay (SYSTEM_ALERT_WINDOW) permission. (Same.)
4. No automatic notification permission dialog on first launch.
   (`MainActivity` no longer calls `RequestPermission().launch()` at
   startup; the kernel refuses to launch the OS dialog from
   NOT_REQUESTED without going through the education sheet first.)
5. Notification permission only after education / user action.
   (`PermissionRouter` enforces.)
6. Microphone permission only after user taps Voice.
   (`VoiceViewModel` checks `PermissionState` before arming capture.)
7. No always-listening. (`VoiceCapture` is hold-to-talk only —
   `start()` refuses without an explicit `arm()`.)
8. Risky actions ask once. (`RiskTier.RISKY.confirmationsRequired = 1`.)
9. Serious actions ask twice. (`RiskTier.SERIOUS.confirmationsRequired = 2`.)
10. Critical actions require impact report + rollback + two confirmations.
    (`Approval`'s init block refuses CRITICAL without an
    `ImpactReport`; the report carries a `rollback`.)
11. Emergency stop is always reachable. (`EmergencyStopBar` sits
    directly under the hero card on the dashboard; the controller is
    idempotent and exception-isolated.)
12. App never bypasses the Permission Kernel. (All callers route
    through `PermissionRouter`; the kernel is the only thing holding
    the `SystemPromptLauncher` reference.)
13. App never directly executes destructive actions. (The approval
    queue is the only path; the app surfaces the decision and writes
    proof — it does not run the action.)
14. App never stores gateway-side secrets. (`GatewayConfig.bearerToken`
    is held only in process; no DataStore key persists it.)
15. No done claim without tests or evidence. (Every module ships JVM
    unit tests under `app/src/test/java/`.)

## Storage

Three stores, deliberate split:

- DataStore (`hermes_settings`) — non-secret prefs: theme, builder /
  reviewer preference, allow-external-app, etc.
- DataStore (`jarvis_memory_v1`) — Memory Tree JSON snapshot.
- File (`<filesDir>/jarvis_audit/audit.jsonl`) — append-only audit
  records. Excluded from cloud backup and device transfer via the
  updated `data_extraction_rules.xml` and `backup_rules.xml`.

There is no `EncryptedSharedPreferences` in Phase 1 — the chat /
provider flow that needed it was retired before this transform.
Reset clears every store and the audit file.

## Foreground service

`HermesService` is the persistent "gateway is running" surface. It is
intentionally local-only — no HTTP calls, no shell, no scraping. The
service exists so the owner always knows when Jarvis Prime is on
watch, and so the platform doesn't kill the process while a worker
run is in flight.

The notification text is in `R.string.orchestrator_notification_*`
and now reads in the Jarvis Prime voice. Start / stop is driven from
the dashboard, not from `MainActivity.onCreate`.

## Build types

| Build type | App id | Notes |
|---|---|---|
| `debug` | `com.aci.hermes.debug` | Side-by-side install for local development. |
| `release` | `com.aci.hermes` | Minified + resource-shrunk. |

CI builds the debug APK on every push / PR via
`.github/workflows/android-build.yml`. The Android SDK and the JDK 21
toolchain are installed by that workflow; local builds need the same.

## Why preserve the `com.aci.hermes` package

Renaming the application id is a one-way migration that invalidates
every existing intent, foreground-service registration, and ADB
script. The product identity is Jarvis Prime; the wire identity is
`com.aci.hermes`. The user-facing label (`R.string.app_name`), every
notification, every screen title, the splash, and the Material theme
all say Jarvis Prime — the package id is the only legacy survivor.
