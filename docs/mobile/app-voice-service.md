# Mobile cockpit — Voice service

> The cockpit must be drivable without looking at it. This document
> specifies the on-device voice pipeline, the hands-free dispatch and
> approval flows, and the TTS confirmation contract.

## 1. Goals

- **One-tap, no-look dispatch.** A long-press on the headset button or
  the on-screen mic FAB starts dictation; releasing it dispatches.
- **Voice confirmation before every destructive action.** TTS reads
  the action out loud ("*approve publishing job 47?*") and waits for
  the user to say *confirm* or *cancel*.
- **Driving mode** turns the whole UI into a single page with a giant
  mic button, large transcript, and only voice-actionable controls.
- **No network round-trips for recognition.** Use the on-device
  `SpeechRecognizer` so we work offline and don't leak the user's
  voice to a third-party recognition service.
- **No always-on listening.** The cockpit never wakes the mic without
  an explicit user action.

## 2. Pieces

```
┌──────────────────────────────────────────────────────────────┐
│                  VoiceCaptureService (foreground)             │
│   - holds SpeechRecognizer                                    │
│   - holds TextToSpeech                                        │
│   - holds MediaSessionCompat for hardware-key capture         │
│   - emits VoicePhase via Flow to VoiceRepository              │
└─────────────▲────────────────────────────────────┬───────────┘
              │                                    │
              │ start/stop/confirm/cancel           │ phase + transcript
              │                                    ▼
┌──────────────────────────┐         ┌────────────────────────────┐
│   VoiceCaptureScreen     │         │       VoiceRepository      │
│   (driving-mode UI)      │ <─────  │  state machine + grammar   │
└──────────────────────────┘         └────────────┬───────────────┘
                                                  │
                                                  ▼
                                       ┌──────────────────────┐
                                       │ JobRepository /      │
                                       │ ApprovalGateVM       │
                                       │ (consumers)          │
                                       └──────────────────────┘
```

## 3. Permissions and manifest

Add to
[`app/src/main/AndroidManifest.xml`](../../apps/android/app/src/main/AndroidManifest.xml):

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE" />
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
<uses-permission android:name="android.permission.BIND_VOICE_INTERACTION"
                 tools:ignore="ProtectedPermissions" />

<service
    android:name=".service.VoiceCaptureService"
    android:exported="false"
    android:foregroundServiceType="microphone" />
