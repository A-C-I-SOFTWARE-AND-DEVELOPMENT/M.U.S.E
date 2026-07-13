# Living Companion Avatar Architecture

## Mission

Make JARVIS Prime feel present and alive without crossing into unsafe or
deceptive behavior. The avatar can become a small always-visible companion,
react to explicit voice input, optionally respond to attention signals, show
work animations, and visually travel toward a target app. Real device control
must remain separate, permissioned, previewed, and owner-gated.

## Product behavior

The avatar has four layers:

1. **In-app avatar** — already safest; lives inside Jarvis Prime screens.
2. **Mini companion mode** — a smaller avatar inside the Jarvis app surfaces.
3. **System overlay mode** — optional “draw over other apps” companion bubble.
4. **Accessibility action mode** — optional device-control lane for taps,
   gestures, back/home/recents, app navigation.

Only layers 1–2 should be default. Layers 3–4 require explicit education,
settings toggles, and approval gates.

## “Feels alive” loop

```text
Signals → Presence policy → Avatar state → Animation plan → Optional action packet → Owner gate → Execution → Audit log → Memory lesson
```

Signals can include:

- gateway status
- task status
- model thinking/working/speaking state
- microphone active state
- explicit voice wake/hold-to-talk
- opt-in camera attention detection
- target app/action request
- approval state
- blocked state
- emergency stop

## Attention detection

Use opt-in attention detection only. The safe first version should infer
“you are looking at Jarvis” from on-device face landmarks/blendshapes without
storing camera frames, identities, raw images, or emotional state.

Rules:

- Camera is off by default.
- Attention mode is disabled while driving unless manually enabled for a legal,
  hands-free mode.
- No raw frames saved.
- No cloud upload.
- No durable memory saying “Jeremiah felt X” from face inference.
- Show a visible camera/listening indicator whenever active.

## Task animation examples

### “Click on Facebook”

Animation-only path:

1. Jarvis shrinks into mini companion mode.
2. Jarvis runs toward the Facebook icon.
3. Jarvis taps the icon visually.
4. App shows “Ready to open Facebook — tap approve.”

Real-device path:

1. Jarvis creates an action packet.
2. Android shows target app, action, risk, and permission source.
3. Owner approves.
4. Accessibility service performs the app launch/tap.
5. Audit log records the action.

### “It is on the next screen”

1. Jarvis looks to the screen edge.
2. Jarvis turns a page / swipes animation.
3. Jarvis points at the target.
4. Real swipe/tap requires explicit action approval.

## Android implementation notes

- Overlay mode uses `SYSTEM_ALERT_WINDOW` / application overlay only after
  Android’s management screen authorization.
- Device actions use AccessibilityService APIs only after the service is
  enabled by the user and can declare gesture capability.
- `dispatchGesture()` can send a tap gesture, but only after proper service
  capability and approval.
- `performGlobalAction()` can perform global actions such as back/home/recents.
- MediaPipe Face Landmarker can detect face landmarks/facial expressions and
  output blendshape scores for virtual avatars.
- Live2D is a viable avatar-rendering route; Cubism SDK for Native/Web/Unity is
  current, but licensing and asset terms must be reviewed before bundling.

## Implemented in this local ZIP

- `hermes_cli/jarvis_prime/companion_presence.py`
- `tests/test_jarvis_prime_companion_presence.py`

This adds the safe backend state machine and animation-plan contract. It does
not yet add Android overlay permission requests or an AccessibilityService.
That is intentional; those are RC3 surfaces and should land as separate PRs.

## Next Android build lanes

### Lane A — in-app mini companion

- Reuse existing `JarvisLivingAvatar.kt`.
- Add mini/corner/task-runner scale mode.
- Add task animation timeline from `TaskAnimationPlan` shape.
- No new permissions.

### Lane B — overlay companion education

- Add a settings screen explaining draw-over-apps.
- Do not auto-request permission on first launch.
- Add emergency stop visible from overlay.
- Add overlay timeout and quiet hours.

### Lane C — attention sensing

- Add opt-in camera attention mode.
- Use on-device MediaPipe Face Landmarker.
- Store only boolean/confidence events in volatile state.
- Add persistent setting: off by default.

### Lane D — action broker

- Add AccessibilityService only for owner-approved commands.
- Preview every gesture before execution.
- Keep a visible audit record.
- Refuse credentials, payments, posting, deleting, or destructive UI flows.

## Hard no-go lines

- Do not make the avatar secretly watch or listen.
- Do not use overlay to trick permission dialogs.
- Do not let animations imply a real action happened when it did not.
- Do not perform real taps without accessibility enablement and owner approval.
- Do not store inferred emotion as durable memory.
