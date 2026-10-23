# FOUNDRY ARCHITECTURE (Phase 2)

**Status:** interfaces implemented and gate-tested with mocks/deterministic examples (2026-08-12).

## Modules (`foundry/`, additive — no changes to M.U.S.E. core)

| Module | Directive § | Purpose |
|---|---|---|
| `foundry/eligibility.py` | §11 | Niche Eligibility Compiler: parse → normalize → validate → classify → score → explain. Emits `docs/foundry/NICHE_CENSUS.{json,md}` |
| `foundry/registry.py` | §41–44 | Content-addressed specialist artifact registry with lifecycle states and known-good rollback lookup |
| `foundry/beliefs.py` | §50 | Belief ledger; REFUTED claims automatically reopen dependents |
| `foundry/teacher.py` | §14–16 | Capability-aware teacher discovery from the *actual* `config/model-catalog.yaml`; no hard-coded providers; credential-free provenance |
| `foundry/runtime_gate.py` | §47 | Fail-closed Tier-0 proposal gate: empty→escalate, low-conf→escalate, schema→escalate, capability→reject, preflight→escalate |
| `foundry/dataset.py` | §16–19 | Dataset engine: provenance, schema validation, exact/normalized dedupe, paraphrase-cluster-safe train/eval partition |
| `foundry/evaluation.py` | §21–22 | Metric suite + acceptance gates (exact-call, argument accuracy, refusal P/R, optional-field hallucination, wrong-domain execution, schema validity) |
| `foundry/executors/qa/validators.py` | §36, §39 | Deterministic QA validators (polycount, n-gons, manifold, degenerate, materials, UV overlap, transforms, naming) + profile-based asset gate |

## Verified at gate time

- Eligibility census over all **137** niche specs:
  LOCAL_GENERAL_MODEL 80 · NEEDLE_REFERENCE_FED 34 · PROVIDER_GENERAL_MODEL 9 ·
  NEEDLE_ROUTER_ONLY 6 · HUMAN_GATED 6 · HYBRID 2
  (deterministic heuristic; per-niche promotion still requires Phase-3 measured gates)
- Runtime gate: 6/6 mock scenarios behave fail-closed.
- Registry: lifecycle transitions + content addressing work; rollback lookup returns known-good.
- Belief ledger: REFUTED → dependent reopen verified by self-test.
- Dataset engine: quarantines exact dupes and unknown-tool rows; cluster-leakage-free partition.
- Evaluation harness: planted metric failures correctly fail their gates.
- Teacher discovery: 40 catalog models → 14 currently env-available; multi-teacher plan fills all roles from local lane (zero-cost).

## Trust boundary (unchanged, §8/§112)

Needle proposes → `runtime_gate` decides → `executors/*` act → deterministic validators
verify → AXIOM attests. No module in `foundry/` can bypass a later stage; each stage can
only narrow.
