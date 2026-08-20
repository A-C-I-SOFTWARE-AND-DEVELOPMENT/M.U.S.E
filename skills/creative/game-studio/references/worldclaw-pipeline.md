# WorldClaw → Muse Game Studio

Distill of **WorldClaw: Agentic 3D Open-World Generation at Scale**
(Guo, Li, Li, Huang — Tencent Hunyuan3D, arXiv:2608.05248, 5 Aug 2026)
folded into this skill's staged pipeline.

- Paper: https://arxiv.org/abs/2608.05248
- HTML: https://arxiv.org/html/2608.05248v1
- Project: https://tencent-hunyuan.github.io/Hunyuan3D-WorldClaw/

**WorldClaw is not a downloadable model and the authors did not release code.**
It is an agentic *workflow*. We take the stages, the intermediate specs, and
the render–inspect loop. We do **not** claim their 4×H20 results on this laptop.

## What the paper actually is

A globally coherent world need not be generated everywhere at once. Shared
constraints (semantics, layout, terrain) are locked first; instance-level
content is realized only in regions that need it.

```
q  →  P = F_plan(q)  →  T = F_terrain(P)  →  O = F_region(P, T)  →  S = Compose(T, O)
```

| Stage | Output | Meaning |
|---|---|---|
| Intent + planning | `P = (R, C_terrain, C_object)` | Regions, terrain constraints, object constraints. Shared semantic interface. |
| Global terrain | `T` | Semantic layout map + region-aware height field + materials + scattered terrain assets. |
| Regional objects | `O` | Per-region editable textured meshes + placement transforms. |
| Compose | `S` | Explicit, explorable, independently editable world (not video, not Gaussians). |

