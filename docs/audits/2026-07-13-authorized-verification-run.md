# Authorized verification run — 2026-07-13

**Scope:** executes the verification commands that the 2026-07-12 Atlas/Fleet
program streams were prohibited from running (see
[`2026-07-12-muse-atlas-universe-verification.md`](./2026-07-12-muse-atlas-universe-verification.md)
"Commands deliberately not run" and
[`2026-07-12-fabrication-game-cinema-verification.md`](./2026-07-12-fabrication-game-cinema-verification.md)
"Verification commands"), limited to what a headless Linux container can
honestly evidence. UE 5.6 / GPU / Windows / headset / signing / third-party
gates remain open and are re-listed at the end.

**Environment:** fresh Linux container (kernel 6.18), Python 3.11.15 with the
repo venv (`pip install -e ".[all,dev]"`), Ubuntu clang 18.1.3, Node v22.22.2,
uv 0.8.17, ruff 0.15.8.
**Base:** branch `claude/desktop-ui-verification`, commit `8096e73da`
(= checkpoint `78793725b` + game-slice commit), PR #629 vs `main` `300cdba95`.

## Executed gates and results

| # | Gate (matrix reference) | Command | Result |
|---|---|---|---|
| V1 | Universe/studio/cockpit suites (§19; fabrication brief suites) | `pytest tests/muse_universe tests/studio tests/gateway/test_cockpit_studio.py` | 🟢 **332 passed, 0 failed** (10.3s) |
| V2 | Planned asset/source/self-check specs (§19) | `pytest tests/assets/test_atlas_crown_assets.py tests/test_synapse_universe_source.py tests/test_synapse_universe_selfcheck.py tests/skills/test_game_studio_{slice,pipeline,profiles,skill}.py` | 🔴→🟢 first-ever run found **2 failures**, fixed in this commit (below); now **55 passed, 1 skipped** |
| V3 | Full gateway suite (C5 precedent) | `pytest tests/gateway` | 🔴→🟢 **6321 passed, 74 skipped**; 2 contract-freeze failures fixed by regenerating the frozen contract (below) |
| V4 | Full-repo collection (C5 precedent) | `pytest --collect-only -q` | 🟢 **31,384/31,408 collected, 24 deselected, zero errors** (69s; up from 29,745 on 2026-06-20) |
| V5 | Blocking lint (C1) | `ruff check .` | 🔴→🟢 4 errors, all inside the byte-preserved `recovered-agent-sources/` archive → archive excluded from lint (below); now **All checks passed** |
| V6 | Type gate (parallel-contract rule: no new diagnostics vs base) | `uv run ty check` | 🟢 **2,718 diagnostics vs 2,881 on `main` base** — no new diagnostics (−163) |
| V7 | Geometry self-check, no UE (§19) | `clang++ -std=c++17 -Wall -Wextra -Werror … geometry-selfcheck` | 🟢 `OK: MuseSacredGeometry C++ self-check passed` |
| V8 | Universe self-check, no UE (§19; first-ever run) | `clang++ -std=c++17 -Wall -Wextra -Werror … universe-selfcheck` | 🟢 `OK: Synapse universe C++ self-check passed` + reference JSON emitted (210 m sphere, 1800 m spine, 1200 m rings, ±0.25°/s counter-rotation, stationary dock at 900 s, ±0.0325 m stereo offsets, stable vessel id, deterministic shot hash) |
| V9 | Provenance validator (source-asset evidence; first-ever run) | `python assets/atlas-crown/validate_assets.py --check` | 🟢 `Atlas Crown provenance is current` |
| V10 | GDScript lint (game-slice CI step) | `python -m gdtoolkit.parser skills/creative/game-studio/reference-slice/scripts/*.gd` | 🟢 clean |
| V11 | Byte-compile of program packages | `python -m compileall plugins/muse_universe agent/studio` | 🟢 clean |
| V12 | Security scan (§17 remaining gate) | `python scripts/scan_secrets.py --base <main>` | 🔴→🟢 **8 blocking findings, all verified false positives — no credential material in the diff** (below) |

