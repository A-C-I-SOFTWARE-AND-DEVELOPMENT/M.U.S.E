# Rive / 3D avatar — animation input contract

`JarvisRiveAvatar` and `JarvisFilamentAvatar` are driven by data, not by
imperative animation calls. Both consume the renderer-neutral
`AvatarInputs` produced by `AvatarAnimation.inputsFor(...)`. Finished art
that honors this contract drops in with **zero Kotlin changes**.

## Rive (`res/raw/jarvis.riv`)

The artboard must expose a state machine named **`JarvisStateMachine`**
with three inputs:

| Input    | Type    | Range  | Meaning                                  |
| -------- | ------- | ------ | ---------------------------------------- |
| `pose`   | number  | 0–16   | `AvatarPose.ordinal` (table below)       |
| `energy` | number  | 0–100  | intensity — pulse/brightness/animation speed |
| `motion` | boolean | —      | when false, hold still (reduced motion / sleep) |

Blend between poses rather than hard-cutting — continuous locomotion
(idle→run→push→settle) is what makes the body read as alive.

## 3D (`.glb`)

The glTF model must contain one animation clip **named after the
lowercase `AvatarPose`** (`idle`, `run`, `push`, `page_turn`, …).
`JarvisFilamentAvatar` looks the clip up by name and crossfades.

## `AvatarPose` ordinals (the source of truth)

| Ordinal | Pose | When |
|---|---|---|
| 0 | `IDLE` | resting fidget |
| 1 | `LISTEN` | mic open / capturing |
| 2 | `THINK` | agent reasoning |
| 3 | `WORK` | agent executing |
| 4 | `SPEAK` | TTS / replying |
| 5 | `APPROVE` | waiting on owner approval |
| 6 | `BLOCKED` | blocked, needs input |
| 7 | `EMERGENCY` | emergency stop (held still) |
| 8 | `RUN` | travelling to a target |
| 9 | `PUSH` | pressing an app/button |
| 10 | `PAGE_TURN` | flipping the home screen |
| 11 | `SCROLL` | dragging content |
| 12 | `POINT` | gesturing without acting |
| 13 | `WANDER` | ambient strolling |
| 14 | `SLEEP` | asleep (dimmed, no motion) |
| 15 | `WAKE` | waking up |
| 16 | `RECOMMEND` | leaning in to suggest |

The ordering is pinned by `AvatarPose` in
`ui/screens/live/AvatarAnimation.kt`; if you reorder the enum, update
the art's `pose` mapping to match (or the avatar will play the wrong
clip).
