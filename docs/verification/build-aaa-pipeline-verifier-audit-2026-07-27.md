# Verifier audit: build-aaa-pipeline

**Date:** 2026-07-27  
**Branch:** `orch/aaa-game-pipeline/build-aaa-pipeline`  
**Target:** `build-aaa-pipeline` (worker)

## Commands executed

```bash
uv sync --python 3.11 --extra all --extra dev
scripts/run_tests.sh tests/studio/test_aaa_pipeline.py -v          # 12 passed
scripts/run_tests.sh tests/studio/ -q                                 # 102 passed
scripts/run_tests.sh tests/skills/test_game_studio_*.py tests/studio/test_game_foundry.py -q  # 20 passed
scripts/run_tests.sh tests/skills/test_game_studio_slice.py tests/skills/test_game_studio_profiles.py tests/skills/test_game_studio_muse_sync.py -q

python scripts/run_pipeline.py --creature-hunting --offline --out /tmp/aaa_verify_run --json
python scripts/verify_slice.py /tmp/aaa_verify_run/frontier-hunt --json
python scripts/run_pipeline.py --creature-hunting --offline --out /tmp/aaa_verify_run2 --json
diff -qr /tmp/aaa_verify_run/frontier-hunt/manifests /tmp/aaa_verify_run2/frontier-hunt/manifests  # identical
python scripts/run_pipeline.py --profile aaa_benchmark --offline --out /tmp/aaa_benchmark_offline --json
```

## Fresh offline run summary

- 10 stages completed, 0 failed
- `acceptance_passed=false`, `evidence_complete=false` (honest about missing UE render evidence)
- `verify_slice.py` → `ok=true` for required manifest + UE5 config paths
- 67 artifact files under project root; UE5 tree has 20+ files (Config, Source, Content manifests)

## Defects observed (evidence paths)

1. **Asset manifest overclaims generated assets** — `manifests/asset_manifest.json` lists FBX paths (e.g. `Content/Creatures/apex_serpent/apex_serpent.fbx`) with `previs_only:false`, but `assets/*.stub.json` stubs exist and no FBX/Content/Creatures tree is written.

2. **validation_ref targets missing files** — entries reference `validation/creature_*.json` but only `validation/gate_report.json` exists.

3. **Provenance marks stub assets as commercial-safe originals** — `provenance/creature_apex_serpent.json` has `source:"original"`, `license:"original"`, `safety_status:"passed"`, `allowed_uses:["private","commercial"]` while asset is an offline stub.

4. **Offline acceptance overrides quality gate** — `agent/studio/aaa_pipeline.py` lines 338–351 force `quality_gate_passed=True` despite `failures` containing `missing_metric:*` entries in `reports/acceptance_report.json`.

5. **Validation stage bypasses hardware gate failure offline** — `validation/gate_report.json` shows `hardware.passed=false` (no UE5, insufficient VRAM/RAM) but validation stage still completes when `offline=true`.

6. **CLI `gates_passed` is misleading** — run_pipeline JSON reports `gates_passed:true` while hardware gate failed; field reflects `not stages_failed`, not gate evaluation.

7. **DefaultEngine.ini GameMode path mismatch** — `GlobalDefaultGameMode=/Script/Game.GameGameMode` but module is `FrontierHunt` (`FrontierHuntGameMode` generated).

8. **Map asset is explicit placeholder** — `Content/Maps/L_OpenWorld.umap.placeholder` only; no compiled map.

## Positive findings

- Quality profiles define 9 explicit budget dataclasses with measurable thresholds; direct `evaluate_acceptance()` enforces over-budget metrics when not overridden.
- Previs manifest correctly sets `authoritative:false`.
- No Monster Hunter / Capcom IP strings in generated artifacts or studio modules scanned.
- Studio API extended compatibly via `StudioOrchestrator.produce_aaa_game()`.
- Checkpoint resume tested and passing.
