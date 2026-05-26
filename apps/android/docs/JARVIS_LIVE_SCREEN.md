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

The screen projects eight discrete states through
`JarvisLiveStateMapper`. The mapper takes a multi-flag
`JarvisLiveUiState` and collapses it using the priority order below.
Higher rows beat lower rows:

| Priority | State            | Pill text         | Voice line                            |
| -------- | ---------------- | ----------------- | ------------------------------------- |
| 1        | EmergencyStop    | Emergency stop    | Emergency stop active.                |
| 2        | Blocked          | Blocked           | Action needed before I can continue.  |
| 3        | ApprovalNeeded   | Approval needed   | Waiting for your approval.            |
| 4        | Speaking         | Speaking          | Speaking.                             |
| 5        | Working          | Working           | Working on the task.                  |
| 6        | Thinking         | Thinking          | Thinking through it.                  |
| 7        | Listening        | Listening         | Listening.                            |
| 8        | Idle             | Idle              | Standing by.                          |

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
- Long-press on the avatar opens an emergency-stop confirmation
  dialog. Tap opens the status detail sheet.
- Text uses Material 3 typography tokens so the screen scales with the
  system text size preference.

## Permission audit

The Jarvis Live PR introduces **zero** new permissions. The manifest
still declares exactly:

- `android.permission.POST_NOTIFICATIONS`
- `android.permission.FOREGROUND_SERVICE`
- `android.permission.FOREGROUND_SERVICE_DATA_SYNC`

A pure-JVM test
(`ManifestPermissionAuditTest`) parses
`AndroidManifest.xml` and asserts the approved set, plus an explicit
forbid-list (RECORD_AUDIO, READ_MEDIA_IMAGES, READ_EXTERNAL_STORAGE,
WRITE_EXTERNAL_STORAGE, CAMERA, SYSTEM_ALERT_WINDOW). The test fails
if anyone adds one of those without updating the audit.

The voice button in the bottom command bar renders disabled with the
content description "Voice input coming soon" until a dedicated voice
PR ships and toggles `JarvisLiveUiState.voiceAvailable`.

## Tests

All tests are pure-JVM JUnit 4 — no Robolectric, no Compose UI test
deps, no emulator. They live at
`app/src/test/java/com/aci/hermes/ui/screens/live/` and
`app/src/test/java/com/aci/hermes/permissions/`:

- `JarvisLiveStateMapperTest` — every state projects, priority order
  is enforced, reduced motion clamps the motion flags, CTAs match the
  expected state, content descriptions are present.
- `ManifestPermissionAuditTest` — forbids the dangerous permission
  list and snapshots the approved set.

Run with:

```
cd apps/android
./gradlew testDebugUnitTest
```

## Follow-up plan

This PR ships the screen foundation. The follow-up PRs will:

1. **Real avatar system** — promote the placeholder
   `JarvisLivingAvatar` into a polished living-avatar engine with
   orb, pixel preset, and a Lottie/Vector option.
2. **Privacy-safe avatar picker** — replace the stub
   `AvatarPickerScreen` with the Android Photo Picker (no
   `READ_MEDIA_IMAGES`), pixelation, and app-private storage. The
   permission audit must still pass.
3. **Voice infrastructure** — wire `voiceAvailable` and the voice
   button to a STT/TTS layer behind an opt-in toggle. `RECORD_AUDIO`
   is requested only when the user enables voice.
4. **Compose UI tests** — add `compose-ui-test-junit4` +
   `compose-ui-test-manifest` and assert against the live semantic
   tree (bottom bar visible, edit-avatar entry visible, CTAs appear
   for the right states).
5. **Optional**: promote Jarvis Live to start destination after the
   above ship and user testing confirms the new home is right.
