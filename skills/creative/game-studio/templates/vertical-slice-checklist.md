# Vertical Slice Acceptance Checklist — <TITLE>

> Owned by `qa-playtest`. The slice is not "done" until every box is checked
> with **evidence** (a log line, a screenshot path, a test name) in the same
> report — no vibe-passes. Maps to the muse Test / Review / Release gates.

## Builds & runs
- [ ] Project opens in the target engine with no script/parse errors
      (`godot --headless --quit` returns 0).
- [ ] Headless export produces a non-empty artifact (`export_godot_slice.py`
      + `verify_slice.py` pass).

## Core loop
- [ ] The core loop from the GDD is playable start-to-finish.
- [ ] Win/lose (or objective-complete) state is reachable and signalled.
- [ ] Controls respond (move, primary verb, camera).

## Presentation
- [ ] Lighting/post matches the art-direction brief (no obvious placeholders
      left where final intent was specified).
- [ ] HUD shows the player's objective/progress.
- [ ] Audio cues fire on their mapped events (or are explicitly deferred).

## Content provenance
- [ ] Every non-placeholder asset is logged in `asset-provenance-log.md`
      with a license, and owner-approved if third-party/AI-generated.

## Gate verdict
- [ ] **PASS / FAIL** with the milestone quality threshold and the evidence
      backing each box above.
