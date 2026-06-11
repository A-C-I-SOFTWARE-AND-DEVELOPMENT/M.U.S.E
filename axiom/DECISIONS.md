# AXIOM — Architecture Decisions

## D1 — Kernel reconstructed from spec (Phase 0 deviation)
`AXIOM-kernel-v1.zip` was not present in the working directory; only
the Volume VII master-build document, the build-prompt PDF, and the
kernel's recovered test caches (hypothesis constant caches + pytest
node IDs) were available. Phase 0 was therefore *reconstruction*: the
20 invariant tests were rebuilt to the exact recovered node IDs, and
every module was rebuilt to the documented design, using the recovered
constant caches as ground truth for constants and vocabulary
(e.g. EARS regex `^THE .+? SHALL .+\.$`, Glicko-2 173.7178/350/0.06,
tier thresholds 7.0/60.0, gate weights 0.2/0.3/0.4/0.65/20.0).
The Glicko-2 implementation reproduces Glickman's published worked
example to 2 decimals (1464.05 / 151.52 / 0.06) on first run.
Smoke transcript shape matches the documented run; event count (5 vs 7)
and champion rating (1720 vs 1765) differ because duel count in the
reconstructed smoke differs — recorded here per the honesty rules.

## D2 — Call-argument binding order
Positional call arguments bind to callee params in **sorted name
order**, because canonical (hashed) form sorts keys — insertion order
must never carry meaning (I1: identity is the hash of canonical form).

## D3 — Vacuity as rejection
A tautological contract clause (negation UNSAT) is treated as a spec
error and rejects the unit, per the failure-mode matrix ("vacuous
specification"). Vacuity never merely warns.

## D4 — OwnerApproval never defaults open
In `run_gates`, a missing check passes by default for every gate
except OwnerApproval, which denies by default. Deny-by-default is the
only safe default for the owner gate.

## D5 — Registry deprecation landed with the registry
`Registry.deprecate` was included in the Phase 0 reconstruction
because the verifier's warning path needs the column; its behavior
tests land in Phase 1.3 per the ladder.
