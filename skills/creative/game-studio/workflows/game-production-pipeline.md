# Workflow: Game production pipeline

End-to-end staged pipeline for taking a brief to a playable, graphically
state-of-the-art vertical slice. Stages map to the `agent/studio/` `Phase` enum
and to the eight muse verification gates (`docs/jarvis-verification-gates.md`).

## Trigger

"make/build/create a game", "vertical slice", or any full-pipeline ask routed by
`../SKILL.md`.

## Required roles

`studio-director` (orchestrates) + the stage roles in `../agents/`.

## Sequence

| # | Stage | `Phase` | Role (builder) | muse gate | Owner gate? |
|---|---|---|---|---|---|
| 1 | Concept / GDD | CONCEPT | `game-designer` | Planning | — |
| 2 | Art direction | CONCEPT | `graphics-tech-artist` | Planning | — |
| 2.5 | **World Vision** | CONCEPT | `studio-director` (dispatches) + `graphics-tech-artist` (consumes) | Planning | Reactor API (key present); LingBot local = VRAM / non-commercial license |
| 2.6 | **WorldClaw spec `P`** | CONCEPT | `game-designer` (intent) → `studio-director` (plan) | Planning | — |
| 3 | Asset production | PROTOTYPE | `3d-asset-artist` | Build | **GPU/paid spend; licensing** |
| 3.5 | **WorldClaw terrain `T`** | PROTOTYPE | `level-designer` + graphics | Build | **engine spawn** (Blender MCP / UE Landscape) |
| 4 | Blockout / WorldClaw regions `O` | PROTOTYPE | `level-designer` (+ `3d-asset-artist` on open-world) | Build | **GPU/paid spend** on instance meshes |
| 4.5 | **WorldClaw refine** | PROTOTYPE | `qa-playtest` + `graphics-tech-artist` | Review | spawn (diagnostic renders) |
| 5 | Systems & gameplay | PROTOTYPE | `gameplay-engineer` | Build | — |
| 6 | Graphics / lighting | VERTICAL_SLICE | `graphics-tech-artist` | Build / Review | **engine spawn (UE5 render)** |
| 7 | Audio | VERTICAL_SLICE | `audio-designer` | Build | (paid spend if hosted) |
| 8 | Playtest / QA | VERTICAL_SLICE | `qa-playtest` | Test / Review | — |
| 9 | Build & release | (export) | `build-release-engineer` | Release | **spawn + publish (owner-only)** |

## Stage 2.5 — World Vision (cinematic / interactive-world refs)

After GDD + art direction lock a one-line look, generate a short concept clip
into the project `vision/` domain (copy from router outputs). Prefer the router:

```powershell
python C:\Users\Echer\models\lingbot-world-v2\muse\world_vision_router.py generate `
  --prompt "<art-direction one-liner>" --force-reactor
```

- **Reactor Helios** = primary on this 8GB laptop (`REACTOR_API_KEY`).
- **LingBot-World 2.0** = secondary when `status.lingbot.ready` or after
  `stop-muse.ps1` + `--force-local` (often still OOM).
- Clips are look-dev references for Stage 6 — **not** meshes and **not** a
  playable build. Full policy: `../references/world-model-routing.md`.
- Record `backend` + license in `templates/asset-provenance-log.md`.

## Stages 2.6 / 3.5 / 4 / 4.5 — WorldClaw (open-world only)

Source: Tencent Hunyuan3D, arXiv:2608.05248. Procedure:
`../references/worldclaw-pipeline.md`. Template: `../templates/world-spec.md`.

Skip this block for indoor / linear / single-room slices — those stay a
plain greybox at stage 4.

1. **2.6 spec `P`** — `game-designer` writes Intent (prompt only). `studio-director`
   completes Plan (`R`, `C_terrain`, `C_object`). File: `design/world-spec.md`.
2. **3.5 terrain `T`** — `level-designer` builds the semantic layout map, region-aware
   height field (UE Landscape + PCG, or Blender displacement), biome materials,
   and terrain-only scatter (rocks / veg). Functional props wait.
3. **4 regions `O`** — for each selected region `r ∈ R+`: render terrain →
   composition image (`comfyui`) → instance meshes (`asset3d_generate`) →
   terrain-aligned `T_place`. Replaces greybox on open-world jobs.
4. **4.5 refine** — `qa-playtest` render–inspect: pose, scale, float / sink.
   Edits stay inside the support region. Iteration budget, then stop.

World Vision clips ≠ WorldClaw meshes. Do not import an MP4 as terrain.

## Stage 3 addendum — Guide-first (LEGO box)

Every hero kit goes through `guide-first` when the seat is unsure **or**
the mesh is blocky/crap:

1. Classify task (`blender-kit` / `pbr` / `fbx-ue`).
2. Open the ledger (official + one dated tutorial). Refuse 60-second slop.
3. Distill to `instruction-card.json` (numbered steps).
4. Execute in order. Adapt names to the kit. Do not skip unwrap/ground/PBR.
5. Judge. FAIL → different URL, max 2 swaps.
6. Evidence: `lookups.md` + card + artifact in the same message.

Runner: `skills/creative/guide-first/scripts/follow_guide.py`.

## Frontier asset stage (Muse local SOTA)

Stage 3 must follow `muse-frontier-assets` + prefill `asset3d.md`:

1. Prefer CC0 → local TripoSR/Hunyuan → Meshy (owner-gated).
2. Write manifest; validate with `frontier/gates/asset_stage.py validate`.
3. Blender MCP `:9876` post (scale, budget, GLB).
4. Import Unreal via Blueprint StaticMeshComponent path; Unity optional.

Held-out prompts live in `models/laguna/frontier/walls/asset3d-wall.jsonl` — never train on them.

## Parallelization

Stages 3, 3.5/4, and 7 own **disjoint file domains** (`assets/`,
`levels/terrain/` + `levels/regions/`, `audio/`) and fan out via `/swarm`
(git worktrees over proven-disjoint globs). `studio-director` declares the
domains before fan-out (the single-writer / disjoint-ownership contract in
`CLAUDE.md`). Stage 5 (`scripts/`) can run in parallel with 3 once the GDD
lands; it waits on 3.5 if gameplay needs the height field.

## Maker-checker

- Stage 5 (`gameplay-engineer`) → reviewed at stage 8 (`qa-playtest`).
- Stages 3/7 (paid generation) → cost surfaced to owner before bulk runs.
- No role approves its own work; `studio-director` names the reviewer.

## Final outputs

- `design/GDD.md`, the engine project (e.g. the Godot slice under
  `skills/creative/game-studio/reference-slice/`), generated assets/audio with
  provenance, and a build artifact + export log.

## Acceptance criteria

- The project opens and runs in the chosen engine.
- For the reference slice: `scripts/export_godot_slice.py` (with the owner spawn
  grant) yields a non-empty `build/slice.x86_64`; `scripts/verify_slice.py`
  passes.
- A build claim is always accompanied by the export log + artifact path.
