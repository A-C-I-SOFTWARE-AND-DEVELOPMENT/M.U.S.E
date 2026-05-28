# `res/raw` — avatar animation assets (future drop-in)

The living avatar currently renders with **self-contained Compose**
renderers — `JarvisPixelAvatar` (animated sprite, the default body) and
`JarvisCharacterAvatar` (procedural humanoid). Neither needs a file here.

This directory is the **drop-in point** for finished art later:

## Rive (`jarvis.riv`)

A future `JarvisRiveAvatar` would load a `.riv` and drive it via three
state-machine inputs (`pose`, `energy`, `motion`) on a machine named
`JarvisStateMachine`. See `docs/avatar/rive-state-contract.md` for the
full pose-ordinal table. Dropping the file in + adding the `rive-android`
dependency + a thin renderer that maps `AvatarInputs` onto those inputs
is all that's needed — `LivingAvatarHost` already routes the `Rive` kind.

## 3D (`.glb`)

A future Filament renderer would load a `.glb` whose animation clips are
named after the lowercase `AvatarPose` (`idle`, `run`, `push`, …). The
`Character3D` kind is already routed through `LivingAvatarHost`.

Both upgrades are pure additions behind the existing `AvatarInputs`
contract — no call-site changes.
