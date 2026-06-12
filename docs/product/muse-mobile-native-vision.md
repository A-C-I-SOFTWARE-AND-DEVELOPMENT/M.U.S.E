# Hermes — Mobile-Native, Voice-First Vision

> **Status:** Vision + decision record. Companion to
> [`muse-10-10-product-spec.md`](muse-10-10-product-spec.md).
> This document explains the mobile-native bet and the technology
> choices that follow from it.

---

## 1. The bet

The phone is the only computer Jeremiah always has on him. Every
product decision flows from one assumption:

> **If Hermes is not first-class on a phone, it does not exist for
> the moments that matter most — the commute, the school pickup,
> the 2 a.m. idea, the in-flight bug report.**

A web app on a phone is not first-class. A native cockpit built for
one-thumb operation, voice capture, and glanceable status is. The
desktop terminal is a power-user surface, not the product.

## 2. Voice-first interaction model

Voice is the **primary** input. Typing is the fallback.

### 2.1 The three voice modes

| Mode | Trigger | What it does | Default |
|---|---|---|---|
| **Push-to-talk** | Long-press the mic button | Records while held; transcribes on release; user reviews and dispatches. | **On** |
| **Continuous hands-free** | Toggle in Settings → Voice; persistent foreground notification while active | Listens for a wake word (`"Hey Hermes"`); captures the next utterance; transcribes; reviews; dispatches with a confirmation phrase. | **Off** |
| **Driving mode** | Manual toggle, Android Auto, car-Bluetooth heuristic | Voice-only UI; spoken confirmations replace taps; destructive actions disabled. | **Off** |

Every mode shows a visible mic-hot indicator the user cannot miss.
No mode listens silently.

### 2.2 The speech-to-text pipeline

```
mic capture --> on-device STT --> transcript review --> dispatch
                    |
                    +-- (fallback, opt-in) cloud STT --> transcript review --> dispatch
```

Rules:

1. **On-device first.** The default STT engine runs on the phone.
   Candidates (decision pending in §5): Whisper.cpp (small/base
   quantized), Vosk, Android's built-in on-device speech recognizer
   (Android 13+).
2. **Cloud STT is opt-in per session.** Cloud STT (e.g. Google,
   Deepgram, OpenAI Whisper API) is faster and more accurate but
   sends audio off-device. It is never the default and a banner
   ("audio sent to <provider>") is visible while it is in use.
3. **No silent fallback.** If on-device STT fails, the user sees a
   "STT failed — type instead" prompt; we never silently swap to
   cloud STT without consent.
4. **Transcripts are user-editable before dispatch.** The cockpit
   shows the transcript, the user can tap to edit, and the prompt
   is only sent on the second confirmation.

### 2.3 Confirmation phrases (driving mode)

Driving mode replaces taps with spoken phrases. The grammar is
narrow on purpose — it is a finite-state command set, not a
free-form conversation.

| Phrase | Action |
|---|---|
| *"Hermes, dispatch."* | Confirms the pending dispatch. |
| *"Hermes, cancel."* | Cancels the pending capture. |
| *"Hermes, approve."* | Approves the next pending approval gate. |
| *"Hermes, reject."* | Rejects the next pending approval gate. |
| *"Hermes, status."* | Reads the current job summary aloud. |
| *"Hermes, end driving mode."* | Exits driving mode (UI re-enables taps after a 3-s safety pause). |

Anything outside this grammar is rejected with *"I only take a small
set of commands while you're driving. Say 'Hermes, end driving mode'
when you can use the screen."*

---

## 3. Android-native vs. Flutter — the decision

We have a working **Android-native** (Kotlin + Jetpack Compose) app
at `apps/android/`. The question is whether the 10/10 cockpit
should:

- **A.** Continue evolving on Android-native (Kotlin + Compose).
- **B.** Rewrite the cockpit in **Flutter** to enable an iOS cockpit
  and a desktop cockpit from one codebase.

### 3.1 Decision (for the 10/10 phase)

> **Stay on Android-native (Kotlin + Compose) through the 10/10
> milestone. Re-evaluate Flutter for the post-10/10 phase once the
> Android cockpit is 10/10 and an iOS cockpit becomes the next
> deliverable.**

### 3.2 Why

| Factor | Android-native | Flutter | Decision driver |
|---|---|---|---|
| Existing investment | `apps/android/` is shipping; the cockpit screens are partly built; the team has Kotlin/Compose muscle memory. | Greenfield rewrite; six-week minimum to reach parity. | **Native wins** for time-to-10/10. |
| Voice + STT integration | Direct access to Android `SpeechRecognizer`, foreground services, MediaProjection, Android Auto, and on-device Whisper bindings. | All of the above is reachable through method channels, but each one is a custom plugin. | **Native wins** for voice-first product. |
| Driving mode + Auto | Android Auto is a first-party Android surface. The native app can register as an Auto app; Flutter cannot today. | Workarounds exist but ship-blockers remain. | **Native wins** for safety surface. |
| Background reliability | Foreground services + WorkManager + Doze handling are all native concerns. Flutter must re-implement each one. | Solvable, but each is its own bug surface. | **Native wins** for reliability. |
| Cross-platform reach | Android only. iOS / desktop need separate effort. | One codebase across Android, iOS, macOS, Windows, Linux, web. | **Flutter wins** for reach. |
| Long-term cost of two codebases | Native iOS adds Swift expertise + two codebases to maintain. | One Dart codebase across all platforms. | **Flutter wins** for long-term cost. |

