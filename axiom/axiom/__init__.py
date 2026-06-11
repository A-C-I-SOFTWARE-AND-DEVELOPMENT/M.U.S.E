"""AXIOM — verified-intelligence kernel.

Founding axiom: no intelligence — including the one that built this —
is trusted without external verification. Intelligence proposes; the
verifier disposes.

Invariants:
  I1 — Resolve or fail: no unresolved reference ever executes.
  I2 — Verify before attest: nothing attests without passing every check;
       runtime postconditions are enforced on concrete values.
  I3 — History is append-only, Ed25519-signed, tamper-evident.
"""

__version__ = "1.0.0"
