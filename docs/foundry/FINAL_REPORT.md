# FOUNDRY FINAL REPORT

**Date:** 2026-08-12 · **Scope executed:** Phase 0 (Reality), Phase 1 (Needle Ground Truth),
Phase 2 (Capability Architecture), Phase 3-miniature (first specialist probe), Phase 6 (Niche Census).
Phases 4/5/7/8 have proven components and honest pending items (below).

## What shipped (VERIFIED)

**Investigation & ground truth**
- Repository/provider/AXIOM/niche/hardware audit: `PHASE0_REALITY.md`, `PHASE0_PROVIDER_INVENTORY.json`.
- Needle 2 pinned end-to-end: source v2.0.1 (abb5c2b…), HF revision 07f3e789…, sha256 for every
  artifact (`NEEDLE_HASHES.json`). Upstream drift caught and handled during the session.
- License resolved: weights Apache-2.0 + package MIT — both permissive, notice-retention required. Not blocked.
- `NEEDLE_GROUND_TRUTH.md` — 10 sections, every claim marked VERIFIED_LOCAL / VERIFIED_UPSTREAM / MEASURED.

**Three upstream-impacting defects found, measured, and worked around**
1. **f16 AdamW NaN** — released checkpoint is float16; stock `init_lora` inherits f16, optimizer
   eps underflows → 100% NaN after one update at any LR. Root-caused through five controlled
   experiments (forward-only, per-example, batched, eager-vs-jit, direct-perturbation). Fixed in the
   vendored copy (f32 LoRA). 3-epoch probe then trained cleanly (12/12 finite steps).
2. **Container/engine skew** — pinned exporter writes 0x82 `.cact`; HF engine 2.0.1 only loads 0x83.
   Pairing rule established: tuned artifacts ↔ engine 2.0.0.
3. **Schema dialect** — raw JSON-Schema `"arguments"` breaks the decode grammar (arg accuracy 0.000);
   native `build_schema`/`Field` `"parameters"` dialect restores it (1.000). Documented as mandatory.

**Foundry scaffolding (`foundry/` package, all gate-tested)**
- `eligibility.py` — census over all 137 niches: 80 LOCAL_GENERAL, 34 NEEDLE_REFERENCE_FED,
  9 PROVIDER_GENERAL, 6 NEEDLE_ROUTER_ONLY, 6 HUMAN_GATED, 2 HYBRID.
- `runtime_gate.py` — fail-closed Tier-0 gate, 6/6 mock scenarios correct.
- `registry.py` — content-addressed lineage + lifecycle + rollback lookup.
- `beliefs.py` — belief ledger with automatic REFUTED→reopen. 12 claims tracked (2 REFUTED).
- `teacher.py` — provider discovery from the real catalog; zero-cost local teacher plan ready.
- `dataset.py` — provenance/validation/dedupe/cluster-safe partition (dupes + unknown tools quarantined in test).
- `evaluation.py` — §21 metrics + §22 gates; planted failures correctly detected.
- `executors/qa/validators.py` — 8 deterministic QA validators + profile gate (smoke-tested).

**First specialist probe (NEEDLE-QA) — honest result: DOES NOT SHIP**
- Stock vs 26-example-tuned, engine-matched, native dialect, n=10 held-out: identical metrics;
  exact-call 0.50 (gate 0.90), refusal recall 0.60 (gate 0.95), wrong-domain 0.40 (gate 0.00),
  argument accuracy 1.00 (gate 0.95), schema validity 1.00 (gate 1.00).
- The gate held. 26 examples is a pipeline probe, not a training set — the learning-curve ladder
  (250→4000) is the next real experiment, not a formality.

## What was killed / rejected (with evidence)

| Candidate | Verdict | Evidence |
|---|---|---|
| Switchyard in runtime path | REJECTED (borrow stage-routing concept only) | `SWITCHYARD_GAP_ANALYSIS.md` — M.U.S.E. routing already superior; pre-alpha risk |
| Confidence-head gating | REFUTED pending calibration study | correct calls scored 0.001–0.03 while spurious scored 0.08–0.25 — inverted overlap |
| Stock lr=1e-4/1e-5 convergence | REFUTED (f16 bug) | NaN probes |
| "26 examples is enough" | REFUTED | tuned == stock on held-out |
| NEEDLE-QA v0.0.1 | KILLED AT GATE | metrics above |

