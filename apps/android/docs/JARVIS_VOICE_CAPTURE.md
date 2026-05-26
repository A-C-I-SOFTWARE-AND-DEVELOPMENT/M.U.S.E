# JARVIS Prime — Android voice capture (Phase 1)

Phase 1 adds a **tap-to-talk** voice surface to the Android cockpit. It
captures a single utterance, lets the user review the transcript, and
routes the result to **chat** or to a **draft task** — never to a
direct action. Vague or serious commands are explicitly held back as
approval-required drafts.

> Phase 1 deliberately does *not* include: always-on listening,
> wake-word detection, background capture, raw-audio upload, or
> automatic execution of captured commands. Future phases may add
> push-to-talk on a hardware button or driving-mode hands-free, but
> those land behind explicit settings, not as defaults.

## Invariants

These are enforced by the code in `app/src/main/java/com/aci/hermes/voice/`
and the tests under `app/src/test/java/com/aci/hermes/voice/`:

1. **No always-on listening.** The microphone is never opened until the
   user taps the **Voice** button, reads the education panel, taps
   **Allow microphone**, and grants the OS permission.
2. **No wake word.** There is no background process listening for a
   hot phrase. The only entry point is the on-screen button.
3. **Permission is requested only after education.** `MainActivity`
   does not request `RECORD_AUDIO`. The only place the permission is
   asked is `VoiceCaptureSheet`, and only after the user has explicitly
   acknowledged what the mic is for.
4. **Cancel works at every step.** Education, requesting-permission,
   permission-denied, listening, captured, manual-entry, and error all
   expose a Cancel that releases the recognizer and returns to Idle.
5. **Captured speech becomes editable text.** STT output is never
   executed directly. The user can edit the transcript on the
   **Review** panel before choosing **Send to chat** or **Create task**.
