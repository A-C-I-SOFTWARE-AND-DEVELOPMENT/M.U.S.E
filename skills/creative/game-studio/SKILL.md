---
name: game-studio
description: "Route a game brief to a gated, engine-agnostic pipeline."
version: 1.0.0
author: Jeremiah Echerd + Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    category: creative
    tags: [game, gamedev, studio, ue5, godot, unity, 3d, graphics, orchestrator, creative, council]
    activation_phrases:
      - "make a game"
      - "build a game"
      - "create a game"
      - "game studio"
      - "vertical slice"
      - "prototype a game"
      - "greybox a level"
      - "design a game"
      - "build the vertical slice"
      - "generate a 3d asset"
    related_skills:
      - ue5-render
      - comfyui
      - aos-enterprise-council
      - kanban-orchestrator
---

# Game Studio Skill

muse's apex-grade surface for **orchestrating the production of a graphically
state-of-the-art PC game**. It routes a one-line brief through a gated,
engine-agnostic pipeline that reuses the existing `agent/studio/` production DAG,
the `ue5-render` skill (Unreal Nanite/Lumen — the SOTA-graphics path), the
`comfyui` skill (textures/concept/audio), and the `asset3d_generate` tool
(text-to-3D meshes).

## Honest framing

A single agent turn **cannot** literally ship a 100-person, $100M AAA title.
What this skill *does* is drive **every step of the production pipeline through
SOTA generative + engine APIs**, so the system goes from one-line brief →
GDD + concept art + 3D assets + greybox level + gameplay systems + lighting +
audio → a **playable, runnable vertical slice** in one orchestrated, gated,
ledgered run. Quality scales with the model and engine access you point it at.
The same framing the underlying engine uses (`docs/studio/README.md`).

**Do not claim a build that did not happen.** No "the game is built" without the
export log + the artifact listing in the same message (the `ue5-render`
"verify, don't vibe" rule).

## When to Use

On any of the activation phrases above — "make a game", "build a vertical
slice", "greybox a level", "generate a 3D asset", etc.

## Routing table

This skill is a **routing layer** (same stance as `aos-enterprise-council`). It
does not write code/assets itself — it dispatches to the agent roles in
`agents/<role>.md` via `delegate_task`, enforces maker-checker, and records the
routing decision to memory under `game-studio/<slug>/`.

| Request signal | Primary roles dispatched |
|---|---|
| "make/build/create a game", "vertical slice" | `studio-director` → `game-designer` → `graphics-tech-artist` + `3d-asset-artist` → `level-designer` → `gameplay-engineer` → `audio-designer` → `qa-playtest` → `build-release-engineer` |
| "design a game" / GDD only | `game-designer` (+ `studio-director` for scope) |
| "greybox a level" / "blockout" | `level-designer` + `gameplay-engineer` |
| "make this look SOTA" / lighting / materials | `graphics-tech-artist` + `art-direction` (UE5 path via `ue5-render`) |
| "generate a 3D asset" | `3d-asset-artist` (uses the `asset3d_generate` tool) |
| "add music / SFX" | `audio-designer` (uses `comfyui` audio) |
| "build & ship the slice" | `build-release-engineer` (**owner-gated**) |

For lightweight asks the chain collapses to: `studio-director` (scope) →
the single relevant role → `qa-playtest`.

## Engine profiles

Engines are pluggable **worker profiles** (`hermes_cli/profiles.py`), so
`/orchestrate` + `kanban_decompose` route to them by name:

| Profile | Engine | Status here |
|---|---|---|
| `game-godot` | Godot 4 | **The only headless-verifiable path in this environment / CI** (`godot --headless --export`). Default for the vertical slice. |
| `game-ue5` | Unreal Engine 5 | The documented **SOTA-graphics path** (Nanite/Lumen/MetaHuman). Requires an owner-provided GPU + licensed engine host; drives renders via the `ue5-render` skill. |
| `game-unity` | Unity 6 | Documented profile only. |

See `../../../docs/game-studio/engine-profiles.md` for the reference
`profiles:` config snippet.

## How this ties into /orchestrate and /swarm

- **Decomposition** — for a full game, hand the brief to `kanban_decompose`
  (`hermes_cli/kanban_decompose.py`); it routes child tasks to the engine
  **profile names** above and to the role agents.
- **Parallel work** — asset, level, and audio production own **disjoint file
  domains** (`assets/`, `levels/`, `audio/`), so fan them out via `/swarm`
  (`hermes_cli/swarm/` — git worktrees over proven-disjoint globs). The
  `studio-director` declares the file domains before fan-out (the
  single-writer / disjoint-ownership contract in `CLAUDE.md`).
- **Underlying engine** — long-running production is executed by
  `agent/studio/` (`StudioOrchestrator.produce_game()`); this skill is the
  muse-facing persona + gate layer on top of it.

## Owner gates

These are owner-gated (`docs/jarvis-verification-gates.md`, Owner Approval
Gate). Defer until the owner replies exactly `Yes, with authorization.`

1. **Engine process spawn** — launching a Godot/Unity export or a UE5 render.
   Gated by `MUSE_GAME_ALLOW_SPAWN=1` (modeled on `ue5-render`'s
   `MUSE_UE5_ALLOW_SPAWN`). Without the grant, `scripts/export_godot_slice.py`
   dry-runs: it prints the exact command and reports `spawned: false`.
2. **GPU / paid-API spend** — text-to-3D mesh generation and texture batches
   cost money. Surface the provider's `est_cost_usd` before bulk generation.
3. **Asset licensing** — any non-original / third-party asset requires owner
   sign-off; record provenance in the asset's `README`.
4. **Publishing a build** — uploading to Steam / itch / a store is an
   **absolute owner-only wall** (same class as the AOS five walls).

## Procedure

1. Classify scope (full game vs slice vs single asset) — `studio-director`.
2. Pick the engine profile (default `game-godot` here).
3. Run the pipeline in `workflows/game-production-pipeline.md`, honoring the
   gates above. To execute the generative DAG end-to-end from a brief, use
   `scripts/run_pipeline.py` (stub-safe; `--offline` forces zero-spend dry-run):

   ```bash
   python scripts/run_pipeline.py --title "Aether Drift" --genre "sci-fi explorer" \
       --engine godot --core-loop "scan, salvage, upgrade" --offline
   ```
4. Produce + verify the artifact. For the reference slice, run
   `scripts/export_godot_slice.py` (gated) and `scripts/verify_slice.py`.

## Verification

- A build claim must be accompanied by the export log + artifact path.
- For the reference slice: `skills/creative/game-studio/reference-slice/` exports
  to a non-empty `build/slice.x86_64` and `scripts/verify_slice.py` passes.
- Tests: `tests/skills/test_game_studio_skill.py`,
  `tests/skills/test_game_studio_slice.py`.

## Pitfalls

- Claiming a finished game from a stub/manifest run — always name what was
  actually generated vs. stubbed.
- Spawning an engine process without the owner grant.
- Sharing a writable file between two parallel roles (sequence them instead).
- Treating UE5 as runnable in this environment — it needs a GPU host; the
  runnable demo is Godot.
