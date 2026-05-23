---
description: Run a full Hermes council audit on the current repo
---

# /hermes-audit

## Purpose

Run the full Hermes council on the current repository and return one
prioritized answer with verdict, code-side blockers, owner-only blockers,
execution plan, validation gates, and the single next action.

## When to use

- You want a multi-domain audit (product, security, UX, mobile, growth) of
  the repo in front of you.
- You are about to make a public claim about the project and want it
  pressure-tested first.
- A new contributor has just inherited the repo and needs a real picture.

## Agents activated

1. `repo-context-librarian` (always first, single pass)
2. `aos-audit-validator` (if the repo contains an agent system)
3. `security-privacy-risk-officer`
4. `qa-launch-validator`
5. `ux-polish-product-designer`
6. `nourish-product-specialist` (only if repo is Nourish)
7. `mobile-release-engineer` (only if repo has a mobile target)
8. `product-strategy-growth-agent` (only if a strategic question is named)
9. `hermes-final-synthesizer` (always last)

Orchestrated by `hermes-chief-orchestrator`.

## Required workflow

1. Chief orchestrator writes the one-paragraph mission brief from the
   user's request.
2. Repo librarian produces the context map.
3. Specialists fan out in parallel with the map + their specific question.
4. Synthesizer reconciles findings.
5. Owner-blocker separation runs against the synthesized list.

## Required output format

```
## Mission
## Specialists engaged (with one-line reason each)
## Findings (per specialist, verbatim summary)
## Synthesizer verdict (SHIP NOW / SHIP AFTER FIXES / DO NOT SHIP / RETHINK)
## Code-side blockers
## Owner-only blockers
## Execution plan (staged)
## Validation gates required before "done"
## Single next action
```

## Validation requirements

- Every "READY"-class verdict requires `qa-launch-validator` evidence.
- Every security claim requires `security-privacy-risk-officer` findings.
- No specialist may be silently skipped — list it as "not run" with reason.
- Synthesizer cannot upgrade above the lowest specialist verdict without
  explicit override rationale.
