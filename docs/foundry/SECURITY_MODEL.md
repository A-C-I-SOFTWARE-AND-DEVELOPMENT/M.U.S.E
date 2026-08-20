# FOUNDRY SECURITY MODEL

**Date:** 2026-08-12 · **Status:** interface-verified; AXIOM deep-revalidation pending (§73)

## Trust boundaries enforced by construction

1. **No model has effect authority.** Needle emits a JSON proposal; `foundry/runtime_gate.py`
   is the only path to an executor. The gate is ordered so no stage can widen a later stage:
   - empty call → escalate
   - confidence < review_threshold → escalate
   - schema-invalid → escalate
   - capability denied → **reject** (hard stop)
   - executor preflight fail → escalate
   - confidence < accept_threshold → escalate
2. **Executors are narrow.** `foundry/executors/qa/validators.py` takes an asset *manifest*,
   not live Blender/Python access. A future Blender executor must declare: input schema,
   required capabilities, preconditions, side effects, allowed paths, resource limits,
   timeout, validation, rollback, evidence output (§36). No executor ships without that block.
3. **The model never judges quality.** Validators are deterministic; NEEDLE-QA only routes (§39).
4. **Verification escape = severity-one** (§48). Definition: a materially incorrect or
   unauthorized proposal causes an external effect the safety layer should have blocked.
   Release target: 0.00. Any occurrence → quarantine + rollback (§79).
5. **Promotion is multi-gate** (§43): artifact integrity → schema compilation → eval pass →
   adversarial pass → executor compatibility → AXIOM policy pass → shadow → canary → ACTIVE.
   The registry (`foundry/registry.py`) records every transition; `known_good()` supports
   instant rollback.
6. **Self-modification limit** (§91): nothing in `foundry/` may weaken capability
   authorization, verification, provenance, secret handling, rollback, promotion gates, or
   ledger integrity. These modules carry no config flag that disables a gate.
7. **Secrets**: teacher provenance stores provider/model IDs only (§16, §56). Dataset
   construction redacts before storage (enforced at dataset-engine ingestion point).

## License posture (Needle 2)

- Weights/engine: Apache-2.0 (HF model card, pinned revision 07f3e789…).
- Python package: MIT (repo LICENSE, pinned commit abb5c2b7…).
- Both permissive; derivatives allowed with notice retention. Vendored copy at
  `third_party/needle` carries both LICENSE texts. Not blocked for internal training/eval.

## Known-open items (honest list)

- AXIOM-native attestation of model promotion (§72): adapter implemented in
  `foundry/axiom_adapter.py` and verified — promotion Unit passes the real Verifier
  (intent:EARS, effects:vocab, refs:resolve-or-fail), lineage recorded as signed ledger
  event. `contracts:degraded` noted (z3 not installed; promotion Units carry no contracts,
  so nothing is attested unproven — the fail-closed path is respected).
- Confidence-head gating is **not** used anywhere yet: probe showed no separation
  (belief `needle.confidence_gates` = REFUTED pending reliability-curve study, §24).
- The stock Needle training script ships an f16-optimizer NaN bug; our vendored copy carries
  the f32-LoRA fix. Any upstream re-pull must re-apply or up-stream the patch.

## AXIOM security revalidation (§73) — MEASURED 2026-08-12

| Probe | Result |
|---|---|
| signature verification (registered unit) | verifies ✓ |
| unknown unit hash | raises `UnresolvedReferenceError` (fail-closed, no silent False) ✓ |
| malformed EARS intent | rejected at `intent:EARS` ✓ |
| out-of-vocabulary effect (`fs.delete_all`) | rejected at `effects:vocab` ✓ |
| unresolved reference | rejected at `refs:resolve-or-fail` ✓ |
| SQL-level payload tamper | `verify_chain()` → False ✓ |
| prev-link tamper | `verify_chain()` → False ✓ |
| signature tamper | `verify_chain()` → False ✓ |
| clean chain | `verify_chain()` → True ✓ |
| z3 contracts | NOT PROVEN — z3-solver not installed; units declaring contracts are fail-closed rejected unless owner opts into degraded mode (correct posture) |
