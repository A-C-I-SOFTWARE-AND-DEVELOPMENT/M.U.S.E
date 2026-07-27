---
name: game-asset-pipeline
description: Typed asset pipeline with manifests, Blender, and UE5 import.
version: "1.0"
author: MUSE Studio
license: MIT
metadata:
  hermes:
    category: creative
    tags: [game, assets, pipeline, ue5, blender]
---

# Game Asset Pipeline Skill

Routes high-fidelity asset production through typed manifests, provider adapters, Blender post-processing contracts, and UE5 import paths.

## When to Use

- Decomposing a game brief into world and asset manifests
- Configuring image, 3D, or audio provider adapters
- Running Blender headless post-processing on generated meshes
- Validating PBR texture budgets and skeletal creature requirements

## Prerequisites

- `agent/studio/` AAA pipeline modules installed
- For offline dry-runs: `AXIOM_STUDIO_OFFLINE=1`
- For real generation: provider API keys in `~/.hermes/.env`

## How to Run

```bash
python scripts/run_pipeline.py --creature-hunting --offline
python scripts/verify_slice.py aaa_pipeline_output/frontier-hunt --json
```

## Quick Reference

| Stage | Output |
|-------|--------|
| decompose | `manifests/world_manifest.json`, `asset_manifest.json` |
| previs | `previs/previs_manifest.json` (non-authoritative) |
| blender_post | `blender/*_contract.json`, `*_headless.py` |
| creature_rig | `manifests/creatures/*.json` |
| ue5_source | `ue5_project/` with Config, Source, Content |
| provenance | `provenance/provenance_index.json` |
| acceptance | `reports/acceptance_report.json` |

## Procedure

1. Load quality profile (`high_fidelity` or `aaa_benchmark`).
2. Run `AAAPipeline.run()` with an `AAAPipelineBrief`.
3. Inspect manifests under `<project_root>/manifests/`.
4. Verify with `scripts/verify_slice.py`.
5. Do not claim visual equivalence without UE render evidence.

## Pitfalls

- LingBot/Reactor previs is reference-only, not authoritative.
- Offline mode defers render evidence; acceptance report marks `evidence_complete: false`.
- Missing licenses fail closed via `LicenseGate`.

## Verification

```bash
scripts/run_tests.sh tests/studio/test_aaa_pipeline.py -q
```
