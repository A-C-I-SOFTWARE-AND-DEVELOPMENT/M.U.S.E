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
- [ ] 5.1 HTN-lite Task tree with verifier tasks; exactly-once leaves
- [ ] 5.2 propose_change flow: blast-radius profile; HIGH needs owner callback
- [ ] 5.3 Risk-tiered auth: silent / lightweight / ceremonial ("Yes, with authorization.")
- [ ] EXIT GATE: HIGH change without the phrase provably never executes; denial ledgered

## Phase 6 — Trust scorecard and autonomy bands
- [ ] 6.1 Per-capability stats: accuracy, promise-keeping, Brier calibration
- [ ] 6.2 Bands B0–B3; one high-severity gate failure demotes immediately
- [ ] 6.3 Sovereignty clauses: three anti-goal counters
- [ ] EXIT GATE: seeded calibration regression auto-demotes a band

## Phase 7 — Ship it
- [ ] 7.1 README.md: quickstart, ASCII architecture, the law
- [ ] 7.2 `python -m axiom` CLI: verify / run / audit / forge / mind recall
- [ ] 7.3 pyproject.toml; `pip install -e .`; version 1.0.0
- [ ] 7.4 Final audit: 60+ green, smoke, full-chain audit
- [ ] DEFINITION OF DONE: all boxes checked, final commit "AXIOM 1.0.0 — all
      phases verified", closing entry with final test count + chain_valid=True

## BLOCKED
(none)
