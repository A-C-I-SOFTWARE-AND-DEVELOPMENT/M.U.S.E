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
| 3 | Asset production | PROTOTYPE | `3d-asset-artist` | Build | **GPU/paid spend; licensing** |
| 4 | Blockout / greybox | PROTOTYPE | `level-designer` | Build | — |
| 5 | Systems & gameplay | PROTOTYPE | `gameplay-engineer` | Build | — |
| 6 | Graphics / lighting | VERTICAL_SLICE | `graphics-tech-artist` | Build / Review | **engine spawn (UE5 render)** |
| 7 | Audio | VERTICAL_SLICE | `audio-designer` | Build | (paid spend if hosted) |
| 8 | Playtest / QA | VERTICAL_SLICE | `qa-playtest` | Test / Review | — |
| 9 | Build & release | (export) | `build-release-engineer` | Release | **spawn + publish (owner-only)** |

## Parallelization

Stages 3, 4, and 7 own **disjoint file domains** (`assets/`, `levels/`,
`audio/`) and fan out via `/swarm` (git worktrees over proven-disjoint globs).
`studio-director` declares the domains before fan-out (the single-writer /
disjoint-ownership contract in `CLAUDE.md`). Stage 5 (`scripts/`) can run in
parallel with 3/4 once the GDD (stage 1) lands.

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
