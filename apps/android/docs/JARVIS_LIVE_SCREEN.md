# Jarvis Live Command Screen

The Jarvis Live command screen is Hermes' "presence" surface — a
full-screen, dark, command-center view of what Jarvis is doing right
now. Unlike the Orchestrator dashboard (which is task-centric), this
screen is presence-centric: a single avatar, a single status line, and
a single command bar.

## Where it lives

- **Route:** `jarvis_live`
  (`com.aci.hermes.ui.navigation.Screen.JarvisLive`).
- **Entry point:** A "Open Jarvis Live" card on the Orchestrator
  dashboard, directly under the service status card. The Orchestrator
  remains the app's start destination — Jarvis Live is additive and
  reversible.
- **Back path:** the top-bar menu icon pops back to the previous
  destination (typically Orchestrator).

## States

The screen projects discrete states through `JarvisLiveStateMapper`.
The mapper takes a multi-flag `JarvisLiveUiState` and collapses it
using the priority order below. Higher rows beat lower rows, so a
safety-critical state can never be hidden by a cosmetic work signal:

| Priority | State          | Pill text       | Voice line                            |
| -------- | -------------- | --------------- | ------------------------------------- |
| 1        | EmergencyStop  | Emergency stop  | Emergency stop active.                |
| 2        | Disconnected   | Disconnected    | I can't reach the runtime right now.  |
| 3        | Blocked        | Blocked         | Action needed before I can continue.  |
| 4        | ApprovalNeeded | Approval needed | Waiting for your approval.            |
| 5        | Warning        | Needs attention | Something needs your attention.       |
| 6        | Speaking       | Speaking        | Speaking.                             |
| 7        | Listening      | Listening       | Listening.                            |
| 8        | Reviewing      | Reviewing       | Reviewing the work.                   |
| 9        | Coding         | Coding          | Writing the code.                     |
| 10       | Researching    | Researching     | Researching the problem.              |
| 11       | Working        | Working         | Working on the task.                  |
| 12       | Thinking       | Thinking        | Thinking through it.                  |
| 13       | Idle           | Idle            | Standing by.                          |

### Where the state comes from (real backend signals)

The avatar is an **operational surface, not decoration** — every state
is derived from a live signal by the pure `JarvisLivePresenceMapper`
(JVM-testable, no Android deps), then resolved by `JarvisLiveStateMapper`:

| Signal (source)                                              | Drives                  |
| ------------------------------------------------------------ | ----------------------- |
| Persisted `emergencyStopEngaged` (`SettingsRepository`)      | EmergencyStop           |
| Cockpit `health()` probe fails / unpaired                    | Disconnected            |
| Job `BLOCKED` (`CockpitJobsRepository`)                      | Blocked                 |
| Pending approvals / `queue.waiting_approval` / job `WAITING_FOR_APPROVAL` | ApprovalNeeded |
| Job `FAILED` or `validation_summary.fail > 0`                | Warning                 |
| Voice loop phase (`VoiceLoopService.phaseFlow`)              | Listening / Thinking / Speaking |
| Active task `WorkerPhase` (`HermesTaskRepository`)           | Researching / Coding / Reviewing |
| Active job, unknown phase                                    | Working (fallback)      |

The runtime queue + approvals are polled (~5 s); jobs, tasks, the
emergency flag, and the voice phase are observed as flows and combined.

> **Researching / Coding / Reviewing are *derived UI state*, not backend
> truth.** They are inferred from the active task's worker lane
> (PLANNER/NAVIGATOR → Researching, EDITOR/EXECUTOR → Coding,
> REVIEWER/JARVIS_FINAL_SYNTHESIS → Reviewing). Unknown lanes degrade to
> the generic Working state. `JarvisLivePresenceMapperTest` pins this
> mapping so a future `WorkerPhase` change fails loudly instead of
> silently mis-animating the avatar.

Each state drives:

- **avatar palette** — gold for thinking/working/approval, cyan for
  listening/speaking, crimson for blocked/emergency
