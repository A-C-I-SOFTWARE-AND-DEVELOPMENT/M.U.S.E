---
description: Run a Nourish-specific product, psychology, UX, mobile, and launch audit
---

# /nourish-audit

## Purpose

Run a Nourish-tailored audit covering product correctness (meal planning,
grocery aggregation, dietary safety), psychology (retention without dark
patterns), UX polish (Sunday-cognition test), mobile readiness, and launch
gates.

## When to use

- The current repo is `nourish-production`.
- You are about to demo, beta-launch, or store-submit Nourish.
- A retention or onboarding change just landed and needs a tailored
  review.

## Agents activated

1. `repo-context-librarian` (first)
2. `nourish-product-specialist` (mandatory)
3. `psychology-behavior-designer` (mandatory)
4. `ux-polish-product-designer` (mandatory)
5. `mobile-release-engineer` (mandatory if mobile build exists)
6. `qa-launch-validator` (mandatory)
7. `security-privacy-risk-officer` (mandatory if user data / accounts
   touched)
8. `hermes-final-synthesizer` (last)

Skill invoked: `nourish-product-playbook`, plus
`mobile-release-readiness`, `ux-polish-review`, and `hermes-launch-audit`
as appropriate.

## Required workflow

1. Mission brief naming the Nourish surface under review (plan / grocery /
   recipe / pantry / onboarding / nutrition / launch).
2. Repo map.
3. Specialists run in parallel, each producing their domain report with
   `file:line` or screenshot references.
4. Synthesizer reconciles into a single verdict and execution plan.

## Required output format

```
## Surface under review
## Nourish domain findings (rule violations, anti-patterns, retention risk)
## Psychology findings (mechanisms used, ethical check, refused patterns)
## UX polish findings (BLOCKER/HIGH/MEDIUM/LOW)
## Mobile readiness (if applicable)
## QA gates
## Security findings (if applicable)
## Synthesizer verdict: SHIP | POLISH | RETHINK
## Code-side blockers
## Owner-only blockers (nutrition data source, store assets, legal)
## Single next action
```

## Validation requirements

- Every domain finding cites a file, route, or screenshot.
- Hard dietary filters (allergens, religious, medical) must be confirmed
  by source inspection; "looks fine" is not enough.
- UI claims (one-handed Sunday plan-confirm) require evidence
  (screenshot or component file).