## Defects found by the first authorized run, fixed in this commit

1. **`tests/test_synapse_universe_source.py::test_stereo_rig_uses_two_physical_cameras_and_symmetric_offsets`** —
   `MuseStereoRigActor.cpp` rejected only `SymmetricOffAxis` instead of
   requiring `SymmetricToeIn`. The policy check is now a positive allowlist
   (`!= EMuseStereoPolicy::SymmetricToeIn` fails closed), so any future policy
   value is rejected until verified — consistent with the program's fail-closed
   invariant and the spec token.
2. **`tests/test_synapse_universe_source.py::test_typed_records_cover_every_frozen_entity_family`** —
   the frozen-contract comment in `MuseUniverseTypes.h` was line-wrapped
   mid-phrase; reflowed so "Unknown fields are intentionally ignored" is
   contiguous. Comment-only; no code change.
3. **Cockpit wire-contract drift** — the checkpoint changed the
   `/v1/cockpit/approvals/...` handler docstring without regenerating the
   frozen contract. Regenerated via `scripts/generate_cockpit_contract.py`
   (127 routes, 125 handlers, 10 owner-gated, 6 unauthenticated);
   `tests/gateway/test_cockpit_contract_freeze.py` now passes.
4. **Lint gate vs recovery archive** — `ruff check .` failed on 4 findings
   inside `recovered-agent-sources/` (including an intentionally broken
   archived prototype). The archive is byte-preserved historical evidence,
   not live code; it is now `extend-exclude`d in `pyproject.toml` alongside
   the existing vendored-payload exclusion.
5. **Secret-scan false positives** — the 8 blocking findings were:
   7× compose env passthroughs of the form `NAME: ${NAME}` /
   `NAME: ${NAME:-}` (references resolved from the runtime environment —
   no values on the lines) in `integrations/n8n/docker-compose.yml` and the
   archived `n8n-stage1-prototype` copy, and 1× the deliberate
   leak-**rejection** fixture in `tests/gateway/test_cockpit_api.py` (asserts
   the API refuses to store a fake key). Fix: `scripts/scan_secrets.py` now
   suppresses pure `${VAR}` interpolation assignments (mirroring the existing
   GitHub-Actions-expression rule, with regression tests in
   `tests/test_scan_secrets.py`), and the fixture line carries
   `# pragma: allowlist secret`. **No secret was committed;** the
   already-public branch contains references only.

## Status effect

- The `LAUNCH_STATUS_CURRENT.md` release blocker **"authorized
  Python/source/self-check and security runs"** is closed by V1–V12.
- Matrix §19 execution evidence now exists for every Python spec suite and
  both no-engine C++ self-checks; §17's "automated secret scan … unrun" is
  closed.
- CI note: GitHub Actions is currently org-locked ("account is locked due to
  a billing issue"), so every hosted-runner job — including `tests.yml` on
  `main` — fails in seconds with no runner. The results above are the
  container-local equivalents; CI re-runs require the owner to unlock
  billing.

## Still open (unchanged by this run)

- **UE 5.6 lane:** UBT compile, `Synapse.*` automation, USD import, packaged
  traversal, MRQ render + stereo EXR/QC, OpenXR, Pixel Streaming.
- **GPU/thermal benchmarks** for Ultra/High/Balanced tiers; desktop-webview
  visual pass.
- **Browser/accessibility/performance matrix acceptance** for the Desktop
  Omni surface (evidence-generating runs are possible headlessly; acceptance
  itself is an owner review).
- **Owner-gated:** billing unlock for Actions; signing/updater keys; live
  Supabase deployment evidence for the remote authority; n8n credentials and
  delegate-dispatch default; merge of PR #629 to `main`
  (`main_branch_merge`, exact phrase required).
- **Deferred next streams** (deliberate ownership boundaries, not regressions):
  `agent/studio` ↔ `service.py`/UI production-API wiring (Shipyard
  `/validate`, Fabrication/Game/Cinema/Release routes), Nero-Fleet observatory
  seams 1b–1d, and the 8 device-consolidation fixes queued for test-first
  porting.