6. **Vague or serious commands are held back.** The
   [`VoiceIntentClassifier`](../app/src/main/java/com/aci/hermes/voice/VoiceIntentClassifier.kt)
   flags transcripts that contain verbs like *delete, deploy, publish,
   spend, push, merge* (or vague scopes like "everything", "whatever
   you think"). Flagged transcripts are routed to a draft task with an
   `[Approval needed]` title prefix and an in-description warning;
   nothing is handed off automatically.

## State machine

```
        Idle
         │  open()
         ▼
     Education ──cancel()──► Idle
         │  acknowledgeEducation()
         ▼
  RequestingPermission ──denied──► PermissionDenied
         │ granted
         ▼
     Listening ──stop()──► Captured
         │  cancel()  │  Final{empty}      Final{cancel phrase}
         ▼            └► message + Captured(empty)  └► Idle
        Idle

  Captured ──sendToChat()──► Idle  (and routes via VoiceCaptureRouter)
  Captured ──createTask()──► Idle  (DRAFT task; [Approval needed] if flagged)
```

If `SpeechRecognizer.isRecognitionAvailable(context)` returns false,
the sheet drops into **ManualEntry** instead of **RequestingPermission**
so the rest of the pipeline still works on devices without an
on-device recognizer.

## Files

| File | Purpose |
|---|---|
| `voice/VoiceCaptureState.kt` | Step enum, `VoiceCommandCategory`, `VoiceCaptureUiState` |
| `voice/VoiceIntentClassifier.kt` | Rule-based safe / approval / cancel classifier |
| `voice/VoiceRecognizer.kt` | Interface + `VoiceRecognizerEvent` sealed class |
| `voice/AndroidSpeechRecognizer.kt` | Wraps `android.speech.SpeechRecognizer` |
| `voice/ManualVoiceRecognizer.kt` | Fallback when STT is unavailable |
| `voice/VoiceCaptureRouter.kt` | Routing interface + `DefaultVoiceCaptureRouter`, `VoicePendingDraft` |
| `voice/VoiceCaptureViewModel.kt` | State machine, drives the recognizer + router |
| `voice/ui/VoiceCaptureButton.kt` | Entry button on the orchestrator dashboard |
| `voice/ui/VoiceCaptureSheet.kt` | Bottom-sheet UI for the whole flow |
| `voice/ui/Waveform.kt` | Decorative animated waveform while listening |

## Manifest

`AndroidManifest.xml` declares the runtime permission and the
`<queries>` block required on Android 11+ for
`SpeechRecognizer.isRecognitionAvailable` to see installed recognition
services:

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />

<queries>
    <intent>
        <action android:name="android.speech.RecognitionService" />
    </intent>
</queries>
```

Declaring the permission does **not** request it. It's only requested
inside the bottom sheet, by an `ActivityResultContracts.RequestPermission`
launcher that fires after the user taps **Allow microphone** on the
education panel.

## Routing

`DefaultVoiceCaptureRouter` is the only routing implementation wired
into `AppContainer`:

- **Send to chat** publishes the transcript to a shared
  `VoicePendingDraft`. The orchestrator dashboard observes that draft
  and navigates to a new task; `TaskDetailViewModel.init` consumes the
  draft and prefills the title and description. The user reviews and
  taps **Save** themselves — there is no auto-save.
- **Create task** writes a `HermesTask` directly to
  `HermesTaskRepository`. The task is always created with
  `status = DRAFT` and `targetTool = MANUAL`. If the classifier flagged
  the transcript, the title is prefixed with `[Approval needed]` and
  the description carries a warning paragraph that explains why.

Neither path calls `HandoffLauncher`, opens an external app, or moves
the task into `HANDED_TO_*`. Voice capture only creates artefacts the
user can audit and choose to act on later.

## Tests

`app/src/test/java/com/aci/hermes/voice/` — pure-JVM JUnit 4 tests
using `kotlinx-coroutines-test` and the local `FakeVoiceRecognizer` /
`RecordingRouter` test doubles.

| Test | Invariant covered |
|---|---|
| `VoiceCaptureViewModelTest.mic is not opened on construction` | No always-on listening; mic only opens on `Listening` step. |
| `VoiceCaptureViewModelTest.open shows education first not permission request` | Education appears before the OS permission dialog. |
| `VoiceCaptureViewModelTest.acknowledge education advances to requesting permission` | The VM does not start the recognizer itself; the sheet asks the OS. |
| `VoiceCaptureViewModelTest.permission denied transitions to denied state without listening` | Denial is recoverable; mic is never opened. |
| `VoiceCaptureViewModelTest.permission granted transitions to listening and starts recognizer` | Listening state renders only after explicit grant. |
| `VoiceCaptureViewModelTest.cancel from listening aborts recognizer and resets state` | Cancel works mid-listen. |
| `VoiceCaptureViewModelTest.stop forwards to recognizer only when listening` | Stop is a no-op outside of `Listening`. |
| `VoiceCaptureViewModelTest.partial transcript is shown while listening` | Live transcript renders. |
| `VoiceCaptureViewModelTest.final transcript moves to Captured and classifies as safe` | Safe text routes to `SAFE_TEXT`. |
| `VoiceCaptureViewModelTest.final transcript with serious verb marks approval-required` | Serious verb classifies APPROVAL_REQUIRED and **does not auto-execute** (`router.calls.isEmpty()`). |
| `VoiceCaptureViewModelTest.send to chat routes through router` | Captured text flows to chat. |
| `VoiceCaptureViewModelTest.create task routes through router and preserves classification` | Captured text flows to task and carries the approval flag. |
| `VoiceCaptureViewModelTest.editing transcript reclassifies` | User edits re-run the safety check. |
| `VoiceCaptureViewModelTest.manual entry available when recognizer is not` | Manual transcript fallback exists when STT is missing. |
| `VoiceCaptureViewModelTest.cancel phrase in final transcript dismisses sheet` | "Never mind" cancels rather than acting. |
| `VoiceCaptureViewModelTest.recognizer error surfaces error step` | Recognizer errors are surfaced, not silently swallowed. |
| `VoiceIntentClassifierTest.*` | Classifier rules — safe text, serious verbs, vague scopes, cancel phrases. |
| `VoicePendingDraftTest.*` | The chat hand-off publish / consume contract. |

Run them with:

```bash
cd apps/android
./gradlew :app:testDebugUnitTest
```

And build the debug APK with:

```bash
cd apps/android
./gradlew assembleDebug
```

## Future phases

- Phase 2: hardware push-to-talk (e.g. mounted device button), opt-in.
- Phase 3: driving-capture mode mirroring the gateway-side safety
  policy in `docs/voice/driving-mode-safety.md` — strict mode that
  vetoes publish-class actions outright.
- Phase 4: streaming partials directly to the orchestrator gateway so
  long-form dictation can feed the same job intake pipeline the CLI
  uses.

None of those phases relax the Phase 1 invariants — they extend the
entry surface while keeping the same classifier and approval gate.
