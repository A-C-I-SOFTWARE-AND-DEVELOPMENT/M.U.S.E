# AAA Game Production Pipeline

Evidence-driven high-fidelity Unreal Engine 5 production pipeline for MUSE Game Studio.

## Overview

The AAA pipeline extends `agent/studio/` with typed manifests, resumable checkpoints, provider adapters, Blender post-processing contracts, UE5 source generation, and acceptance gates. It targets open-world creature-hunting quality benchmarks without copying any commercial IP.

## Entry Points

```bash
# CLI
python scripts/run_pipeline.py --creature-hunting --offline --json

# Verification
python scripts/verify_slice.py aaa_pipeline_output/frontier-hunt --json

# Python API
from agent.studio import AAAPipeline, AAAPipelineBrief, run_creature_hunting_pipeline
```

## Pipeline Stages

1. **decompose** — world + asset manifests from brief
2. **previs** — LingBot/Reactor previs (non-authoritative)
3. **world_systems** — terrain, foliage, water, atmosphere, VFX, missions, AI, audio, cinematics
4. **creature_rig** — skeletal creature manifests with 15 required animations
5. **blender_post** — headless Blender contracts per asset
6. **asset_generation** — provider-configured image/3D/audio stubs or real calls
7. **ue5_source** — UE5 project with World Partition, PCG, Nanite, Lumen, VSM, HLOD, scalability
8. **provenance** — immutable asset provenance index
9. **validation** — cost, hardware, license gates
10. **acceptance** — render-comparison and performance report

## Quality Profiles

| Profile | Use |
|---------|-----|
| `previz` | Fast iteration, no render evidence |
| `high_fidelity` | Production UE5 open-world target |
| `aaa_benchmark` | Maximum fidelity; requires measured UE evidence |

Profiles define explicit polygon, texture, material, animation, draw-call, memory, frame-time, lighting, streaming, and asset-density budgets in `agent/studio/quality_profiles.py`.

## Honest Claims Policy

- No visual equivalence claimed without real UE render evidence.
- Offline mode sets `evidence_complete: false` in acceptance reports.
- Previs sources are marked `authoritative: false`.
- Missing providers, licenses, or engine installs fail closed with actionable errors.

## Related Skills

- `skills/creative/game-studio/` — routing and Godot reference slice
- `skills/creative/game-asset-pipeline/` — asset pipeline operations
- `skills/creative/muse-frontier-assets/` — frontier biome/creature specs

## Local production run

The verified Windows toolchain is Blender 5.2 LTS plus Unreal Engine 5.8:

```powershell
python scripts/run_pipeline.py --creature-hunting `
  --world-previs --previs-backend reactor `
  --execute-blender --package --out final_pipeline_output --json
```

This renders an original Blender conditioning frame, invokes the configured
Reactor/LingBot router for RGB-only world previs, emits UE camera conditioning,
creates proof FBX assets, compiles the generated C++ project, authors and audits
`L_OpenWorld`, and optionally cooks Win64. Native commands persist stdout,
stderr, and machine-readable evidence below `ue5_project/Evidence/`.

Build and verify the deterministic playable proof separately:

```powershell
python scripts/build_playable_proof.py --out final_proof_game --json
python scripts/verify_playable_proof.py final_proof_game/FrontierHunt
```

The proof must pass editor compilation, map authoring, map audit, UE automation,
Win64 cook/package, and packaged-executable smoke launch before `playable` can
be true.

## Provider and licensing limits

- Reactor Helios is preferred when its existing credential is available.
- Local LingBot is a fallback only. Its CC BY-NC-SA output is non-commercial,
  and upstream expects substantially more than one 8 GB GPU.
- World-model video is visual reference, never geometry or authoritative game
  content.
- A queued cloud response is not an asset. Mesh adapters must return a non-empty
  local GLB, glTF, or FBX before a manifest references it.
- Blender procedural meshes are original proof assets, but production acceptance
  remains blocked until rig, animation, texture, and quality validation passes.
- Missing credentials, license terms, renders, performance metrics, or artifacts
  remain visible failures; no offline or proof flag overrides those gates.

## Recovery

- Re-run the same command to resume completed stages. Native gates resume only
  when source fingerprints and evidence artifacts still match.
- Use `--previs-image PATH` if Blender source rendering is unavailable.
- Use `--previs-backend reactor` to avoid the local multi-GPU LingBot path on an
  8 GB laptop GPU.
- Inspect `validation/gate_report.json`, `reports/acceptance_report.json`,
  `ue5_project/Evidence/toolchain-report.json`, and command logs before retrying.