```

`RECORD_AUDIO` is requested with the runtime-permission UX the first
time the user enters Voice Capture; refusing it disables driving mode
but leaves the typed Prompt Command Center fully usable.

## 4. State machine

`VoicePhase` is the canonical state every UI consumes:

```kotlin
sealed interface VoicePhase {
    data object Idle : VoicePhase
    data class Listening(val partial: String) : VoicePhase
    data class Heard(val final: String) : VoicePhase
    data class Confirming(val action: VoiceAction, val prompt: String) : VoicePhase
    data class Dispatching(val action: VoiceAction) : VoicePhase
    data class Done(val action: VoiceAction, val outcome: VoiceOutcome) : VoicePhase
    data class Failed(val message: String) : VoicePhase
}
```

Transitions:

```
Idle ──start──▶ Listening
Listening ──onResults──▶ Heard
Heard ──parse──▶ Confirming | Failed("unrecognised command")
Confirming ──"confirm"──▶ Dispatching
Confirming ──"cancel" / timeout 10s──▶ Idle
Dispatching ──onSuccess──▶ Done
Dispatching ──onFailure──▶ Failed
Done / Failed ──ack──▶ Idle
```

## 5. Voice grammar

The grammar is deliberately keyword-driven so we can match on the
exact final transcript from `SpeechRecognizer` without bringing in an
NLU library. Phrases are matched case-insensitively and tolerate one
common filler word at the front (`"please dispatch …"`).

| Phrase | Action | Notes |
|---|---|---|
| `dispatch <freeform prompt>` | dispatch | Everything after *dispatch* is the prompt body. |
| `confirm` / `confirm dispatch` / `confirm publish` / `confirm approve` | confirm pending action | Only valid in `Confirming` phase. |
| `cancel` | cancel pending action | Only valid in `Confirming` phase. |
| `approve job <number>` | open Approval Gate for `<number>` and prepare confirm | Number is parsed as digits. |
| `cancel job <number>` | open Worker Dashboard, queue cancel intent | |
| `status` | TTS speaks queue summary | `"two running, one waiting approval, three offline pending"` |
| `pause stream` / `resume stream` | toggles `EventRepository.streamPaused` | |
| `read errors` | TTS reads the last three error events | |
| `read ledger <number>` | TTS reads the most recent ledger entries for that job | |

A phrase that does not match is reported back as
`Failed("I didn't catch a command — try saying 'dispatch …'")`. The
cockpit does not guess — guessing on a *force-push* approval would
be a disaster.

## 6. Hardware-key capture

`VoiceCaptureService` owns a `MediaSessionCompat` so that pressing
the headset / steering-wheel media-play key starts and stops
dictation without the user looking at the phone:

- **Single press** on a headset button → toggles `Listening`.
- **Long press** → toggles **Driving mode** (the screen if open) and
  keeps listening continuously until tapped off.
- **Bluetooth A2DP connected** → if *Voice → Auto-enter driving mode
  on Bluetooth* is enabled, the service raises a notification offering
  to enter driving mode.

## 7. Confirmation contract

Every destructive action goes through a confirmation in three layers:

1. **Visual confirm sheet** — Material 3 modal bottom sheet with the
   action wording.
2. **Text-to-speech read-out** — the *same* wording is spoken via
   `TextToSpeech` so a driver hears it.
3. **Wait for "confirm" or "cancel"** — the service listens for ≤10 s
   and treats silence as cancel.

The wording template (`VoicePromptBuilder`) is deterministic:

```
"<action>: <subject>. <key facts>. Say confirm to proceed, cancel to abort."
```

Examples:

- `Publishing job 47 on hermes-agent / claude/foo. 3 commits, base main. Say confirm to proceed, cancel to abort.`
- `Approving deploy for job 92 to Vercel production. 2 high-severity risks remaining. Say confirm to proceed, cancel to abort.`
- `Cancelling job 14: telegram-gateway-restart. Say confirm to proceed, cancel to abort.`

The TTS engine speaks at the user's system speech rate. The cockpit
does not race the speech — the confirmation timer starts when TTS
reports `onDone`.

## 8. Offline behaviour

- **Recognition** is on-device, so it works offline.
- **Dispatch** that fails with a network error during voice flow goes
  to the `OfflineQueue`; TTS reads
  *"Saved offline. Will dispatch when the gateway is reachable."* —
  not *"dispatched"*. The cockpit never lies about agent state.
- **Approval / publish / override** are **not** queued offline. They
  require an explicit network round-trip. If the network is down,
  TTS reads *"Cannot approve right now — backend unreachable."* and
  the user can retry from the Decision Ledger Viewer.

## 9. Privacy

- The mic is opened **only** in `Listening` and only while the
  foreground service is alive.
- Transcripts are held in memory and disposed when the screen leaves
  `STARTED`. Nothing is written to disk.
- No analytics call sees the transcript. No SDK other than the
  AOSP `SpeechRecognizer` sees the audio buffer.
- The foreground notification has a *Stop listening* action and the
  notification persists for the entire mic-on lifetime so the user
  is never surprised.

## 10. Failure modes (and what the UI does)

| Failure | UI |
|---|---|
| `RECORD_AUDIO` denied | Driving-mode entry disabled; Settings → Voice has a *Grant microphone* primary action. |
| No on-device recogniser (rare) | Settings → Voice surfaces a *Voice typing* link to the Android voice input setting. |
| TTS engine missing | Visual confirmation sheet is the *only* layer; the cockpit logs a once-per-process warning to Diagnostics. |
| Recognition returned empty | TTS: *"Didn't hear anything."* Phase returns to `Idle`; the mic does not re-open without another tap. |
| Recogniser timed out | Same as empty. |
| Phrase unrecognised | TTS reads the failure reason; the mic re-opens for one more attempt (one retry only — do not loop on misrecognition). |

## 11. Files

| File | Purpose |
|---|---|
| `service/VoiceCaptureService.kt` | foreground service, owns `SpeechRecognizer`, `TextToSpeech`, `MediaSessionCompat` |
| `data/voice/VoiceRecognizer.kt` | thin wrapper turning `SpeechRecognizer` callbacks into `Flow<VoicePhase>` |
| `data/voice/VoicePromptBuilder.kt` | deterministic phrasing of every confirmation |
| `data/voice/ConfirmationPlayer.kt` | TTS wrapper with idle/playing/done state |
| `data/voice/VoiceGrammar.kt` | keyword parser (pure, unit-tested) |
| `data/voice/VoiceRepository.kt` | composes the above and exposes `Flow<VoicePhase>` |
| `ui/screens/voice/VoiceCaptureScreen.kt` | driving-mode composable |
| `ui/screens/voice/VoiceCaptureViewModel.kt` | consumes repository, talks to `JobRepository` |

## 12. Tests

- **Grammar tests** for every supported phrase and every reject case;
  pure unit tests, no Android dependency.
- **State-machine tests** for every transition listed in §4 using a
  fake recogniser and fake TTS.
- **Confirmation-builder tests** that pin the exact strings — a
  regression where the cockpit suddenly reads *"approve job 47"*
  instead of *"approving job 47 …"* would be a UX bug, so we lock
  the wording.
- **Mock-mode demo script** in
  `apps/android/app/src/main/assets/mocks/voice/demo.json` so a tester
  can replay a driving-mode session without speaking aloud.
