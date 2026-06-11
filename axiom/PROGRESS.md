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
- [ ] 1.1 Body interpreter ops: min, max, abs, if (select), eq/lt → bools
- [ ] 1.2 Recursion/cycle guard at verify time → Rejection("cycle")
- [ ] 1.3 Registry deprecation: old hash resolves, verifier warns
- [ ] 1.4 Ledger compaction: summarize pre-checkpoint events, root still verifies
- [ ] EXIT GATE: full suite green (~30+), smoke.py unchanged output

## Phase 2 — Memory plane live
- [ ] 2.1 Mind facade: observe / recall / on_verification
- [ ] 2.2 Contradiction → OwnerRequired + contradiction_report ledger event
- [ ] 2.3 Disk persistence; restart preserves tiers/beliefs/retrievability
- [ ] EXIT GATE: simulated mid-session kill, reopen, nothing lost, chain valid

## Phase 3 — Forge engine
- [ ] 3.1 Persist ratings + archive to SQLite; RD inflates for idle candidates
- [ ] 3.2 Tournament over 4 real unit variants; cheat dies at runtime gate
- [ ] 3.3 Kill-switch anomaly test: halt + ledger alarm
- [ ] 3.4 Trajectory export: trajectories.jsonl / negatives.jsonl
- [ ] EXIT GATE: two consecutive runs share ratings; champion lineage from ledger

## Phase 4 — Agent surface
- [ ] 4.1 MCP tools: memory_query, memory_observe, forge_run, ledger_history, unit_compose
- [ ] 4.2 In-process fastmcp client test for every tool
- [ ] 4.3 AGENT_GUIDE.md
- [ ] EXIT GATE: scripted agent session end-to-end through MCP tools only

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
