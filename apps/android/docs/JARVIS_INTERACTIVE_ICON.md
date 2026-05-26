# Jarvis Prime Interactive Icon

## Mission

Build Jarvis Prime's visible presence as an in-app icon that:

- shows the assistant's current state at a glance
- accepts a handful of common commands as gestures
- never requests the system overlay permission in this wave

The floating-bubble overlay surface ships **later**, behind a dedicated
education flow. This document covers the in-app icon only.

## Where it lives

This lane introduces a single, isolated composable plus a minimal
event contract. The state layer it consumes (`IconState`,
`IconStateMapper`, `JarvisIconColors`, `OrchestratorIconStateMapping`)
already exists at `ui/jarvis/` and is reused unchanged.

```
apps/android/app/src/main/java/com/aci/hermes/ui/
├── jarvis/                                # state layer (reused, unmodified)
│   ├── IconState.kt
│   ├── IconStateMapper.kt
│   ├── JarvisIconColors.kt
│   └── OrchestratorIconStateMapping.kt
└── components/
    ├── JarvisPrimeIcon.kt                 # static brand glyph (untouched)
    └── icon/                              # this lane
        ├── JarvisInteractiveIcon.kt       # entry-point composable
        ├── JarvisIconEvent.kt             # sealed event contract
        └── IconAccessibility.kt           # state → label + action hint
```

The interactive composable is deliberately named `JarvisInteractiveIcon`
(not `JarvisPrimeIcon`) so it does not collide with the existing static
brand glyph at `ui/components/JarvisPrimeIcon.kt`.

## Entry point

```kotlin
@Composable
fun JarvisInteractiveIcon(
    state: IconState,
    onEvent: JarvisIconEventHandler,
    modifier: Modifier = Modifier,
    size: Dp = 72.dp,
    reducedMotion: Boolean = false,
)
```

The composable is dumb — it accepts a state and renders. State
resolution lives in `IconStateMapper`, the orchestrator bridge lives
in `OrchestratorIconStateMapping`.

## Event contract

```kotlin
sealed class JarvisIconEvent {
    object Tap : JarvisIconEvent()
    object LongPress : JarvisIconEvent()
    object DoubleTap : JarvisIconEvent()
    object SwipeUp : JarvisIconEvent()
    object SwipeDown : JarvisIconEvent()
}

fun interface JarvisIconEventHandler {
    fun onEvent(event: JarvisIconEvent)
}
```

| Gesture     | Event       | Suggested wiring (caller decides)       |
|-------------|-------------|-----------------------------------------|
| tap         | `Tap`       | open chat                               |
| long-press  | `LongPress` | emergency-stop confirm                  |
| double-tap  | `DoubleTap` | announce status / quick toggle          |
| swipe up    | `SwipeUp`   | open Tasks                              |
| swipe down  | `SwipeDown` | mute briefly / collapse to status pill  |

Vertical-drag threshold is `size / 3`. A drag that does not pass the
threshold is dropped without emitting any event.

## States

The composable handles every `IconState` via the appearance recipe,
but the mission's six required states are the explicit acceptance
surface:

| Mission state    | `IconState`               | Ring / Core         | Pulse |
|------------------|---------------------------|---------------------|-------|
| idle             | `IDLE`                    | gold-deep / core    | low   |
| listening        | `LISTENING`               | **cyan** / cyan     | high  |
| working          | `WORKING`                 | slate / slate       | med   |
| needs_approval   | `WAITING_FOR_APPROVAL`    | **gold** / core     | med   |
| blocked          | `BLOCKED`                 | red / charcoal      | off   |
| emergency_stop   | `CRITICAL_ACTION_PENDING` | **red** / red       | max   |

`SERIOUS_ACTION_PENDING`, `WARNING`, `COMPLETE`, `THINKING`,
`SPEAKING`, and `OFFLINE` also render correctly — they're inherited
from the full enum.

## State mapping

`IconStateMapper` collapses a snapshot of signals into one state:

```kotlin
val state = IconStateMapper.map(
    IconStateInputs(
        gatewayOnline = serviceRunning,
        listening = voiceListening,
        criticalActionPending = emergencyStopArmed,
        pendingApproval = approvalsInQueue,
        blocked = policyBlocked,
        // … etc.
    ),
)
```

