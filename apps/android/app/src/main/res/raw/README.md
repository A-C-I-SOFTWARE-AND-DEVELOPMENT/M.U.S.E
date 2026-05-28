# `res/raw` — avatar animation assets

## `jarvis.riv` (PLACEHOLDER — must be replaced with real art)

`JarvisRiveAvatar` loads `R.raw.jarvis` and drives it by setting three
state-machine inputs. The checked-in `jarvis.riv` is a **non-binary
placeholder** so the project compiles and `R.raw.jarvis` resolves; the
Rive runtime can't render it. Drop a real `.riv` here (same filename)
and the avatar comes alive with **zero Kotlin changes**.

### Required artboard contract

The `.riv` must expose a state machine named **`JarvisStateMachine`**
with these inputs (see `docs/avatar/rive-state-contract.md`):

| Input    | Type    | Driven by                       |
| -------- | ------- | ------------------------------- |
| `pose`   | number  | `AvatarPose.ordinal` (0–16)     |
| `energy` | number  | `0–100` (intensity)             |
| `motion` | boolean | suppress looping when `false`   |

`pose` ordinals follow `AvatarPose` order: IDLE, LISTEN, THINK, WORK,
SPEAK, APPROVE, BLOCKED, EMERGENCY, RUN, PUSH, PAGE_TURN, SCROLL,
POINT, WANDER, SLEEP, WAKE, RECOMMEND.

The artboard should blend between poses (not hard-cut) so locomotion
reads continuously — that's what makes the body feel alive.

## 3D body (`assets/`, not here)

The Filament `Character3D` renderer loads a `.glb` from the app's
`assets/` (or generated into `filesDir/avatar/`). Its animation clips
must be **named after the lowercase `AvatarPose`** (`idle`, `run`,
`push`, …) so `JarvisFilamentAvatar` can address them by name.