## Remaining work (no follow-ups hidden — explicit list)

1. Dataset ladder for NEEDLE-QA (250→4000) via teacher plan; re-eval. **Blocker-free — WSL2 GPU path verified (62s/epoch), ~an hour per ladder rung.**
2. ~~WSL2 CUDA-JAX probe~~ **DONE — VERIFIED**: JAX 0.11.0 cuda12 in WSL2 sees `CudaDevice(0)` (RTX 5070); 26-example epoch in 62s vs 295s Windows CPU, finite losses. `NEEDLE_COMPUTE_PATH.json`.
3. Blender/FBX executors with staging + provenance (§37/§38) — **DONE**: `foundry/executors/blender` + `foundry/executors/fbx`, capability + path-safety proven, real Blender 5.2 headless build executed in the E2E demo.
4. AXIOM attestation adapter for model promotion (§72) — **DONE**: `foundry/axiom_adapter.py`, verified through the real Verifier + signed ledger; §73 tamper probes all pass (see SECURITY_MODEL.md table).
5. EVAL_RUNTIME_SHADOW capture wiring — **SCAFFOLD DONE**: `foundry/shadow.py` (shadow capture, secret scrub, failure clustering, retrain proposals) tested; needs live traffic hookup.
6. Confidence reliability curves before any confidence gating.
7. Upstream the f32-LoRA patch to cactus-compute/needle.
8. Phase 7 zero-manual mint proof once 1 lands.
9. NEEDLE-ERA: reference-fed extraction mechanically works but is below gate on stock — train or kill after the dataset ladder (§13 S6 policy holds).

## Late-session measured additions (2026-08-12)

- **E2E demo (§86): PASS** — NL brief → stock Needle spec extraction → runtime gate → real Blender 5.2 headless build (exit 0, 15.2s) → FBX validation (16.7KB artifact) → deterministic QA gate pass → AXIOM attestation with valid chain → registry entry. Transcript: `E2E_DEMO_TRANSCRIPT.json`.
- **Failure demo (§87): ALL EXPECTATIONS MET** — off-topic→escalate, under-specified→escalate, adjacent-domain→escalate, malformed→escalate, invalid-executor-output→verification rejection + quarantine + known-good rollback, all with ledger evidence. Transcript: `FAILURE_DEMO_TRANSCRIPT.json`.
- **Quantization (§82)**: 2-bit mixed == 4-bit on quality, 2× faster (0.23s vs 0.45s mean), 40% smaller. Choose 2-bit. `NEEDLE_QUANTIZATION.json`.
- **Tokenization (§83)**: game-dev vocab avg 2.83 tokens/term; no accuracy harm measured. `NEEDLE_TOKENIZATION.json`.
- **Tool retrieval (§23)**: top-5 ceiling measured (8th tool unreachable) — macro-tool rule is mandatory, not advisory.
- **Test suite**: `tests/foundry/test_foundry.py` — 23/23 pass (all foundry modules + AXIOM adapter + tamper evidence).

## Artifacts index

`docs/foundry/`: PHASE0_REALITY.md, PHASE0_REALITY_SNAPSHOT.json, PHASE0_PROVIDER_INVENTORY.json,
NEEDLE_GROUND_TRUTH.md, NEEDLE_HASHES.json, NEEDLE_FINETUNE_PROBE.json, NEEDLE_STOCK_VS_TUNED.json,
NICHE_CENSUS.{json,md}, SWITCHYARD_GAP_ANALYSIS.md, ARCHITECTURE.md, SECURITY_MODEL.md,
TRAINING_RUNBOOK.md, EVALUATION_POLICY.md, PROVIDER_POLICY.md, FOUNDRY_RUNBOOK.md, belief_ledger.json.
`foundry/`: 8 modules. `third_party/needle/`: vendored, patched, pinned.

**Measured, not claimed. Gates held. The refusal to ship a weak specialist is the system working.**