`OrchestratorIconStateMapping.inputsFor(...)` builds those inputs from
the orchestrator's task list. The mapper is pure and side-effect-free,
so the same logic will drive the in-app icon today and the future
overlay surface unchanged.

## Accessibility

- Every `IconState` has a unique, non-blank `accessibilityLabel()`.
- The composable applies the label as both `contentDescription` and
  `stateDescription` so TalkBack announces it on focus and again on
  state change.
- A state-specific action hint (`semanticActionHint()`) is attached
  to the `onClick` semantic so TalkBack tells the user what `Tap`
  will do *right now* (review approval / stop listening / open Jarvis).
- `OFFLINE` is dimmed (`alpha = 0.6`); `BLOCKED` and `OFFLINE` have
  pulse amplitude `0f` by design.

## Reduced motion

Pass `reducedMotion = true` to suppress the infinite halo pulse. The
icon still renders at its base size and remains fully labeled — only
the breathing animation is dropped. Callers should propagate the
system-level reduced-motion preference.

## Non-goals (this wave)

- **No overlay / system bubble.** No `SYSTEM_ALERT_WINDOW`, no
  `ACTION_MANAGE_OVERLAY_PERMISSION`. The composable lives entirely
  inside the app process.
- **No permission additions.** A guard test asserts the manifest
  permission set is unchanged.
- **No nav, AppContainer, or Screen edits.** This lane is the icon
  itself plus its docs and tests — wiring it into the home/orchestrator
  screens is the next lane.
- **No persistence.** The state is recomputed from the latest
  `IconStateInputs`. Anything durable lives in its owning repository.

## Tests

Pure-JVM unit tests under
`apps/android/app/src/test/java/com/aci/hermes/ui/components/icon/`:

- `IconAccessibilityLabelTest` — every required state has a non-blank
  label; emergency-stop label is distinct from approval + blocked;
  action hint differs across listening / approval / idle.
- `EmergencyStopAppearanceTest` — `CRITICAL_ACTION_PENDING` uses the
  red ring + core, pulse amplitude `1.0f`, not dim, and is visually
  distinct from `BLOCKED` and `WAITING_FOR_APPROVAL`.
- `NeedsApprovalMappingTest` — `IconStateInputs(pendingApproval = true)`
  resolves to `WAITING_FOR_APPROVAL`; critical wins when both flags
  are set.
- `JarvisIconEventModelTest` — every `JarvisIconEvent` subclass is a
  singleton; an exhaustive `when` covers all five branches.
- `ManifestPermissionsUnchangedTest` — the Android manifest still
  declares exactly `{POST_NOTIFICATIONS, FOREGROUND_SERVICE,
  FOREGROUND_SERVICE_DATA_SYNC}` and does **not** declare
  `SYSTEM_ALERT_WINDOW`.

## Verifying locally

```bash
cd apps/android
./gradlew testDebugUnitTest    # pure-JVM unit tests
./gradlew assembleDebug        # builds the debug APK
```

## Integration snippet (for the follow-up lane)

The next lane wires `JarvisInteractiveIcon` into the cockpit. Sketch:

```kotlin
val inputs = OrchestratorIconStateMapping.inputsFor(
    serviceRunning = uiState.serviceRunning,
    tasks = uiState.tasks,
    voiceListening = uiState.voiceListening,
    pendingApproval = uiState.pendingApprovals.isNotEmpty(),
    criticalActionPending = uiState.emergencyStopArmed,
)
val state = IconStateMapper.map(inputs)

JarvisInteractiveIcon(
    state = state,
    onEvent = { event ->
        when (event) {
            JarvisIconEvent.Tap -> openChat()
            JarvisIconEvent.LongPress -> confirmEmergencyStop()
            JarvisIconEvent.DoubleTap -> announceStatus()
            JarvisIconEvent.SwipeUp -> openTasks()
            JarvisIconEvent.SwipeDown -> collapseToStatusPill()
        }
    },
    reducedMotion = uiState.reducedMotion,
)
```

Wiring lives in the caller — this lane intentionally does not touch
`HermesNavGraph`, `Screen`, `AppContainer`, or `AndroidManifest.xml`.
