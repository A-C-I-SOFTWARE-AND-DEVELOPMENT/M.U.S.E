# Jarvis Prime App Permission Flow

## Purpose

This document captures the Android permission policy for the Jarvis
Prime app at `apps/android/`. The policy is enforced both in code
(`MainActivity`, `AndroidManifest.xml`, the education screens) and in
unit tests under `app/src/test/kotlin/`.

## Hard rules

1. **No notification permission request on first launch without
   education.** `MainActivity.onCreate` never references
   `POST_NOTIFICATIONS` or calls a permission launcher. The runtime
   prompt is launched only from
   `NotificationEducationScreen` after the user taps **Enable
   notifications**.
2. **No microphone permission request on startup.** The runtime prompt
   is launched only from `VoiceEducationScreen` after the user taps
   **Start voice setup**. Mock mode never triggers the prompt.
3. **No overlay permission in this wave.** `SYSTEM_ALERT_WINDOW` is
   not declared in the manifest. The "interactive Jarvis icon" is an
   in-app surface, not a system overlay.
4. **No SMS or Call Log permissions.** `READ_SMS`, `RECEIVE_SMS`,
   `SEND_SMS`, `RECEIVE_MMS`, `RECEIVE_WAP_PUSH`, `READ_CALL_LOG`,
   `WRITE_CALL_LOG`, `PROCESS_OUTGOING_CALLS`, and `READ_PHONE_STATE`
   are not declared in the manifest.
5. **Optional permissions are skippable.** Each education screen has a
   **Not now** action that records no opt-in and advances to the next
   step. Skipped permissions can be granted later from settings via
   **Replay onboarding** or a future settings screen.
6. **Mock mode never asks for any runtime permission.** Choosing mock
   mode is sufficient to use the app end-to-end.

## Declared manifest permissions

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
```

- `INTERNET` is a normal permission used only by gateway mode. It
  carries no runtime prompt.
- `POST_NOTIFICATIONS` and `RECORD_AUDIO` are declared because Android
  requires the manifest entry before a runtime prompt can be shown.
  Declaring is not requesting — the runtime prompt is gated on a tap
  inside the matching education screen.

## Per-permission flow

### Notifications

1. User reaches `NotificationEducationScreen` (step 5 of 9).
2. Screen explains: *"We will not ask Android for this permission until
   you tap Enable. The app works fully without it."*
3. User taps **Enable notifications** or **Not now**.
4. On **Enable**: if the device is API 33+,
   `rememberLauncherForActivityResult(RequestPermission())` launches
   the system prompt. On grant, `OnboardingViewModel.recordNotificationOptIn()`
   sets `notificationOptIn = true` in the repository. On older
   devices, the opt-in flag is set without a prompt because the
   runtime permission did not exist.
5. On **Not now**: navigation advances; `notificationOptIn` stays
   `false`.

### Voice / Microphone

1. User reaches `VoiceEducationScreen` (step 6 of 9).
2. Screen explains that mock mode never records audio and that the
   prompt only fires on the user's tap.
3. User taps **Start voice setup** or **Not now**.
4. On **Start voice setup**: launcher launches the
   `RECORD_AUDIO` system prompt. On grant, the view-model sets
   `voiceOptIn = true`.
5. On **Not now**: navigation advances; `voiceOptIn` stays `false`.

### Interactive Jarvis icon

No overlay permission is requested. The icon is rendered inside the
app's own activity surface, so `SYSTEM_ALERT_WINDOW` is not required
and is explicitly not declared.

### Emergency stop

Emergency stop is implemented entirely with in-app state
(`OnboardingState.emergencyStopEngaged`) and the long-press gesture is
attached to the in-app icon. It requires zero Android permissions.

## Fallback behaviour

If notification permission is denied (or skipped) the app continues to
work — owner-approval prompts surface inside the app instead of as
push notifications, and gateway / Termux / mock modes function
normally. The home screen reads `OnboardingState.notificationOptIn`
and `voiceOptIn` to show **On / Off** state without ever calling
`requestPermissions`.

## Verification

| Invariant | Test |
|-----------|------|
| Manifest contains no SMS / Call Log / overlay permissions | `ManifestPermissionsTest` |
| `MainActivity` never references permission APIs or sensitive constants | `StartupPermissionPolicyTest.mainActivityNeverRequestsPermissionsAtStartup` |
| Notification prompt lives only in education screen | `StartupPermissionPolicyTest.notificationEducationScreenOwnsTheNotificationPrompt` |
| Microphone prompt lives only in education screen | `StartupPermissionPolicyTest.voiceEducationScreenOwnsTheMicrophonePrompt` |
| New install opens onboarding by default | `OnboardingFlowTest.newUserSeesOnboardingByDefault` |
| Skipping optional permissions still completes onboarding | `OnboardingFlowTest.skippingOptionalPermissionsKeepsOnboardingComplete` |
| Mock / Gateway / Termux all selectable | `OnboardingFlowTest.{mockModeIsAvailableAndStaysSelectable,gatewayModeIsSelectable,termuxModeIsSelectable}` |

Run with `cd apps/android && ./gradlew :app:testDebugUnitTest`.
