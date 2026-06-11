# AXIOM — Build Progress

Protocol: read this file first every iteration. Plan → test-first →
build → full suite → commit → log. Never claim green without real
output.

## Phase 0 — Kernel baseline
- [x] Reconstruct kernel from Volume VII spec + recovered cache evidence
      (AXIOM-kernel-v1.zip was not available — see DECISIONS.md D1)
- [x] All locked deps installed (blake3 1.0.8, z3-solver 4.16, pynacl 1.6.2,
      fsrs 6.3.1, hypothesis 6.155.2, pytest 9.0.3, fastmcp 3.4.2)
- [x] Baseline gate: `python -m pytest tests/ -q` → **20 passed in 1.54s**
- [x] Smoke transcript:
      ```
      [1] attested  unit=1b6eb6cab462…  checks=['intent:EARS', 'effects:vocab', 'refs:resolve-or-fail', 'contracts:z3']
      [2] run(100C) = 212.0F
      [3] forge: champion=v2 (1720), gate-failed=['cheat'] (rating 0)
      [4] memory 1 tier=working  R=1.00
      [5] ledger: 5 events, chain_valid=True
      ```
- [x] Committed: Phase 0 baseline

## Phase 1 — Harden the kernel
- [x] 1.1 Body interpreter ops: min, max, abs, if (select), eq/lt → bools
      (tests: test_op_min_max, test_op_abs, test_op_if_select_and_comparisons,
      test_op_eq_produces_bool — contracts proven over each)
- [x] 1.2 Recursion/cycle guard at verify time → Rejection("cycle")
      (honest cycles unconstructible under content addressing; test forges
      one via simulated registry corruption — see DECISIONS.md D6)
- [x] 1.3 Registry deprecation: old hash resolves, verifier warns
- [x] 1.4 Ledger compaction: summarize pre-checkpoint events, root still
      verifies; post-checkpoint events untouched
- [x] EXIT GATE: `python -m pytest tests/` → **28 passed in 0.30s**;
      smoke.py output unchanged from Phase 0

## Phase 2 — Memory plane live
- [x] 2.1 Mind facade (`axiom/memory/mind.py`): observe / believe / recall /
      on_verification, wiring MemoryStore + BeliefBase + routed retrieval
- [x] 2.2 Contradiction → contradiction_report ledgered, then OwnerRequired
      raised; entrenched belief untouched; weak beliefs revised with lineage
- [x] 2.3 Disk persistence (data dir per Mind); restart preserves tier,
      content, beliefs, and FSRS retrievability to 1e-9
- [x] EXIT GATE: simulated mid-session kill (drop all objects, reopen) —
      nothing lost, chain valid. `pytest tests/` → **33 passed in 0.63s**;
      smoke unchanged

## Phase 3 — Forge engine
- [x] 3.1 RatingStore (SQLite): ratings persist; idle candidates' RD
      inflates per the empty-period rule, capped at the default 350
- [x] 3.2 ForgeEngine tournament over 4 real unit variants of one spec;
      hard gate = Verifier.verify + runtime probes; cheat (c+32, statically
      clean) eliminated by the runtime postcondition, not judges; shortest
      verified unit (v_short, 3 ops) is champion
- [x] 3.3 Kill-switch: seeded 5000-rating anomaly → halt + forge_kill_switch
      ledger alarm; ratings earned before the halt still persist
- [x] 3.4 Trajectory export: verifier-passed → trajectories.jsonl,
      failures → negatives.jsonl, every record anchored to a unit hash
- [x] EXIT GATE: two consecutive runs share persistent ratings; champion
      lineage reconstructed from ledger events alone (forge_champion +
      forge_duel). `pytest tests/` → **39 passed in 1.71s**; smoke unchanged

## Phase 4 — Agent surface
- [x] 4.1 Nine MCP tools: registry_search, verify_and_register, run,
      ledger_verify, memory_observe, memory_query, forge_run,
      ledger_history, unit_compose (refs/EARS/contracts checked as you
      compose) — all errors machine-readable (owner_required,
      unresolved, postcondition, capability)
- [x] 4.2 In-process fastmcp Client exercises every tool + asserts all
      nine publish input schemas (no manual testing)
