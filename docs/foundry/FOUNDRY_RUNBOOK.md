# FOUNDRY RUNBOOK

How to mint a specialist (target state; steps marked [PROVEN] have real measured evidence,
[SCAFFOLD] are implemented and gate-tested with mocks, [PENDING] need their first real run).

1. **Pick a niche** — read `docs/foundry/NICHE_CENSUS.json`. Only NEEDLE_ROUTER_ONLY /
   NEEDLE_REFERENCE_FED / HYBRID niches proceed. [PROVEN: census over 137 specs]
2. **Eligibility record** — `foundry/eligibility.py` classification + evidence. [PROVEN]
3. **Schema** — author ≤5 macro-tools via `@tool` + `Field` (native dialect only). [PROVEN format]
4. **Executor contract** — declare name/schema/capabilities/preconditions/side-effects/allowed
   paths/limits/timeout/validation/rollback/evidence (§36). No contract, no training. [SCAFFOLD: QA validators]
5. **Dataset** — `foundry/teacher.py` plan → synthesis (or human seeds) → `foundry/dataset.py`
   validation/dedupe/partition. Mandatory classes: positive, paraphrase, boundary,
   missing-evidence, under-specified, off-topic, adjacent-domain, adversarial-ambiguity,
   conflicting, malformed (§17). ≥15% negatives. [PROVEN engine; ladder unproven at scale]
6. **Learning curve** — 250/500/1000/2000/4000 subsets; stop at flat validation gain (§18). [PENDING]
7. **Train** — TRAINING_RUNBOOK pins; f32-LoRA patch mandatory; engine 2.0.0 for tuned artifacts. [PROVEN on 26-ex probe]
8. **Evaluate** — `foundry/evaluation.py` over EVAL_STANDARD/HARD/ADVERSARIAL vs stock baseline,
   same engine. [PROVEN harness; gates enforced]
9. **Decision** — gates fail → kill-switch ladder (§90): schema fix / dataset fix / merge tools /
   split tools / reference-feed / stock model / deterministic parser / local general / provider /
   retire. Recorded in the belief ledger. [PROVEN: NEEDLE-QA probe correctly held at gate]
10. **Register** — `foundry/registry.py` record with full hash lineage; lifecycle CANDIDATE→…→ACTIVE
    only through §43 promotion gates incl. shadow + canary. [SCAFFOLD]
11. **Attest** — AXIOM promotion attestation linking niche, dataset, base, adapter, model, eval,
    thresholds, executor, schema (§72). [PENDING: AXIOM adapter]
12. **Operate** — shadow → canary → active; failure clustering feeds the active-learning loop (§61);
    rollback via `known_good()` (§44). [SCAFFOLD]

## Zero-manual proof obligation (§65)

Phase 7 requires minting one census niche end-to-end with no manual dataset engineering.
Current honest state: steps 1–5 and 7–9 have proven components; the fully-automatic chain
(synthesis at scale → train → gate decision → register) has not yet run unattended.

## Demos executed (2026-08-12)

- **§86 E2E**: `python foundry/e2e_demo.py` → PASS. NL brief → stock Needle spec → gate →
  real Blender 5.2 headless build (exit 0) → FBX validation → QA gate → AXIOM attestation
  (valid chain) → registry. Transcript: `docs/foundry/E2E_DEMO_TRANSCRIPT.json`.
- **§87 failure containment**: `python foundry/failure_demo.py` → ALL EXPECTATIONS MET.
  All five failure classes contained with ledger evidence. Transcript:
  `docs/foundry/FAILURE_DEMO_TRANSCRIPT.json`.

## Runtime learning (§45/§61)

`foundry/shadow.py` — shadow capture with secret scrubbing, live-domain estimates,
failure clustering, retrain proposals (data, not authority). Tested; hook into the
M.U.S.E. router to start collecting EVAL_RUNTIME_SHADOW traffic.

## Performance baseline (§96, measured on this laptop)

Cold start ~0.6s total (weight load 0.01s, schema init 0.36s, first call 0.26s).
Warm requests: p50 0.21s, p95 0.25s, mean 0.17s, n=12. Peak RAM ~107MB.
Full data: `docs/foundry/NEEDLE_PERFORMANCE.json`. Tier-0 latency budget is real.
