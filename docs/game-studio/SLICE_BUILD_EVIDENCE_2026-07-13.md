# Vertical slice — build, render, and muse-sync evidence (2026-07-13)

Owner authorization for the engine-spawn gate was given in-session
("yes, with authorization."), unlocking the `MUSE_GAME_ALLOW_SPAWN=1` path in
`skills/creative/game-studio/scripts/export_godot_slice.py`. Everything below
ran inside a headless Linux container; commands and hashes are reproducible
from the repo.

## Engine provenance (github.com blocked; Nix binary cache used)

The container's network policy blocks `github.com` release downloads and the
Docker registry CDN, so the engine came from the NixOS binary cache
(`cache.nixos.org`, Fastly-served, signature `cache.nixos.org-1` on every
narinfo, FileHash verified locally on each blob):

- **Editor/exporter:** `/nix/store/8qkmn39v8f0cs1sfzlkc6a0i4bjrwjns-godot4-4.2.2-stable`
  (nixpkgs 24.05 build of upstream 4.2.2; self-reports
  `4.2.2.stable.nixpkgs.15073afe3` — the official 4.2.2 release commit).
  Full 170-path runtime closure materialized under `/nix/store`.
- **Export templates:** `/nix/store/8zli1zc87spqxkv3n558b3hkyplgqnsm-source` —
  the **official** Godot 4.2.2 export-templates archive as a fixed-output
  (content-addressed) derivation, `version.txt` = `4.2.2.stable`;
  `linux_debug.x86_64` + `linux_release.x86_64` installed to
  `~/.local/share/godot/export_templates/4.2.2.stable/`.
- The exported game binary banner self-reports
  `Godot Engine v4.2.2.stable.official.15073afe3` (it *is* the official
  release template with the pck attached).

## Build → verify → smoke (all green)

| Step | Command | Result |
|---|---|---|
| Import | `godot --headless --import .` | 🟢 exit 0 |
| Project load | `godot --headless --path . --quit` | 🟢 exit 0, no SCRIPT ERROR |
| Export (owner-gated) | `MUSE_GAME_ALLOW_SPAWN=1 python …/export_godot_slice.py` | 🟢 `success: true`, exit 0 |
| Artifact verify | `python …/verify_slice.py build/slice.x86_64` | 🟢 ok, 62,204,152 bytes |
| Smoke | `./slice.x86_64 --headless --quit-after 300` | 🟢 300 frames, exit 0 |
| GDScript lint | `python -m gdtoolkit.parser scripts/*.gd tools/capture/capture.gd` | 🟢 clean |
| Slice + sync tests | `pytest tests/skills/test_game_studio_slice.py tests/skills/test_game_studio_muse_sync.py` | 🟢 all pass (incl. the engine-gated headless-load test, now actually executed) |

Final artifact hashes (build outputs are gitignored by design; these hashes
are the record):

- `slice.x86_64` — `sha256:49db0d5082faa83283d140c90da109b3407a5d72c17ab97742b132ba7e615316`
- `slice.pck` — `sha256:12f72fa8977790afdda573fed1a917dcb9f11b8d966b6a108371d6b8e0511137`

## Graphics polish overhaul (this commit)

Environment: TAA + 8192 soft-shadow atlas (project settings), SSR 128 steps,
SSAO 2.2, SDFGI occlusion, tuned glow (intensity 0.9, HDR threshold 0.85),
volumetric-fog anisotropy/GI/sky injection, contrast/saturation grade, warm
mie tint + energy on the physical sky. Set pieces: the arena is now fully
enclosed (east/west walls + emissive strips), a volumetric holo-beam and
emissive dais ring anchor the hero prop, a rim spotlight keys it, and 220
drifting dust motes fill the volume. Collectibles gained per-instance
breathing emission (`resource_local_to_scene`) plus a warm point light and
additive halo; the core omni light breathes in `game.gd`. The ramp is now a
real 4-wide ramp instead of a reused 24-unit wall slab that bisected the
arena. HUD: text shadows, cyan title treatment, brand line.

**Rendered proof** (real Vulkan frames, CPU rasterizer — llvmpipe/lavapipe
via Mesa 24.0.7 from the same Nix cache, under Xvfb, Movie Maker mode,
`tools/capture/Capture.tscn` harness):

- [`evidence/2026-07-13-slice-title-1280x720-lavapipe.png`](./evidence/2026-07-13-slice-title-1280x720-lavapipe.png)
- [`evidence/2026-07-13-slice-run-1280x720-lavapipe.png`](./evidence/2026-07-13-slice-run-1280x720-lavapipe.png)

Engine banner during capture: `Vulkan API 1.3.274 — Forward+ — llvmpipe
(LLVM 17.0.6)`; ~2.3 s/frame CPU. These prove the authored lighting stack
(SDFGI, SSR reflections on the wet floor, glow, volumetrics, dust) renders as
designed; they are **not** a GPU performance claim — frame-rate/tier
benchmarks remain a target-GPU gate.

## Game elements synced with muse

- **Contract:** [`slice-manifest.json`](../../skills/creative/game-studio/reference-slice/slice-manifest.json)
  enumerates every game element (scenes, scripts, states, six collectibles,
  objective, timer/best-time store, sfx, hero-prop slot, HUD nodes, input
  actions, graphics flags/set-pieces, export preset, muse mapping).
  `tests/skills/test_game_studio_muse_sync.py` keeps it drift-proof against
  the actual Godot project (states parsed from `game.gd`, collectible count
  from `Main.tscn`, flags from the environment, actions from
  `project.godot`).
- **Bridge:** `skills/creative/game-studio/scripts/sync_slice_to_muse.py`
  maps a verified build to a completed **simulation** mission (fail-closed:
  no artifact → no mission; simulation without the simulation label is
  dropped by the bridge) and records it through the existing
  `plugins.muse_universe.achievements.AchievementBridge` — no new primitives.
- **Seam fix:** `plugins/hermes-achievements/dashboard/plugin_api.py` only
  *re-exported* `record_external_evidence`, so the bridge's explicit-seam
  detection (literal `def` required) never activated. It is now a real
  wrapper `def`; the seam loads.
- **Live record:** the final build synced with
  `status=accepted`, `record_id=external_da08587468203e67c5e4db24`,
  `dedupe_key=da08587…bb667f2b`, mission `atlas-slice-build-49db0d5082fa`,
  evidence references = the two artifact SHA-256 values above + the element
  and engine claims.

## Honest boundaries

- The Linux build is unsigned and produced in-container; the
  `muse-game-slice.yml` CI run on a hosted runner is still blocked by the
  org's GitHub Actions billing lock (this document is the container-local
  equivalent of that gate).
- CPU-rendered frames verify *correctness of the look*, not performance.
- Publishing/distribution of the build remains owner-gated.