- **status pill** color and label
- **voice/status line** below the avatar
- **contextual CTA** — approve (gold), review block (crimson), release
  emergency stop (crimson)
- **motion enabled flag** — disabled under emergency stop *and* under
  system reduced motion
- **particles enabled flag** — disabled additionally under blocked

## Motion and accessibility

- **Reduced motion** is detected from
  `Settings.Global.ANIMATOR_DURATION_SCALE == 0f`. When on, the
  avatar pulse and ring sweep stop and the particle layer is
  short-circuited at the top of its composable. The avatar still
  renders the correct color for the current state.
- **Content descriptions** are returned by the projector as resource
  ids so every state's avatar carries a state-specific TalkBack
  description ("Jarvis is thinking", etc.).
- The status pill exposes a parameterized content description
  ("Current Jarvis state: …") so TalkBack reads the state without
  relying on the visual pill text alone.
- **Gesture model (Presence Mode):** single-tap the avatar to talk
  (tap-to-talk), double-tap for the status detail sheet, long-press for
  the emergency-stop confirmation. The status pill is also tappable for
  the sheet, and "Change companion" (sprite cycle) moved to the overflow
  menu.
- Text uses Material 3 typography tokens so the screen scales with the
  system text size preference.
- The new Warning and Disconnected states never rely on color/animation
  alone — each has a distinct pill label, voice/status line, and
  TalkBack content description.

## Actions (operational, never hidden)

The avatar surface keeps every critical control reachable:

- **Emergency stop** — long-press → confirmation → the **real** global
  stop: `OrchestratorServiceController.emergencyStop()` halts the
  service and `SettingsRepository.setEmergencyStopEngaged(true)` is
  persisted, so the EmergencyStop state shows on every surface (this
  screen, the floating overlay, Control) until released.
- **Open approvals** — the ApprovalNeeded CTA routes to the gated
  Approvals screen (the owner phrase is enforced there). The avatar
  **never** approves anything itself.
- **Swipe to current job** — a left-swipe opens the active job's
  TaskDetail (or the Tasks list when none is active). The Blocked and
  Warning CTAs open the same job.
- **Voice / Presence Mode** — toggle hands-free Presence Mode from the
  overflow menu. When on, JARVIS arms a keyless on-device wake word
  ("Jarvis") via `KeywordSpeechWakeWordEngine`; a single tap on the
  avatar (or the command-bar mic) is the tap-to-talk fallback that opens
  the mic immediately (`VoiceLoopService.talkNow`). The degradation
  chain is camera attention (gated — see below) → wake word + voice
  activity → mic / tap-to-talk; the active trigger is chosen by
  `PresenceModePolicy.trigger`. A status line under the avatar shows
  `Hands-free · listening/thinking/speaking` so the state is conveyed by
  text, not animation alone. The floating overlay mirrors the same voice
  phase even when the cockpit UI is backgrounded
  (`PresenceModeController`). The wake word + tap-to-talk use only the
  already-declared `RECORD_AUDIO` + `SYSTEM_ALERT_WINDOW`.
- **Camera attention (opt-in, default OFF)** — an additional overflow
  toggle. When enabled AND Presence Mode is on AND the `CAMERA`
  permission is granted (`AttentionPolicy.active`, a three-way AND), the
  live screen runs on-device face-**presence** detection
  (`CameraXFaceAttentionDetector`: CameraX front camera + bundled ML Kit
  face detection) and arms listening on a glance
  (`AttentionPolicy.shouldArmOnTransition`, rising edge only). Privacy
  guarantees: a persistent visible "Camera on" indicator renders off the
  **same** `cameraActive` flag that gates the detector (they cannot
  diverge); the detector is bound to the screen lifecycle and released on
  exit; frames are analysed in memory and closed immediately — **no
  frame, image, identity, or expression is stored or transmitted**, and
  ML Kit runs fully on-device. It reports only `PRESENT`/`ABSENT`.

## Permission audit

