# p2 — Auto-apply driver: STATUS

**Module:** `hermes_cli/jarvis_prime/research_fabric/auto_apply.py`

## What works end-to-end (verified 2026-07-20)

* Candidate JSON loads -> `Candidate` dataclass.
* Autonomy branch `autonomy/<candidate_id>` is created/checked out (never the caller's branch).
* `SnapshotStore`, `GuardrailLedger`, `ChampionStore`, `ProposalBook`, `CharterBook` (seeded with a 1-hour auto-charter), `AlignmentMonitor` all construct against repo-local state under `.hermes/research_fabric/`.
* `AutonomyController.evaluate_and_apply(...)` runs the full pipeline: monitor -> hard-wall -> ratchet -> 8 strict gates -> capability -> charter scope+budget -> dry-run/apply/canary/rollback.
* Ratchet correctly evaluates per-domain non-regression, cold-start floor (0.80), holdout floor, safety counts, eval win-rate.
* Strict gates correctly **block** when the packet lacks real evidence (planning fields, git_diff artifact, review artifact, executed test evidence, release packet, rollback evidence). This is the intended fail-closed behavior.
* Corpus record is written to `.hermes/research_fabric/corpus/<ts>-<id>.json` regardless of decision, capturing candidate + outcome + branch + HEAD sha.

## What remains (p3 territory)

* A real evidence-bundle-producing benchmark harness that runs the catalog verifiers, captures planning/build/review/test/release/rollback artifacts into a `GuardrailEvidenceBundle`, and feeds the bundle into `drive_candidate`. Only then will gates 1-8 actually PASS and the applier + canary + rollback path be exercised live.
* Replace the `_default_canary` (which just re-reads candidate domain_scores) with a canary that re-invokes the catalog verifiers and detects a real post-apply regression.
* Add a fixture-based test under `tests/jarvis_prime/research_fabric/test_auto_apply.py` that exercises: (a) gate-blocked path with empty bundle (already proven manually), (b) full apply path with a mocked `gate_runner` returning PASS, asserting branch + commit + corpus + champion freeze all land.

## Smoke test (manual, 2026-07-20)

```
python -m hermes_cli.jarvis_prime.research_fabric.auto_apply \
  --repo . \
  --candidate .hermes/research_fabric/smoke/candidate.json \
  --packet   .hermes/research_fabric/smoke/packet.json \
  --dry-run
```

Outcome: `decision=blocked, ratchet.passed=true, gate_overall=fail` — exactly the expected cold-start fail-closed behavior with an empty evidence bundle.
