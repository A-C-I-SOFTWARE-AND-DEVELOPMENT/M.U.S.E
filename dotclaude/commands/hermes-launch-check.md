---
description: Validate whether the current repo is launch-ready
---

# /hermes-launch-check

## Purpose

Decide, with evidence, whether the current branch is ready to ship to
production / the stores / the demo. Produces a gate report and a single
next action.

## When to use

- Before any go-live, store submission, marketing push, or demo.
- Before any external claim of "ready" / "launched" / "v1".

## Agents activated

1. `repo-context-librarian` (first)
2. `qa-launch-validator` (mandatory)
3. `security-privacy-risk-officer` (mandatory)
4. `mobile-release-engineer` (mandatory if any mobile target exists)
5. `ux-polish-product-designer` (mandatory if user-facing UI exists)
6. `hermes-final-synthesizer` (last)

Skill invoked: `hermes-launch-audit`.

## Required workflow

1. Mission brief: target environment (staging / production / store), date
   if known, and what counts as launched.
2. Repo map.
3. Run the gate set (install, typecheck, lint, tests, build, smoke,
   deployment, mobile/store if applicable, monitoring, copy & polish,
   owner-only items).
4. Each gate is GREEN / RED / N-A with evidence.
5. Synthesizer assembles the verdict and the single next action.

## Required output format

```
## Branch / commit
## Target environment
## Gate results
| Gate | Result | Evidence |
| --- | --- | --- |
...
## Code-side blockers (RED gates Claude can fix)
## Owner-only blockers (Play Console, App Store, Vercel, DNS, Stripe, legal)
## Verdict: READY TO SHIP | FIX REQUIRED | NOT READY
## Single next action
```

## Validation requirements

- GREEN requires captured command + exit code or a screenshot/log
  reference.
- N-A requires a reason.
- "READY TO SHIP" requires zero RED gates AND no open CRITICAL/HIGH
  security findings.
- The verdict cannot be "READY" if any owner-only blocker is unresolved.