Representation contract (the paper's load-bearing claim): **terrain + instance
meshes**, so the result can enter a game engine. Video / splat / panorama is a
look-dev artifact, not a world.

## Paper agents → our 9 seats

No new seats. WorldClaw's specialized agents map onto the existing roster.

| WorldClaw agent | Muse seat | Writes |
|---|---|---|
| Intent analysis (extract only what the prompt said) | `game-designer` | `design/world-spec.md` §Intent |
| Scene planning (complete the schema, no geometry) | `studio-director` | `design/world-spec.md` §Plan |
| Terrain planning | `level-designer` | `levels/terrain-spec.md` |
| Terrain assets + materials | `3d-asset-artist` + `graphics-tech-artist` | `assets/terrain/`, materials |
| Height field + scatter + Blender refine | `level-designer` | `levels/terrain/` |
| Regional planning (pick `R+ ⊆ R`) | `level-designer` | `levels/regions/` |
| Region compose → segment → reconstruct → place | `3d-asset-artist` | `assets/instances/` |
| Object + contact refine (render–inspect) | `qa-playtest` + `graphics-tech-artist` | reports + transforms |
| World Vision (Reactor / LingBot) | **tool**, not a WorldClaw stage | `vision/` look-dev only |

## Muse stages (inserted, not replacing GDD / gameplay / QA)

Trigger **only** when the brief is an open world, multi-biome map, explorable
terrain, or "world from a prompt". Linear / indoor / single-room slices keep
the old greybox path.

| # | Muse stage | WorldClaw analogue | Builder | Domain |
|---|---|---|---|---|
| 1 | GDD | (ours; paper has no GDD) | `game-designer` | `design/` |
| 2 | Art direction | shared style attrs on `P` | `graphics-tech-artist` | `design/` |
| 2.5 | World Vision | **not in the paper** — cinematic refs | router + graphics | `vision/` |
| **2.6** | **World spec** | §2.1 Intent + scene plan | designer → director | `design/world-spec.md` |
| 3 | Hero / gameplay assets | paper's instance pass is later | `3d-asset-artist` | `assets/` |
| **3.5** | **Global terrain** | §2.2 | `level-designer` | `levels/terrain/` |
| **4** | **Regional populate** (replaces greybox on open-world jobs) | §2.3.1–2.3.2 | `3d-asset-artist` + `level-designer` | `levels/regions/`, `assets/instances/` |
| **4.5** | **Render–inspect refine** | §2.3.3 | `qa-playtest` + graphics | reports |
| 5–9 | Systems, lighting, audio, QA, export | unchanged | existing seats | existing domains |

World Vision stays a **clip**. WorldClaw stays **meshes**. Never swap them.

## Intermediate specs (must exist on disk)

### `P` — `design/world-spec.md` (+ optional `.json`)

Intent analysis writes **only** what the prompt stated. Scene planning then
fills the schema. Do not mix the two passes.

```
R            major regions, attributes, adjacency
C_terrain    terrain type, landform, surface, terrain-associated assets per region
C_object     categories, appearance, density, region-level spatial relations
shared       theme, visual style, material prefs, atmosphere
```

Template: `../templates/world-spec.md`.

### `P_terrain` — `levels/terrain-spec.md`

```
p_layout     region categories, relative positions, adjacency, coverage
p_asset      terrain-asset categories, affinities, densities
p_material   surface types, styles, texture requirements
θ_terrain    world scale, base elevations, noise freqs/amps, geomorphic ops, blend widths
I_concept    optional (World Vision still or ComfyUI concept)
```

### `T` — `levels/terrain/`

1. **Semantic layout map** `I_layout` — color-coded 2D partition (not a floorplan).
2. **Height field** — soft region weights blend base elevation + multi-frequency
   noise + geomorphic ops (peak / dune / terrace / erosion):

   `H(x) = Σ_r m̃_r(x) [ h_r + Σ_k w_{r,k} N_{r,k}(x) + Σ_j α_{r,j} G_{r,j}(x) ]`

3. **Materials** — generative PBR for hero surfaces; procedural / tileable for
   large biomes. Same `m̃_r` weights blend materials.
4. **Scatter** — rocks, veg clusters, landform attachments only. Functional
   objects wait for the regional pass.
5. **Refine** — render, inspect, edit θ / blend / texture scale / scatter /
   lighting. Stop when the check passes or the iteration budget is spent.

### `O_r` — `assets/instances/<region>/`

For each selected region `r ∈ R+`:

1. Render local terrain, keep camera `κ_r`.
2. Terrain-conditioned composition image `I_comp^r` (image model, not a mesh).
3. Instance split (SAM3 if present; else generate one asset per listed object).
4. Image-to-3D mesh `M_i` + appearance `U_i`.
5. Place with a terrain-aligned transform `T_place^i` (ray intersection +
   contact-ratio search). No floating, no deep penetration.
6. Refine: pose / scale / mesh quality, then object–terrain co-deformation
   restricted to the support region.

## This machine (honest)

Paper impl (§3.1): Claude Opus 4.8, GPT-Image-2, SAM3, SAM3D, Hunyuan3D,
Blender 5.1.1, **4× NVIDIA H20**.

This box: RTX 5070 Laptop **8 GB**, 32 GB RAM, Blender **5.2**, UE **5.8**,
ComfyUI, Hunyuan3D / Meshy / TripoSR via `asset3d_generate`.

| Paper tool | Muse stand-in | Gate |
|---|---|---|
| Claude Opus 4.8 planner | seat LoRAs on Qwen3.8-27B UD-Q3_K_XL (when landed) | none |
| GPT-Image-2 layout + compose | `comfyui` | spend if hosted |
| SAM3 instance split | skip if missing — one-prompt-per-object | — |
| SAM3D reconstruct | `asset3d_generate` (Hunyuan3D → TripoSR → Meshy) | **paid/GPU** |
| Hunyuan3D PBR refine | same tool + Blender MCP `:9876` | spend |
| Blender 5.1.1 MCP | Blender 5.2 MCP (already in frontier-assets) | spawn |
| 4×H20 height field | UE 5.8 Landscape + PCG (`ue5-mega-world`) **or** Blender displacement | spawn |

Do not claim SAM3 / SAM3D / GPT-Image-2 / Opus 4.8 ran unless the log says so.

## Limitations we inherit (paper §5)

1. **Quality is bounded by the backbone.** Open-source planners often emit
   non-executable terrain/material programs. Layout maps from weak image models
   are frequently unusable. Say so when that happens.
2. **LLM-written Blender graphs are brittle.** Scale errors and broken node
   links show up as bad landforms. Budget render–inspect loops; do not one-shot.
3. **Instance-wise reconstruct + refine is slow.** Fine for a slice region;
   do not promise a dense km² world in one turn on 8 GB.

## What WorldClaw does not do

- Gameplay, input, AI, audio, packaging — still stages 5–9.
- A playable build. `S` is an editable world, not `slice.exe`.
- Replace World Vision. Clips stay look-dev.
- Purple/indigo/violet palettes. Keep teal / emerald / amber.

## Verification

A WorldClaw stage is done only when all of these exist in the same message:

- `design/world-spec.md` with Intent and Plan as separate sections
- `levels/terrain/` height + layout map + provenance
- at least one region in `assets/instances/` with mesh + `T_place`
- a diagnostic render (RGB; instance/normal/depth if the engine can emit them)
- `qa-playtest` contact note: no systematic float / sink

No file path → the stage did not happen.
