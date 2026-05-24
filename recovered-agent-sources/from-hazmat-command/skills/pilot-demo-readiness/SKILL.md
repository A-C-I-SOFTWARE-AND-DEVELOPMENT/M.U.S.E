---
name: pilot-demo-readiness
description: Use to prepare for and judge readiness of a real customer demo or pilot session. Walks the demo end-to-end including failure paths, bilingual rendering, audit-ledger export, OCR low-confidence path, and verifies no owner-only-wall dependency on demo morning. Aligned with docs/workflows/pilot-demo-readiness.md.
disable-model-invocation: true
---

# pilot-demo-readiness

## When to use

Owner schedules a customer demo, pilot kickoff, founder demo, or
investor walkthrough. Run this skill 24–72 hours ahead. Re-run on
the morning of the demo.

## Method

1. **Identify the demo script.** The exact steps the carrier sees.
   Local mode AND cloud mode if both are in scope.
2. **Walk the script.** Each step on the build the carrier will
   see. Note any deviation, latency, or error message.
3. **49 CFR rule engine.** Run the canonical compliant case, the
   canonical non-compliant case, and one near-boundary case. Note
   the verdicts.
4. **Bilingual surfaces.** Render both languages. Confirm parity.
5. **Audit ledger.** Export an audit chain for the demo case.
   Confirm it verifies (monotonic, Merkle anchor reachable).
6. **OCR low-confidence path.** Force a low-confidence OCR result.
   Confirm graceful fallback, no crash.
7. **Trust portal.** Render the trust portal. Confirm no
   owner-only-wall content (no "buy now" CTAs the owner hasn't
   approved).
8. **Owner-only-wall check.** Confirm nothing in the demo requires
   the owner to ad-spend, OAuth, submit, or Publish on demo
   morning. If yes, that's a NO-GO.
9. **Baseline drift check.** `npm test` count matches the
   documented baseline (e.g., 727 at v1.0.0-enterprise-ready).
10. **Release-freeze check.** No active freeze trigger per
    `docs/governance/09-release-freeze-and-safety-budget-policy.md`.
11. **Verdict.** Hand to `pilot-readiness-judge`. Output is GO or
    NO-GO with named blockers.

## Output

`docs/templates/pilot-readiness-report-template.md` filled in
with verdict, blockers, risks, and what-if-it-fails plan.

## Anti-patterns

- "Should work" without a step-by-step walkthrough.
- Verdict GO with no recovery plan for the failure paths you saw.
- Skipping the bilingual case because "the carrier speaks English".
- Letting a feature-flag-dependent step slip into the demo.
