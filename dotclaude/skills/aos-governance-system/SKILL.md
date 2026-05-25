---
name: aos-governance-system
description: Design or audit an autonomous operating system — agent boundaries, memory layers, confidence/escalation, audit trails, validation gates. Use when designing a multi-agent system, extending an existing one, or auditing it against honest-autonomy criteria.
---

# AOS Governance System

## Use when

- Designing a new multi-agent system.
- Adding or removing an agent in an existing system.
- Auditing a system before any "autonomous" public claim.

## Design checklist (every item is required)

1. **Boundary** — Each agent has a written input contract and output
   contract (types, required fields, error shape).
2. **Escalation** — Each agent has a named condition under which it stops
   and asks the owner.
3. **Memory model** — Scope (turn / session / durable / shared), expiry,
   eviction policy.
4. **Validation gate** — Between any two steps, an executable check (not a
   self-report) decides whether to proceed.
5. **Audit trail** — Every action logs actor, input hash, output hash, tool
   calls, validation result, timestamp.
6. **No silent fallback** — Missing specialist → "not run", not fabrication.
7. **No self-grading** — Verifier is a different session than the actor.
8. **Reproducibility** — Same input + same memory → same audit trail
   (modulo declared non-determinism).
9. **Failure modes named** — At least five realistic failures with the
   guard for each.
10. **Honesty floor** — When the loop fails, the system says so to the
    owner; it does not paper over the failure.

## Audit pass

For an existing system, walk each checklist item and mark PASS / FAIL / N-A
with evidence (file:line or log excerpt). Any FAIL on items 1, 4, 5, 6, or 7
blocks the "autonomous" claim.

## Output

```
## System
## Purpose (one sentence)
## Agent table (name, contract, escalation, memory scope)
## Operating loop (perceive / reason / decide / act / verify / remember)
## Memory model
## Validation gates
## Audit trail schema
## Failure modes & guards
## Honesty floor
## Open questions for the owner
```
