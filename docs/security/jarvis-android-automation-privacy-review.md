# JARVIS Prime Android — Automation Surface Security & Privacy Review

- **Repo:** `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`
- **Date:** 2026-06-04
- **Scope:** the Android device-automation surface — accessibility gestures,
  floating overlay, camera/mic presence, device-control broker, consent,
  emergency stop, and what is persisted/transmitted.
- **Method:** read-only static review (no behavioral change beyond the two
  fail-safe fixes noted in §4).

## Executive summary

The automation surface is **well-architected for safety**. Device control
flows through a single pure-function chokepoint (`DeviceActionBroker`) with a
safety-first precedence, defaults **fully dormant** on a fresh install,
requires both an OS grant *and* explicit per-capability owner consent, holds
sensitive actions for confirmation, and writes an append-only **local-only**
ledger. The emergency stop is genuine: it flips a volatile flag the synchronous
gesture guard reads, drops in-flight gestures, and tears down the overlay and
voice loop. Avatar animation is separated from real device control. Screen
content scraped via accessibility is used transiently for target resolution and
is **never persisted or transmitted**. Camera/mic are opt-in, on-device,
presence/transcript-only (no frame/audio storage), behind foreground services
with visible notifications.

**No spyware-like behavior was found** — no silent capture, no background
camera/mic without a foreground service + notification, no exfiltration of
screen content or transcripts.

**Verdict: conditionally safe to ship as a personal-tool fork** (the stated
context). Not yet ready for general/Play distribution until the deferred
findings below (esp. #4, #5) and the `QUERY_ALL_PACKAGES` scope (#2) are
addressed.

## Findings

| # | Area | Severity | Evidence | Status |
|---|------|----------|----------|--------|
| 1 | Comment claimed the manifest *forbids* CAMERA, but it is declared and used by the Live attention detector | Medium | `voice/PresenceModeController.kt:34` vs `AndroidManifest.xml` CAMERA + `vision/CameraXFaceAttentionDetector.kt` | **Fixed** (comment corrected) |
| 6 | Gesture guard was fail-**open**: a null guard allowed gestures (`gestureGuard?.invoke() == false`) | Low | `service/JarvisAccessibilityService.kt:53` | **Fixed** (now `!= true` → null/false both block) |
| 2 | `QUERY_ALL_PACKAGES` treated as always-granted | Medium | `AndroidManifest.xml`; `DeviceControlCapability.kt:47`, `DeviceControlController.kt:110` | Deferred — narrow to `<queries>` before any Play distribution; document as a deliberate fork choice |
| 3 | Broad accessibility scope (reads all window content) | Medium | `res/xml/jarvis_accessibility.xml:14-18`; reads at `JarvisAccessibilityService.kt:82-92,139-152` | Deferred — acceptable (content never stored/sent); recommend an explicit "no node text leaves device" test + narrowing event types |
| 4 | `confirmSensitiveActions` is owner-disableable → SENSITIVE actions can auto-run with no per-action confirm; sensitivity is binary (no irreversible/external tier) | Medium | `DeviceConsentState.kt:13-22`, `DeviceActionBroker.kt:60-63`, `DeviceActionPacket.kt:6-12` | Deferred — add a non-disableable confirmation floor + a third "irreversible/external" tier (design change) |
| 5 | Device-control halt is decoupled from the global emergency-stop state machine; `releaseEmergencyStop()` re-enables gestures without the audited resume-approval flow | Medium | `HermesNavGraph.kt:109-114`, `DeviceControlController.kt:146-149` vs `EmergencyStopController.kt:144-218` | Deferred — wire device-control halt/release to `EmergencyStopController` so one stop blocks everything and resume is approval-gated everywhere (architectural change) |
| 7 | `dispatchBlocking` ignores the async cancellation result (ledger may record EXECUTED for a system-cancelled gesture) | Low | `JarvisAccessibilityService.kt:125-137` | Deferred — minor correctness; await the deferred or drop it |

## Privacy posture (verified)

- **No persistence of screen content or transcripts.** The device-action
  ledger entry is deliberately minimal (label, sensitivity, outcome, reason)
  with an explicit "no screen contents, no transcripts, no secrets" contract
  (`DeviceActionLogEntry.kt`). Scraped node text is in-memory only, for target
  resolution (`DeviceControlController.kt:164-171`).
- **Ledger is local-only**, atomic, capped at 500 entries
  (`DeviceActionLedger.kt`). No network egress.
- **Camera**: opt-in, on-device, presence-only (PRESENT/ABSENT), no frame
  storage, bound to the foreground Live screen, default off
  (`vision/CameraXFaceAttentionDetector.kt`, `AttentionDetector.kt`,
  `PresenceModeController.kt`).
- **Microphone**: foreground service + visible "listening" notification,
  on-device STT, only the final transcript used, no raw audio stored
  (`service/VoiceLoopService.kt`, `di/AppContainer.kt:302-313`).
- **Redactor gap (low, by design)**: `PrivacyRedactor`/`SecretRedactor` cover
  the social-intelligence and audit surfaces, not the device-action ledger —
  acceptable today because labels are synthesized previews ("Open Facebook"),
  never raw screen text. Invariant to preserve: if a label ever incorporates
  resolved on-screen text, route it through the redactors first.

## Owner-gate / emergency-stop posture (verified)

- Default-off consent; broker blocks unless a capability is **both** OS-granted
  and owner-consented; accessibility is the hard gate for all gestures.
- Confirmation holds SENSITIVE actions for explicit owner approve/dismiss;
  approval re-runs the full broker check (no stale-approval bypass).
- Emergency stop blocks execution first in broker precedence, drops mid-flight
  gestures via the synchronous guard, and is reachable globally and from the
  Device Control screen. (Caveat #5: the *release* path is not approval-gated.)

## Changes made in this review (fail-safe only)

1. **#1** — corrected the `PresenceModeController` comment to state the truth:
   CAMERA is declared and used only by the opt-in, default-off, on-device Live
   attention detector (a stale "manifest forbids camera" comment is an audit
   hazard).
2. **#6** — hardened the accessibility gesture guard to **fail closed**: a
   gesture now runs only on an explicit `true` from the guard; a null guard or
   emergency-stop `false` both block.

Both are in the safe direction (worst case: over-block a gesture). No
behavioral change to consent, the broker, the ledger, or the camera/mic paths.

## Recommended before general/Play distribution

- #5: unify device-control halt with the audited global emergency-stop +
  approval-gated resume.
- #4: non-disableable confirmation floor + an irreversible/external sensitivity
  tier.
- #2: narrow `QUERY_ALL_PACKAGES` to `<queries>`.
- #3: add a test asserting no accessibility node text reaches the ledger/network.
- #7: await/await-drop the gesture cancellation deferred.
