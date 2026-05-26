# Jarvis Live Feedback

## Mission

The user must never wonder if the app is frozen. Jarvis Prime is
always visibly alive:

- the avatar always has subtle motion (unless reduced-motion is on),
- a status pill always names the current state,
- a one-line status sentence always explains what Jarvis is doing,
- long-running tasks expose a phase + step label,
- approvals, blocks, and emergency-stop are unmistakable,
- no fake completion claims and no silent failures.

## Pipeline

```
domain signals             pure mapping             screen
─────────────────          ──────────────           ──────
HermesTask list      ─┐
serviceRunning       ─┤   IconStateInputs   →
voice / approvals    ─┤   IconStateMapper   →     IconState
                      │
worker phase         ─┤   JarvisLiveInputs  →
chat-stream state    ─┤   JarvisLiveStatus
emergency stop       ─┤   Projector (pure) →     JarvisLiveStatus
gateway online       ─┤
reduced-motion       ─┘                            │
                                                   ▼
                                          JarvisLivingAvatar
                                          + status pill
                                          + status line
                                          + detail / progress
                                          + approval / emergency
```

`IconStateMapper` resolves which icon-level state wins.
`JarvisLiveStatusProjector` turns that, plus the live-screen-only
signals (worker phase, chat stream, emergency stop, approval queue,
reduced-motion), into the bundle the screen renders.

Both mappers are pure functions — `apps/android/app/src/test/...` runs
them under stock JVM JUnit, no Android dependencies.

## States and language

| IconState                  | Worker phase | Pill                | Status line                                | Avatar activity         |
|----------------------------|--------------|---------------------|--------------------------------------------|--------------------------|
| any (emergency-stop flag)  | —            | `EMERGENCY STOP`    | `Emergency stop active.`                   | CrimsonLockedRing        |
| any (gateway offline)      | —            | `Offline`           | `Gateway offline.`                         | Static                   |
| CRITICAL_ACTION_PENDING    | —            | `Critical approval` | `Critical action — needs your approval.`   | CrimsonLockedRing        |
| SERIOUS_ACTION_PENDING     | —            | `Approval needed`   | `Serious action — needs your approval.`    | GoldRing                 |
| BLOCKED                    | —            | `Blocked`           | `Blocked — action needed.`                 | Static                   |
| WAITING_FOR_APPROVAL       | —            | `Approval needed`   | `Waiting for your approval.`               | GoldRing                 |
| SPEAKING (or chat=SPEAKING)| —            | `Speaking`          | `Talking it through.`                      | MouthPulse               |
| LISTENING                  | —            | `Listening`         | `Listening.`                               | Subtle                   |
| THINKING (or chat=THINKING)| —            | `Thinking`          | `Thinking through it.`                     | AnimatedDots             |
| WORKING                    | PLANNING     | `Planning`          | `Building the plan.`                       | TaskOrbit                |
| WORKING                    | CODING       | `Coding`            | `Editing the files.`                       | TaskOrbit                |
| WORKING                    | TESTING      | `Testing`           | `Running checks.`                          | CheckPulse               |
| WORKING                    | REVIEWING    | `Reviewing`         | `Reviewing the result.`                    | ScanRing                 |
| WORKING                    | NONE         | `Working`           | `Working on the task.`                     | TaskOrbit                |
| COMPLETE                   | —            | `Done`              | `Done. Ready when you are.`                | CheckPulse               |
| WARNING                    | —            | `Heads up`          | `Heads up — non-fatal issue.`              | Subtle                   |
| IDLE (floor)               | —            | `Idle`              | `Ready when you are.`                      | Subtle                   |

## Avatar activity catalog

| Activity              | Visual                                      | Reduced-motion fallback |
|-----------------------|---------------------------------------------|--------------------------|
| `Static`              | base icon, no overlay                       | unchanged                |
| `Subtle`              | base icon's own breath                      | breath suppressed        |
| `AnimatedDots`        | three dots arcing under the icon, staggered | dots collapse to Static  |
| `ScanRing`            | rotating arc segment around the ring        | collapse to Static       |
| `TaskOrbit`           | bead orbiting the ring                      | collapse to Static       |
| `CheckPulse`          | outer check-style pulse ring                | collapse to Static       |
| `MouthPulse`          | horizontal bar under core that breathes     | collapse to Static       |
| `GoldRing`            | solid gold attention ring                   | **preserved**, no breath |
| `CrimsonLockedRing`   | solid red attention ring                    | **preserved**, no breath |

Attention rings (`GoldRing`, `CrimsonLockedRing`) survive reduced-motion
because they are the legibility signal — the user still needs to see
that approval / emergency stop is required. The pill, status line,
detail line, and progress label always render in either mode.

## Adding a new signal

1. Add the producer flow to wherever it naturally lives (orchestrator
   repo, voice pipeline, worker process, chat gateway).
2. Add the corresponding field to either `IconStateInputs` (if it's a
   universal signal) or `JarvisLiveInputs` (if it's only relevant on
   the live screen).
3. Wire it into `JarvisLiveViewModel` — either as a flow collected in
   `init`, or as a public setter the producer calls.
4. Add a `JarvisLiveStatusProjector.project` branch with the matching
   pill text, status line, and avatar activity.
5. Add a unit test that asserts:
   - the new branch fires when its signal is set,
   - it produces a non-blank pill + status line,
   - it loses to emergency stop and gateway offline,
   - it behaves correctly under `reducedMotion = true`.

## Test contract

`apps/android/app/src/test/java/com/aci/hermes/ui/jarvis/JarvisLiveStatusProjectorTest.kt` pins:

- every `IconState` produces a non-blank pill + status line
- emergency stop outranks every other state
- gateway offline outranks every non-emergency state
- `BLOCKED` outranks `WORKING`
- `approvalQueueCount > 0` outranks `IDLE`
- `reducedMotion = true` forces `shouldPulse = false` for every state
- `reducedMotion = true` preserves attention rings (gold / crimson)
- a long-running working task with a phase never looks idle
- no combination of (state × phase × stream × motion × gateway) returns
  blank UI

## Honesty rules

- `COMPLETE` only fires when `OrchestratorIconStateMapping` already says
  so (5-second recent-completion flash window). The projector never
  fabricates completion.
- When `gatewayOnline = false`, the projector ALWAYS surfaces
  `Gateway offline.` — never `Idle`.
- When `emergencyStopActive = true`, the projector surfaces
  `EMERGENCY STOP` over every other claim — including completion.

## Out of scope (follow-up)

- avatar picker (Photo Picker, local pixelator, app-private storage,
  Settings row, Robolectric bitmap tests)
- embedding the avatar block into HomeScreen and OrchestratorScreen
- real voice-capture wiring (no `RECORD_AUDIO`)
- real chat-stream producer (the screen accepts the state; the
  producer is wired by the chat-screen branch)
- bitmap upload of any kind
