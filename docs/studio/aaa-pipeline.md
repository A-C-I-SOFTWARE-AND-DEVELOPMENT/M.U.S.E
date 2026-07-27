# Studio AAA Pipeline

Technical reference for the high-fidelity game production system in `agent/studio/`.

## Modules

| Module | Purpose |
|--------|---------|
| `aaa_pipeline.py` | Main orchestrator |
| `quality_profiles.py` | Fidelity tiers and explicit budgets |
| `manifests.py` | World, asset, and pipeline manifests |
| `creature_specs.py` | Skeletal creature + animation requirements |
| `world_specs.py` | Terrain, foliage, water, atmosphere, VFX, missions, AI, audio, cinematics |
| `checkpoints.py` | Resumable stage checkpoints |
| `gates.py` | Cost, hardware, license, owner-authorization gates |
| `provider_config.py` | Image/3D/audio provider adapter configuration |
| `blender_contract.py` | Blender headless post-processing contracts |
| `ue5_generator.py` | UE5 source tree with WP/PCG/Nanite/Lumen |
| `acceptance.py` | Render-comparison and performance acceptance reports |

## API Compatibility

Existing APIs remain unchanged:

- `StudioOrchestrator.produce_game()` — generative DAG
- `StudioOrchestrator.produce_open_world_rpg()` — blueprint scaffold
- `StudioOrchestrator.produce_game_foundry()` — evidence-backed foundry
- `GameFoundry.create()` / `.build()` — now uses `ue5_generator` for Unreal projects

New API:

- `StudioOrchestrator.produce_aaa_game(brief)` — full AAA pipeline
- `AAAPipeline.run(AAAPipelineBrief)` — direct pipeline access
- `run_creature_hunting_pipeline(root, offline=True)` — verification brief

## Offline Fixtures

- `tests/studio/fixtures/creature_hunting_brief.json`
- `tests/studio/test_aaa_pipeline.py`

## Tests

```bash
scripts/run_tests.sh tests/studio/test_aaa_pipeline.py -q
scripts/run_tests.sh tests/studio/test_game_foundry.py -q
```