- [x] 4.3 AGENT_GUIDE.md: search-before-invent, verify-before-claim,
      the verify-rollback retry pattern with error→fix mapping
- [x] EXIT GATE: scripted agent session (test_scripted_agent_session_end_to_end)
      composes a NEW unit calling a registered unit, verifies, runs
      (12.0 from quadruple(3)), audits chain — MCP tools only.
      `pytest tests/` → **47 passed in 3.28s**; smoke unchanged
      (iteration-5 anchor: smoke re-run, LAW re-read)

## Phase 5 — Orchestration with gates
- [x] 5.1 HTN-lite (`orchestrator/htn.py`): Task trees where every
      decomposition node MUST carry a verifier task (rejected at
      construction otherwise); leaves run through JobStore — replaying a
      plan re-runs nothing (exactly-once proven)
- [x] 5.2 propose_change flow (`orchestrator/proposals.py`): blast-radius
      profile selects the gate set; every gate result ledgered, fail-fast;
      OwnerApproval never defaults open
- [x] 5.3 Risk-tiered auth: silent (LOW) / lightweight callback (MED) /
      ceremonial exact-phrase "Yes, with authorization." (HIGH)
- [x] EXIT GATE: HIGH change tried with None, True, "yes", and three
      near-miss phrasings — plan body never ran, 6 change_denied events
      ledgered, chain valid. `pytest tests/` → **55 passed in 4.46s**;
      smoke unchanged

## Phase 6 — Trust scorecard and autonomy bands
- [x] 6.1 TrustScorecard (`governance/scorecard.py`): per-capability
      prediction accuracy, promise-keeping, Brier calibration, rolling
      windows; no evidence = worst-case Brier by design
- [x] 6.2 BandManager (`governance/bands.py`): B0–B3; promotion needs a
      full 20-sample window (acc ≥ .8, Brier ≤ .15, promises ≥ .9);
      ONE high-severity gate failure demotes immediately; every
      transition ledgered as band_transition
- [x] 6.3 Sovereignty (`governance/sovereignty.py`): interruption stub,
      why-attached-to-decisions, oracle check (confidence > 0.8 without
      attestation ref = violation) — all with coverage counters
- [x] EXIT GATE: seeded calibration regression (20× confident-and-wrong)
      auto-demotes B1→B0, reason recorded, chain valid.
      `pytest tests/` → **61 passed in 3.16s**; smoke unchanged

## Phase 7 — Ship it
- [x] 7.1 README.md: the law, 9-command quickstart, ASCII layer diagram
- [x] 7.2 `python -m axiom` CLI: verify / run / audit / forge /
      mind observe / mind recall — JSON out, exit 0 = verified truth,
      exit 1 = machine-readable refusal (5 CLI tests, in-process)
- [x] 7.3 pyproject.toml (axiom-kernel 1.0.0); `pip install -e .` works;
      `axiom` console script installed and answering
- [x] 7.4 Final audit (real output pasted below)
- [x] DEFINITION OF DONE: all boxes checked

## BLOCKED
(none)

## CLOSING ENTRY — AXIOM 1.0.0

Final full suite:
```
$ python -m pytest tests/ --timeout 60
66 passed, 1 warning in 3.54s
```
Final smoke (unchanged through every phase):
```
[1] attested  unit=1b6eb6cab462…  checks=['intent:EARS', 'effects:vocab', 'refs:resolve-or-fail', 'contracts:z3']
[2] run(100C) = 212.0F
[3] forge: champion=v2 (1720), gate-failed=['cheat'] (rating 0)
[4] memory 1 tier=working  R=1.00
[5] ledger: 5 events, chain_valid=True
```
Final CLI audit over a fresh end-to-end session (verify → run → audit):
```
$ axiom run <hash> --args '{"x": 21}'
{ "ok": true, "result": 42.0 }
$ axiom audit
{ "chain_valid": true, "events": 2 }
```
**66 tests green. chain_valid=True.** Phase ladder complete:
kernel (20) → hardening (28) → memory plane (33) → forge engine (39)
→ agent surface (47) → orchestration gates (55) → trust bands (61)
→ shipped (66). The proof is not a claim; it is a chain anyone can
recompute.