The 10/10 bar is **mobile-native, voice-first** — not "available on
every platform". The path that fastest gets the cockpit to 10/10 on
the device that matters most (the user's Android phone) is native.
We accept that this defers iOS by one phase.

### 3.3 Conditions that would flip the decision

We re-open the question if any of the following becomes true:

- iOS becomes a hard requirement before the 10/10 ship date.
- Flutter gains first-class Android Auto support (currently
  unofficial / community plugins only).
- The Compose stack hits a wall we cannot ship through (none today).
- A Hermes-on-iPad/macOS use case becomes the dominant cockpit
  pathway.

When any of those flips, we move the cockpit to Flutter behind a
phased migration plan — not a big-bang rewrite. The gateway API
(`/v1/cockpit/...`) is intentionally framework-agnostic so the
cockpit can swap underneath without backend changes.

### 3.4 What the native cockpit must add to reach 10/10

The existing `apps/android/` is alpha. Capabilities below are not
yet built and must land before the cockpit is 10/10:

- Continuous hands-free listening with wake-word + visible mic-hot
  indicator.
- Driving mode surface with narrow voice grammar.
- Android Auto integration (or, at minimum, an "in-car safe" surface
  detectable by Bluetooth heuristics).
- On-device STT integration (Whisper.cpp or platform STT) as the
  default; cloud STT behind a per-session opt-in.
- Voice readback of validation reports and gate decisions.
- Plain-English "why" expansions on every job card.
- Glanceable lock-screen / always-on widget for "next pending
  approval" and "current job status".

These are tracked in [`muse-definition-of-done.md`](muse-definition-of-done.md).

---

## 4. UX principles for a phone cockpit

1. **Glanceable.** Any screen should answer "what is Hermes doing?"
   in one second of reading. No required scroll for the primary
   answer.
2. **One-thumb.** Every primary action is reachable with the right
   thumb on a 6-inch screen held vertically. No two-handed gestures
   for primary flows.
3. **Calm by default.** Notifications fire on **state changes the
   user must act on** (approval pending, validation failed,
   publishing complete) — never on routine progress. Routine
   progress is reflected in the dashboard, not the notification
   tray.
4. **Voice readback for anything destructive.** If the user is
   approving a destructive action by voice, Hermes reads the action
   back in plain English and requires *"Hermes, confirm"* before
   acting.
5. **Never lose a prompt.** A captured prompt is persisted locally
   before dispatch; if dispatch fails, the prompt stays in the
   cockpit's outbox and is replayed on reconnect.
6. **Lock-screen widget.** A single 2x2 widget shows the next
   pending approval, the current job's phase, and a mic icon for
   "new prompt." Tapping the widget jumps to the right screen.
7. **No raw model output.** Stack traces, JSON dumps, and provider
   error blobs are folded behind a "show details" button. The
   default view is plain English. See
   [`muse-plain-english-principles.md`](muse-plain-english-principles.md).

---

## 5. Open technical decisions

The decisions below are still open. They are tracked here so the
spec stays honest about what is decided and what is not.

| Decision | Options | Trigger to decide |
|---|---|---|
| On-device STT engine | Whisper.cpp (small.en, quantized) · Android `SpeechRecognizer` (on-device, 13+) · Vosk | First spike that lands voice capture in the cockpit. |
| Wake-word engine | Porcupine (Picovoice) · Sherpa-onnx · custom Whisper VAD loop | After STT pick. Porcupine is best in class but commercial; the others are FOSS. |
| Driving-mode trigger heuristic | Android Auto handoff · car-Bluetooth name pattern · explicit toggle only | Decide once we have telemetry on false-positives. |
| Lock-screen widget API | Glance (Compose) · classic AppWidget · both | Glance is the Compose-native path; classic is more portable. |
| Cockpit ⇄ backend transport | Existing HTTP + SSE · gRPC-Web · WebSocket | Stick with HTTP + SSE through 10/10; revisit only if SSE proves unreliable on cellular. |

When any of these flips, update this file and the corresponding
section of [`muse-10-10-product-spec.md`](muse-10-10-product-spec.md).

---

## 6. Cross-references

- [`muse-10-10-product-spec.md`](muse-10-10-product-spec.md) — overall product spec.
- [`muse-user-journeys.md`](muse-user-journeys.md) — journey #1 (driving) and #7 (network recovery) are the heaviest tests of the mobile-native bet.
- [`muse-definition-of-done.md`](muse-definition-of-done.md) — per-capability checklists, including cockpit DoD.
- [`../android/muse-apk-cockpit.md`](../android/muse-apk-cockpit.md) — current cockpit screen spec.
- [`../android/muse-apk-api-contract.md`](../android/muse-apk-api-contract.md) — gateway API for the cockpit.
- [`../android/muse-apk-ui-wireframes.md`](../android/muse-apk-ui-wireframes.md) — current wireframes.
