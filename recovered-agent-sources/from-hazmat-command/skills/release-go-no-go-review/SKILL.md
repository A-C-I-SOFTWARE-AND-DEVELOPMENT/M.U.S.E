---
name: release-go-no-go-review
description: Use before tagging or shipping a release. Verifies G0–G4 release governance per PUBLISH.md, runs the freeze-trigger check, and produces a binary GO / NO-GO recommendation for the owner. Aligned with docs/skills/release-go-no-go-review.md (the AEO SOP) and docs/governance/09-release-freeze-and-safety-budget-policy.md.
disable-model-invocation: true
---

# release-go-no-go-review

## When to use

Owner is considering tagging a release, promoting Vercel to
production, or clicking Base44 Publish. Run this skill first.

## Method

1. **PUBLISH.md G0–G4 walk-through.** Each gate's evidence
   confirmed:
   - G0 — preview running clean (Vercel preview URL reachable,
     Base44 Builder preview matches branch).
   - G1 — owner walked both surfaces.
   - G2 — explicit owner approval recorded.
   - G3 — rollback plan stated.
   - G4 — post-publish verification plan stated.
2. **Freeze-trigger check.** Walk the 9 release-freeze triggers in
   `docs/governance/09-release-freeze-and-safety-budget-policy.md`.
   Any active? If yes, NO-GO until cleared or owner overrides
   explicitly.
3. **Pilot-week 24h freeze rule.** If we are inside a pilot
   week's 24h freeze window: NO-GO unless owner overrides.
4. **Baseline drift.** `npm test` count matches the documented
   baseline. If not, explain.
5. **CI green on the target SHA.** Lint/typecheck/test/build,
   dependency audit, gitleaks, semgrep, e2e, governance index,
   agentos check.
6. **Rollback validated.** Revert SHA known. Doc procedure
   exists.
7. **What-if-it-fails plan.** Named failure modes, recovery
   steps.
8. **Verdict.** Hand to `pilot-readiness-judge` if it overlaps a
   demo. Otherwise produce the verdict directly.

## Output

```
VERDICT: GO | NO-GO
GATES:
- G0: ok | blocked-by ...
- G1: ok | blocked-by ...
- G2: ok | blocked-by ...
- G3: ok | blocked-by ...
- G4: ok | blocked-by ...
FREEZE-TRIGGERS: none-active | active: ...
BASELINE: stable | moved (explain)
ROLLBACK: <revert SHA + doc>
WHAT-IF-IT-FAILS: <named failure, recovery>
```

## Anti-patterns

- GO with one gate marked "should be ok".
- GO without naming the rollback SHA.
- Ignoring an active freeze trigger.
- Verdict from a builder agent (use `pilot-readiness-judge` or
  Assurance for independence).
