# AXIOM Agent Guide

How an LLM agent should use the AXIOM MCP tools. The founding axiom
applies to you: **you are not trusted without external verification.
You propose; the verifier disposes.**

## The three habits

1. **Search before invent.** Call `registry_search` before writing a
   unit. If a verified unit already does the job, call it by hash —
   never re-derive what is already attested.
2. **Verify before claim.** Nothing you compose exists until
   `verify_and_register` returns `ok: true`. Do not tell the user a
   unit "works" on the strength of your own confidence; the
   attestation hash is the claim.
3. **Audit after act.** `ledger_history(unit_hash)` shows everything
   a unit has ever done; `ledger_verify` proves nobody (including
   you) rewrote history.

## The tools

| Tool | Use it to | Returns on failure |
|---|---|---|
| `registry_search(name)` | Find existing verified units | `[]` |
| `unit_compose(...)` | Build a unit form with refs checked as you go | `{ok: false, errors: [...]}` |
| `verify_and_register(unit_form)` | The gate: attest or be rejected | `{ok: false, errors: [...]}` |
| `run(unit_hash, args, capabilities)` | Execute with postconditions enforced | `{ok: false, error: ...}` |
| `memory_observe(content, source_grade, contradicts?)` | Record observations | `{ok: false, error: "owner_required", ...}` |
| `memory_query(query, k)` | Routed recall | `[]` |
| `forge_run(units, probes)` | Hard-gated tournament over variants | raises on kill-switch |
| `ledger_history(unit_hash)` | One unit's full audit trail | `[]` |
| `ledger_verify()` | Prove the chain | `chain_valid: false` (alarm!) |

## The verify-rollback retry pattern

Errors are machine-readable so your retry converges. Map error → fix:

| Error | Meaning | Fix |
|---|---|---|
| `{check: "intent:EARS"}` | Intent isn't a well-formed EARS clause | Rewrite as `THE <system> SHALL <response>.` (or WHEN/WHILE/WHERE form, ending with a period) |
| `{check: "refs:resolve-or-fail", unresolved: H}` | You hallucinated a reference | `registry_search` for the real unit; use its hash. **Never** invent a hash |
| `{check: "contracts:z3", error: "contracts unsatisfiable"}` | Your contracts contradict each other | Re-read the intent; delete or fix the conflicting clause |
| `{check: "contracts:z3", error: "vacuous clause"}` | A contract is a tautology (`result == result`) | Write a clause that actually constrains the result |
| `{check: "effects:vocab"}` | Undeclared/unknown effect | Declare every effect from `db.read, db.write, fs.read, fs.write, net` (or `regulated:<x>`); cover your callees' effects |
| `{error: "postcondition", clause: C}` | Your body lies at runtime | The math is wrong. Fix the body until clause C holds on concrete values |
| `{error: "capability"}` | Caller didn't grant the declared effects | Ask the owner for the capability; do not strip the declaration |
| `{error: "owner_required"}` | You contradicted an entrenched belief | Stop. Surface the conflict to the owner verbatim; never overwrite |

Retry loop: compose → verify → on rejection, apply the mapped fix to
the *one* failing part → verify again. If the same error repeats 3
times, stop and report the raw error to the owner.

## What you cannot do (by construction)

- Register a unit without passing every check.
- Run a unit whose effects exceed granted capabilities.
- Get a result from a unit whose postcondition fails — you get a
  violation event instead.
- Win a tournament with a gate-failed candidate; its rating is 0 by law.
- Edit or erase history. The ledger is append-only and signed;
  `ledger_verify` is the court of record.
