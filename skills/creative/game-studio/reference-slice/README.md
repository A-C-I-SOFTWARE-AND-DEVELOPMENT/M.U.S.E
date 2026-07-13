# Vertical Slice (Godot 4) — muse Game Studio reference

A small but **real, runnable** vertical slice produced by the `game-studio`
skill. It is the verification artifact proving the pipeline ends in a playable
build — not a scaffold stub.

## What's in it

- **`project.godot`** — Godot 4.x project, Forward+ renderer.
- **`scenes/Main.tscn`** — greybox level: a `WorldEnvironment` with a procedural
  sky and SOTA post (SDFGI global illumination, SSAO, SSIL, SSR, glow, ACES
  tonemap), a shadow-casting `DirectionalLight3D`, a floor + walls + ramp
  greybox, and a `HeroProp` slot for the generated asset.
- **`scenes/Player.tscn` + `scripts/player.gd`** — a `CharacterBody3D` controller
  (WASD move, Space jump, mouse-look), pure GDScript, no plugins.
- **A real game loop** — `scripts/game.gd` (manager) + `scenes/Collectible.tscn`
  + `scripts/collectible.gd`: collect the glowing pickups, a HUD tracks
  `Collected: X / N`, and clearing them all shows a win message.
- **`assets/prop.glb`** — placeholder hero prop; the slot the `asset3d_generate`
  tool fills (see `assets/README.md`).
- **`export_presets.cfg`** — a headless `Linux/X11` preset named `linux`.

## Open it

```bash
godot --path skills/creative/game-studio/reference-slice
```

## Build it headlessly (owner-gated)

Use the skill's gated wrapper — it refuses to spawn a process unless
`MUSE_GAME_ALLOW_SPAWN=1` is set:

```bash
MUSE_GAME_ALLOW_SPAWN=1 python skills/creative/game-studio/scripts/export_godot_slice.py
# → build/slice.x86_64  (+ the export log)
python skills/creative/game-studio/scripts/verify_slice.py \
    skills/creative/game-studio/reference-slice/build/slice.x86_64
```

(Headless export needs the matching Godot export templates installed. Without
them, the project still opens and runs — `godot --headless --quit --path .`
validates it loads.)

## Regenerate the hero asset

See `assets/README.md` — `3d-asset-artist` → `asset3d_generate` → copy the
returned `.glb` over `assets/prop.glb`, then record provenance.

## Game-elements contract + muse sync

- **`slice-manifest.json`** enumerates every game element (scenes, scripts,
  states, collectibles, objective, timer, sfx, HUD, input actions, graphics
  flags/set-pieces, export preset, muse mapping). It is drift-proofed against
  the actual project by `tests/skills/test_game_studio_muse_sync.py`.
- **`../scripts/sync_slice_to_muse.py`** maps a verified build to a completed
  *simulation* mission and records it through muse_universe's
  `AchievementBridge` (`--dry-run` prints the outbox without recording).
- **`tools/capture/Capture.tscn`** is the deterministic acceptance-capture
  harness (title + in-run frames via Movie Maker mode); see
  `docs/game-studio/SLICE_BUILD_EVIDENCE_2026-07-13.md` for the rendered
  evidence and full build provenance.
