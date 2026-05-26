# Jarvis Prime App Onboarding

## Purpose

This document describes the first-run onboarding flow for the Jarvis
Prime Android app at `apps/android/`. The flow educates the user about
Jarvis Prime, gateway / Termux / mock mode, the owner approval system,
optional notifications, optional voice capture, the interactive icon,
and emergency stop **before** any sensitive runtime permission is
requested.

## Design rules

The flow follows the JARVIS Prime operating system principles
(`docs/jarvis-prime-operating-system.md`) and the mobile voice workflow
(`docs/mobile-voice-development-workflow.md`). The Android-specific
hard rules are:

- No notification runtime prompt at first launch without education.
- No microphone runtime prompt until the user taps **Start voice setup**.
- No overlay (SYSTEM_ALERT_WINDOW) prompt anywhere in this wave.
- No SMS or Call Log permissions are declared in the manifest.
- Every optional permission is skippable; skipping leaves the app fully
  functional in mock mode.
- Mock mode must always be available, including as the default for a
  first run.

## Screen order

The nine onboarding screens are declared in
`com.jeremiahecherd.jarvisprime.nav.ONBOARDING_ROUTES` and rendered in
this order:

| # | Route | Screen | Purpose |
|---|-------|--------|---------|
| 1 | `onboarding/welcome` | `WelcomeScreen` | Greets the user and frames the rest of the flow. |
| 2 | `onboarding/what` | `WhatJarvisDoesScreen` | Explains Companion / Strategy / Critic / Operator / Builder / Mobile Voice. |
| 3 | `onboarding/owner` | `OwnerControlScreen` | Names the owner-gated actions and the approval model. |
| 4 | `onboarding/mode` | `ModeSelectionScreen` | Lets the user pick **Mock** (default), **Gateway**, or **Termux**. |
| 5 | `onboarding/notification` | `NotificationEducationScreen` | Explains notifications and only then offers the runtime prompt. |
| 6 | `onboarding/voice` | `VoiceEducationScreen` | Explains voice capture and only then offers the microphone prompt. |
| 7 | `onboarding/icon` | `InteractiveIconEducationScreen` | Explains the in-app status icon and why no overlay permission is needed. |
| 8 | `onboarding/emergency-stop` | `EmergencyStopScreen` | Teaches the long-press emergency stop gesture. |
| 9 | `onboarding/finish` | `FinishScreen` | Commits `onboardingComplete = true` and routes to `Routes.HOME`. |

A new install starts at `Routes.WELCOME`. A subsequent launch starts at
`Routes.HOME`. The home surface includes a **Replay onboarding** action
that calls `SettingsRepository.resetForReplay()` and navigates back to
the welcome screen — granted permissions are preserved.

## State

Onboarding state is persisted by
`com.jeremiahecherd.jarvisprime.data.SettingsRepository`, a thin
DataStore-Preferences wrapper that emits a single immutable
`OnboardingState` flow:

```kotlin
data class OnboardingState(
    val onboardingComplete: Boolean = false,
    val mode: JarvisMode = JarvisMode.MOCK,
    val notificationOptIn: Boolean = false,
    val voiceOptIn: Boolean = false,
    val emergencyStopEngaged: Boolean = false,
)
```

Defaults are deliberately conservative — mock mode, no notifications,
no microphone, emergency stop disengaged.

## Architecture

`MainActivity` does nothing during `onCreate` except hand the
`SettingsRepository` to `JarvisPrimeNavGraph`. The nav graph reads the
state flow and chooses `Routes.WELCOME` vs `Routes.HOME` for the start
destination.

`OnboardingViewModel` is the only writer of onboarding state. Each
screen takes its slice of state through arguments and dispatches user
actions to the view-model — there's no hidden side effect.

Education screens own their own permission launchers via
`rememberLauncherForActivityResult`. The launcher is constructed at
composition time (Compose's rule) but is only **invoked** from the
button's `onClick`, so launching the system prompt always traces back
to a user tap.

## Tests

`apps/android/app/src/test/kotlin/com/jeremiahecherd/jarvisprime/`
contains plain JUnit4 tests:

- `ManifestPermissionsTest` — fails if SMS, Call Log, or overlay
  permissions creep into `AndroidManifest.xml`.
- `StartupPermissionPolicyTest` — fails if `MainActivity` or
  `JarvisPrimeApp` references `requestPermissions`,
  `RequestPermission()`, `POST_NOTIFICATIONS`, `RECORD_AUDIO`, or
  `SYSTEM_ALERT_WINDOW`. Confirms each education screen owns its own
  launcher.
- `OnboardingFlowTest` — runs the nine flow invariants against an
  in-memory `SettingsRepository` (new user sees onboarding, skipping
  optional permissions still completes onboarding, opt-in is only
  recorded after explicit action, all three modes are selectable, mock
  remains available, replay preserves granted permissions).
- `NavGraphTest` — locks the screen order at exactly the nine routes
  specified above.

Run with `./gradlew :app:testDebugUnitTest`.
