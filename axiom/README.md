# AXIOM

*A verified-intelligence kernel. Intelligence proposes; the verifier
disposes.*

## The law

> **No intelligence — including the one that built this — is trusted
> without external verification.**

Three invariants no change may ever violate (the test suite is their
court):

- **I1 — Resolve or fail.** No unresolved reference ever executes.
  Identity is the blake3 hash of canonical form; names are metadata.
  A hallucinated reference is a hard error, never a guess.
- **I2 — Verify before attest.** Nothing earns an attestation without
  passing every check: EARS intent, resolved refs, Z3 contracts
  (satisfiable + consistent + non-vacuous), effect closure. At runtime,
  postconditions are enforced again on concrete values — a unit that
  lies at runtime yields **no result** and a violation event.
- **I3 — History is append-only and tamper-evident.** Every
  consequential act leaves an Ed25519-signed, hash-chained record.
  `verify_chain()` is the court of record; Merkle checkpoints give
  O(log n) inclusion proofs.

## Quickstart (9 commands)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python -m pytest tests/                  # the law, executable: all green
python smoke.py                          # the canonical first artifact
echo '{"name":"double","doc":"","params":{"x":"float"},"intent":"THE unit SHALL return two times x.","contracts":["result == x * 2.0"],"effects":[],"refs":{},"body":[{"op":"mul","in":["x",2.0],"into":"y"},{"op":"return","in":["y"]}]}' > double.json
axiom verify double.json                 # attest (prints the unit hash)
axiom run <unit_hash> --args '{"x": 21}' # 42.0, postcondition-enforced
axiom audit                              # chain_valid: true
python -m axiom.interface.mcp_server     # the agent surface (MCP, stdio)
```

## Architecture

```
L7 GOVERNANCE   trust scorecard · autonomy bands B0–B3 · sovereignty clauses
L6 EVOLUTION    Forge: Glicko-2 + matchmaking · MAP-Elites · kill-switch
L5 ORCHESTRATION HTN-lite w/ verifier nodes · 8 gates · risk-tiered auth
L4 INTERFACE    FastMCP tools · machine-readable errors · AGENT_GUIDE.md
L3 MEMORY       FSRS economy · AGM beliefs · routed retrieval · Mind facade
L2 SEMANTICS    EARS intent · Z3 contracts · declared effects     contracts.py/effects.py
L1 IDENTITY     blake3 content-addressed registry · resolve-or-fail   canonical.py/registry.py
L0 RECORD       hash-chained signed ledger · Merkle checkpoints      ledger.py
```

Canonical data flow: intent (EARS) → grounding (registry resolve) →
generation → **verification (the gate)** → attestation (ledger) →
execution (capability-gated, postcondition-enforced) → memory (FSRS
grade = verifier outcome) → evolution (Forge: hard-gated tournaments;
only verifier-passed trajectories are exported for distillation).

## What is demonstrated here, today

- Hallucinated references cannot attest (I1 tests).
- Contradictory and vacuous specs are caught before execution.
- A unit that lies at runtime returns nothing — only a violation event.
- Tampering with one byte of history is detected.
- A gate-failed candidate can never out-score a verified one,
  regardless of judges: its rating is 0 by law.
- A HIGH-risk change without the exact phrase
  `Yes, with authorization.` is provably never executed.
- A calibration regression (confident and wrong) auto-demotes the
  autonomy band, and the demotion is in the ledger.
- When the prover is unavailable, the kernel **fails closed**: a unit
  that declares contracts is rejected (`contracts:unverified`) rather
  than attested unproven — re-opening that path is an explicit,
  owner-gated opt-in (`AXIOM_ALLOW_UNVERIFIED_CONTRACTS=1`).

## Layout

```
axiom/core/          canonical, registry, contracts, effects, ledger, verifier
axiom/memory/        fsrs_memory, beliefs, retrieval, mind
axiom/forge/         ratings, matchmaking, archive, tournament, engine
axiom/orchestrator/  jobs, gates, htn, proposals
axiom/governance/    scorecard, bands, sovereignty
axiom/interface/     mcp_server
tests/               the law, executable
```

See [AGENT_GUIDE.md](AGENT_GUIDE.md) for how an LLM agent should use
the MCP tools (search before invent; verify before claim; the
verify-rollback retry pattern), [PROGRESS.md](PROGRESS.md) for the
build ladder with pasted gate outputs, and
[DECISIONS.md](DECISIONS.md) for the architecture decisions.

— *built by Claude, architect of AXIOM. The proof is not a claim;
it is a chain anyone can recompute.*
