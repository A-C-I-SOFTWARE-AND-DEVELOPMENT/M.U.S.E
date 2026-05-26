# Jarvis Prime Interactive Icon

## Mission

Build Jarvis Prime's visible presence as an in-app icon that:

- shows the assistant's current state at a glance
- accepts a handful of common commands as gestures
- never requests the system overlay permission in this wave

The floating-bubble overlay surface ships **later**, behind a dedicated
education flow. This document covers the in-app icon only.

## Files

```
apps/android/app/src/main/java/com/aci/hermes/ui/jarvis/
├── IconState.kt                       # State enum, accessibility labels, priority
├── IconStateMapper.kt                 # IconStateInputs → IconState (pure)
├── JarvisIconColors.kt                # State → IconAppearance recipe + palette
├── JarvisHaptics.kt                   # Thin shim over HapticFeedback
├── JarvisPrimeIcon.kt                 # The @Composable + gesture detector
├── OrchestratorIconStateMapping.kt    # HermesTask snapshot → IconStateInputs
└── ReducedMotion.kt                   # rememberReducedMotion() helper
```

## States

| State                       | Color (core / ring) | Pulse | Notes                                  |
|-----------------------------|--------------------|-------|----------------------------------------|
| `IDLE`                      | core / gold        | low   | default ambient                        |
| `LISTENING`                 | cyan / cyan        | high  | mic open — the "cyan listening glow"   |
| `THINKING`                  | violet / violet    | med   | model reasoning                        |
| `SPEAKING`                  | cyan / cyan        | high  | TTS playback                           |
| `WORKING`                   | slate / slate      | med   | background task in flight              |
| `WAITING_FOR_APPROVAL`      | core / **gold**    | med   | non-destructive approval — gold ring   |
| `SERIOUS_ACTION_PENDING`    | gold / **gold**    | high  | reversible-but-serious — gold ring     |
| `CRITICAL_ACTION_PENDING`   | red / **red**      | high  | destructive — red ring                 |
| `BLOCKED`                   | charcoal / red     | off   | precondition fail                      |
| `WARNING`                   | amber / amber      | med   | non-fatal                              |
| `COMPLETE`                  | green / green      | high  | transient green flash on task complete |
| `OFFLINE`                   | dim gray (50% α)   | off   | gateway unreachable                    |

`SERIOUS_*` and `CRITICAL_*` are deliberately visually distinct — the
former uses gold (filled core), the latter uses red. Their
accessibility labels are also distinct so TalkBack announces them
differently.

## Interactions

| Gesture            | Callback          | Default wiring (current wave)             |
|--------------------|-------------------|-------------------------------------------|
| tap                | `onTap`           | open Chat (placeholder snackbar)          |
| press + hold ≥350ms| `onHold`          | start Voice Capture (placeholder)         |
| press + hold ≥1.5s | `onLongPress`     | open Emergency Stop confirm (placeholder) |
| double tap         | `onDoubleTap`     | announce current status                   |
| swipe up           | `onSwipeUp`       | open Tasks (already shown on Orchestrator)|

Thresholds live in `JarvisIconGestures` (`HOLD_THRESHOLD_MS`,
`LONG_PRESS_THRESHOLD_MS`, `SWIPE_UP_DISTANCE`). All five gestures are
mutually exclusive within a single press — if `onSwipeUp` or `onHold`
fires, `onTap` will not. `onHold` and `onLongPress` can both fire on a
single >1.5s press (hold begins voice capture; long-press escalates to
emergency stop).

Haptic feedback is invoked on every gesture path via `JarvisHaptics`,
which is a thin wrapper around Compose's `LocalHapticFeedback`. The
wrapper exists so the composable doesn't have to spell out
`HapticFeedbackType` guards inline and so tests can swap a fake.

## State mapping

The composable is dumb — it accepts an `IconState` and renders. The
"what state are we in" decision is owned by `IconStateMapper`, a pure
function over `IconStateInputs`:

```kotlin
data class IconStateInputs(
    val gatewayOnline: Boolean = true,
    val listening: Boolean = false,
    val thinking: Boolean = false,
    val speaking: Boolean = false,
    val working: Boolean = false,
    val pendingApproval: Boolean = false,
    val seriousActionPending: Boolean = false,
    val criticalActionPending: Boolean = false,
    val blocked: Boolean = false,
    val warning: Boolean = false,
    val recentCompletion: Boolean = false,
)
```

Priority is encoded in `IconState.priority()`. The rules:

1. If `!gatewayOnline` → `OFFLINE` (overrides everything).
2. Otherwise the highest-priority active signal wins.
3. `IDLE` is the floor.

`OrchestratorIconStateMapping.inputsFor(...)` is the bridge from the
orchestrator domain (`HermesTask`, `TaskStatus`, service-running flag)
to the icon's domain-neutral `IconStateInputs`. The orchestrator
package never imports the icon package directly — the bridge lives in
the icon package, by design.

Current orchestrator → icon mapping:

| Orchestrator signal                          | Icon input flag         |
|----------------------------------------------|-------------------------|
| `serviceRunning == false`                    | `gatewayOnline = false` |
| any task `IN_REVIEW`                         | `pendingApproval`       |
| any task `HANDED_TO_CODEX` or `HANDED_TO_CLAUDE` | `working`           |
| any task `NEEDS_REVISION`                    | `warning`               |
| any task `COMPLETE` updated within 5s        | `recentCompletion`      |

`seriousActionPending`, `criticalActionPending`, `blocked`,
`voiceListening`, `voiceSpeaking`, `thinking` are passthrough
parameters — the wiring for those lives next to the future voice and
approval pipelines.

## Accessibility

- Every `IconState` has a unique, non-blank `accessibilityLabel()`.
- The composable applies the label as both `contentDescription` and
  `stateDescription` so TalkBack reads the right phrase whether the
  user focuses the icon for the first time or after a state change.
- `onClick(label = "Open chat")` is set on the semantics modifier so
  TalkBack can announce the primary action.
- `rememberReducedMotion()` reads
  `Settings.Global.ANIMATOR_DURATION_SCALE` and
  `TRANSITION_ANIMATION_SCALE`. When both are zero the infinite halo
  pulse is suppressed — the icon still renders at its base size and
  remains fully labeled.

## Tests

Pure-JVM unit tests (`app/src/test/java/com/aci/hermes/ui/jarvis/`):

- `IconStateMapperTest` — every priority rule, idle floor, offline
  override.
- `IconStateAccessibilityTest` — every state has a unique non-blank
  label; serious vs critical are distinct in label AND ring color;
  offline is the only `dim` state; offline/blocked have zero pulse.
- `OrchestratorIconStateMappingTest` — `HermesTask` shapes map to the
  right `IconStateInputs` → `IconState`.

Compose UI tests (`app/src/androidTest/java/com/aci/hermes/ui/jarvis/`):

- `JarvisPrimeIconTest` — every state renders with its accessibility
  label; tap / double-tap / long-press / swipe-up callbacks fire;
  reduced-motion still renders and is labeled; serious and critical
  expose distinct content descriptions.

## Verifying locally

```bash
cd apps/android
./gradlew assembleDebug              # builds the debug APK
./gradlew testDebugUnitTest          # runs the pure-JVM tests above
./gradlew connectedDebugAndroidTest  # runs the Compose UI tests on a device
```

## Non-goals (this wave)

- **No overlay / system bubble.** The composable lives inside the app
  process and is reachable only when the user is on a Hermes screen.
  Adding `SYSTEM_ALERT_WINDOW` or invoking `ACTION_MANAGE_OVERLAY_PERMISSION`
  is explicitly out of scope.
- **No Chat / Voice / Emergency Stop screens.** Those land in later
  waves. The icon's callbacks surface placeholder snackbars from the
  Orchestrator screen until the destinations exist.
- **No persistence of icon state.** The mapper is recomputed on every
  state snapshot. State that needs to persist across process death
  (e.g. an in-flight approval) lives in its owning repository, not in
  the icon.
