# MUSE Presence Mode (mobile-native, hands-free)

Presence Mode turns the Android cockpit into a hands-free command center.
MUSE lives over the launcher and other apps (the existing floating
avatar), the conversation is hands-free by default, and the avatar
animates from the **real** voice/job/action state — not a demo.

> This page is the mobile presence layer. For the capture surfaces,
> STT/TTS choices, and driving-mode safety, see
> [voice-first-user-guide.md](voice-first-user-guide.md) and
> [driving-mode-safety.md](driving-mode-safety.md). Presence Mode does
> **not** change what the backend can do — a spoken turn and a typed
> turn produce the same Hermes job, ledger, and gates.

---

## How it starts a conversation — the fallback chain

Presence Mode never press-and-holds to talk. A turn starts from the first
**available** trigger in this strict order:

```
camera attention (opt-in)  →  wake word ("Hey MUSE")  →  mic button
```

- **Camera attention** — opt-in only, behind the `CAMERA` permission, with
  a visible on-screen privacy indicator whenever the camera is active. If
  the permission is denied or the hardware is absent, Presence Mode falls
  back automatically.
- **Wake word** — an on-device, keyless "Hey MUSE" spotter
  (`SpeechRecognizerWakeWordEngine`). Audio never leaves the device; it
  only arms when Presence Mode is enabled and the RECORD_AUDIO permission
  is granted. It is pluggable — a dedicated low-power engine (Porcupine /
  Vosk) can be dropped in behind the same `WakeWordEngine` interface.
- **Mic button** — the always-honest floor. Tap to talk when neither
  attention nor a wake word is available. Tap-to-talk is the *fallback*,
  never the primary interaction.

The arbitration lives in one tested state machine,
`PresenceModeController`. Listening is **opt-in**: nothing arms until you
enable Presence Mode, and an emergency stop disarms every trigger.

## Gestures on the avatar

| Gesture | Action |
|---|---|
| **Single tap** | Talk (mic fallback) — start a turn |
| **Double tap** *or* status pill *or* overflow → Status detail | Open the status sheet |
| **Long press** | Emergency stop (confirm dialog) |

The status sheet is no longer the single-tap action — tapping the avatar
talks to MUSE.

## What the avatar shows (real state)

The avatar and the status pill reflect the genuine phase published by the
voice loop and the agent stream:

`Idle → Listening → Thinking → Working → Speaking`, plus
`ApprovalNeeded`, `Blocked`, and `EmergencyStop`. When listening, the live
transcript is surfaced so you can see what MUSE heard. The floating
overlay mirrors the same state.

## Knowing when the mic / camera is on

You are never left guessing:

- The hands-free loop runs as a **foreground service** with a persistent
  "MUSE is listening" notification and the OS microphone indicator.
- Camera attention (when enabled) shows an in-app privacy indicator plus
  the OS camera indicator.
- The status pill reads **Listening** while the mic is open.

## Approval by voice — never silent

High-risk, owner-gated actions (deploy, merge, publish, spend, credential
change, …) can be approved hands-free, but only through a mandatory
ceremony enforced by `VoiceApprovalCoordinator`:

1. MUSE **reads the exact action back** aloud.
2. You must reply with an **explicit authorization phrase** — e.g.
   *"yes, with authorization"*, *"confirm"*, *"approve"*.
3. A bare *"yes"* / *"ok"* is **insufficient** and will not approve. A
   negative reply, a timeout, or "cancel" abandons the approval.

Only after the ceremony is satisfied does the app submit the canonical
owner phrase to the gateway, which **re-verifies it server-side** (the
gateway returns `403` otherwise). Voice never holds or auto-fills the
owner phrase, and it can never approve an action it didn't read back.

Driving mode adds a second gate: an approved publish/merge still raises a
`DrivingSafetyVeto` on the backend and is queued for a non-driving
confirmation — see [driving-mode-safety.md](driving-mode-safety.md).

## Emergency stop

A long press anywhere on the avatar raises the emergency-stop confirm.
Confirming tears down the hands-free voice loop (mic + foreground service
stop), disarms every Presence trigger, and latches `EmergencyStop` until
you release it.

## Backend reuse (no duplication)

The mobile read-back / classification / driving veto are **not**
reimplemented on the phone. The cockpit gateway exposes the canonical
`hermes_cli.voice_intake` pipeline:

- `POST /v1/cockpit/voice/intake` — transcript → read-back + draft
- `POST /v1/cockpit/voice/{id}/decide` — explicit phrase → terminal state

The Android client (`HermesCockpitClient.voiceIntakeCreate/Decide`) calls
these so the safety logic has a single source of truth.

## Privacy posture

- Wake-word audio is processed entirely on the device and never uploaded.
- Camera attention (opt-in) analyzes frames on-device for presence only;
  no frames are stored or uploaded.
- The on-device STT path sends only the transcript to the gateway; raw
  audio is not persisted by the app.

## Current status / follow-ups

- The camera-based attention detector (CameraX + ML Kit) is the documented
  next step; until it ships, Presence Mode degrades safely to the
  wake-word → mic-button fallback (already live and tested).
- The wake word uses the system recognizer; a dedicated low-power engine
  is a drop-in behind `WakeWordEngine`.
