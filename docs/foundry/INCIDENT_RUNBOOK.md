# INCIDENT RUNBOOK

Severity-one conditions (§79) and the exact response path.

## Severity-one triggers

- verification escape (§48 definition)
- unauthorized effect executed
- corrupted artifact accepted into the registry
- AXIOM signature bypass or ledger tamper going undetected
- data leakage into training data / provenance / logs
- specialist repeatedly routing to a destructive tool

## Response sequence

1. **QUARANTINE** — `record.transition("QUARANTINED", reason)` in `foundry/registry.py`.
   The runtime gate never routes to non-ACTIVE specialists, so quarantine alone stops traffic.
2. **STOP the affected capability** — remove the capability grant from the gate's
   `capability_authorized` map entry for that specialist.
3. **PRESERVE EVIDENCE** — do not delete checkpoints, datasets, eval outputs, or ledger files.
   Hash everything touched (`foundry.registry.sha256_file`) before any further action.
4. **ROLLBACK** — `registry.known_good(specialist_id)` → transition to ACTIVE. Never fix-forward
   while bad behavior is live (§44).
5. **BLAST RADIUS** — query the ledger for every event carrying the bad artifact hash;
   enumerate effected executions.
6. **REPRODUCE** — add the failing input to EVAL_ADVERSARIAL *and* the historical regression
   suite (§62) before any retrain.
7. **FIX** — kill-switch ladder (§90): schema → dataset → tool merge/split → reference-feed →
   stock model → deterministic parser → local general → provider → retire.
8. **REGRESSION-TEST** — original eval + current eval + historical failure suite +
   adjacent-domain + refusal suite + executor compatibility. All six, no exceptions.
9. **RE-PROMOTE** only through the full §43 gate chain, including shadow and canary.

## Ledger forensics

AXIOM ledger tamper evidence (measured §73 table in SECURITY_MODEL.md): payload, prev-link,
and signature tampering all flip `verify_chain()` to False. If the chain verifies, the ledger
you are reading is the ledger that was written.

## Contact/authority

Only the owner may: rotate keys, publish artifacts externally, change promotion thresholds,
or disable any gate. Everything else in this runbook is pre-authorized reversible action.