The state-wiring and Presence-Mode work add **no** new permissions.
Opt-in camera attention adds exactly one — `android.permission.CAMERA`,
default OFF, used only for on-device face-presence as described above.
The three audits (`ManifestPermissionAuditTest`,
`manifest/ManifestPermissionsTest`, `data/avatar/ManifestPermissionsTest`)
were amended in lockstep to move `CAMERA` into the approved/allow set
(with the opt-in rationale recorded in each), while everything else —
contacts, SMS, call log, location, broad media/storage — stays
forbidden, so further scope creep still fails CI.

A pure-JVM test
(`ManifestPermissionAuditTest`) parses
`AndroidManifest.xml` and asserts the approved set, plus an explicit
forbid-list (RECORD_AUDIO, READ_MEDIA_IMAGES, READ_EXTERNAL_STORAGE,
WRITE_EXTERNAL_STORAGE, CAMERA, SYSTEM_ALERT_WINDOW). The test fails
if anyone adds one of those without updating the audit.

The voice button in the bottom command bar is enabled wherever the
device exposes a `SpeechRecognizer`; it starts/stops the hands-free
`VoiceLoopService` behind the `RECORD_AUDIO` consent. No new permission
is introduced by the real-state wiring.

## Tests

All tests are pure-JVM JUnit 4 — no Robolectric, no Compose UI test
deps, no emulator. They live at
`app/src/test/java/com/aci/hermes/ui/screens/live/` and
`app/src/test/java/com/aci/hermes/permissions/`:

- `JarvisLiveStateMapperTest` — every state projects, priority order
  is enforced (incl. the new Disconnected/Warning/work-phase rows),
  reduced motion clamps the motion flags, CTAs match the expected
  state, content descriptions are present.
- `JarvisLivePresenceMapperTest` — locks the backend-signal → flag
  derivation: emergency/disconnected/approval/blocked/warning priority
  and the `WorkerPhase` → Researching/Coding/Reviewing mapping (the
  guard rail against silent drift).
- `AvatarAnimationTest` — the new states reuse stable `AvatarPose`
  ordinals (Rive contract held) and Disconnected freezes motion.
- `PresenceModeTest` — the Presence Mode trigger degradation chain
  (camera → wake word → mic), the voice-phase → presence-state
  projection, and the `WakeWordMatcher` whole-word matching rules.
- `AttentionPolicyTest` — camera attention runs only behind the
  three-way opt-in/presence/permission AND, and arms on the rising edge
  into PRESENT only.
- `ManifestPermissionAuditTest` (+ the two `ManifestPermissionsTest`s) —
  snapshot the approved permission set (now including the opt-in
  `CAMERA`) and keep the dangerous permissions forbidden.

Run with:

```
cd apps/android
./gradlew testDebugUnitTest
```

## Follow-up plan

The avatar reflects real JARVIS state (Phase 1) and hands-free Presence
Mode is wired (Phase 2). Remaining follow-ups:

1. **Dedicated wake-word spotter** — the current
   `KeywordSpeechWakeWordEngine` is a keyless, best-effort
   `SpeechRecognizer` loop. A purpose-built spotter (e.g. Picovoice
   Porcupine) is a drop-in via `VoiceLoopService.Wiring.wakeWordFactory`;
   it needs an access key, which must not live in source.
2. **Background camera attention** — camera attention currently runs
   only while the live screen is visible (lifecycle-bound). Extending it
   to the floating overlay would need a camera foreground-service type
   and extra review; intentionally out of scope here.

3. **Compose UI tests** — add `compose-ui-test-junit4` and assert the
   live semantic tree (CTAs appear for the right states, swipe opens
   the current job).

**Shipped (opt-in, default OFF):** camera attention — on-device
CameraX/ML Kit face-presence detection to arm Presence Mode, behind the
`CAMERA` permission. The three permission audits were amended in lockstep
to allow `CAMERA` (rationale recorded inline); it is owner-authorized,
default-off, shows a visible indicator while active, and processes frames
on-device only (none stored or transmitted).
