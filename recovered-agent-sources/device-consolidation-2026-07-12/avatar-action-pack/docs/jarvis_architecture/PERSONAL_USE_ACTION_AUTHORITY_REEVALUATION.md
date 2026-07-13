# Personal-Use Action Authority Re-evaluation

## Decision

Jeremiah has granted standing authorization for this private local build to move beyond preview-only avatar choreography and into a real personal-device action broker.

The plan is now:

1. Keep Hermes/JARVIS as the reasoning and memory backend.
2. Keep the Android app as the living companion surface.
3. Add an owner-authorized action broker that can perform real cross-app navigation and gestures after Android capability grants are enabled.
4. Treat Android system permissions as technical capability checks, not as a lack of owner consent.

## Meaning of authorization

Authorization is now project-level and persistent for the local personal build:

- JARVIS may animate task work.
- JARVIS may use the mini companion overlay.
- JARVIS may navigate across apps.
- JARVIS may use AccessibilityService gesture dispatch for taps/swipes.
- JARVIS may use on-device camera attention signals for presence.
- JARVIS may query known target packages such as Facebook.

## What still remains gated

These are no longer moral/permission doubts. They are engineering safeguards:

- Android overlay grant must exist before drawing over other apps.
- AccessibilityService must be enabled before gesture execution.
- MediaProjection requires per-session user consent by Android design.
- Emergency stop always wins.
- For accidental-damage prevention, the default build pauses before final send/post/payment/security/destructive gestures. This can be changed in code, but the safe default remains.

## Why this is the right architecture

A standing authorization profile makes the system feel alive instead of constantly asking for approval. Runtime capability checks keep it reliable: if Android denies overlay, screen capture, or accessibility, JARVIS should visibly say what capability is missing instead of pretending it can act.

## Implementation lanes

### Lane A — In-app living avatar

No special Android permissions. The avatar lives inside the Hermes app, reacts to tasks, and displays memory/thinking/working states.

### Lane B — System overlay mini companion

Uses SYSTEM_ALERT_WINDOW and a foreground service. The mini avatar can stay on top of other apps and run to the edge/target coordinates.

### Lane C — Accessibility action broker

Uses AccessibilityService with window-content retrieval and gesture capability. It locates actionable nodes first, then falls back to dispatchGesture taps when node actions fail.

### Lane D — Attention sensing

Uses on-device face/attention signals only. No raw frame storage. No cloud upload. No durable emotion inference. Attention state should be short-lived: looking, away, talking, unknown.

### Lane E — Screen-aware choreography

Optional MediaProjection for visual grounding when Accessibility node descriptions are insufficient. Android requires user consent for each media-projection session.
