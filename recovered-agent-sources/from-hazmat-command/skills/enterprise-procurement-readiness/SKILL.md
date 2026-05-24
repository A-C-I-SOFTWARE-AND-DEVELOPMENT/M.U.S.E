---
name: enterprise-procurement-readiness
description: Use when preparing for an enterprise procurement / RFP / security review. Walks RFP answer bank, ISO 27001 / compliance evidence matrix, sub-processor list, DPA / MSA drafts, and trust-portal content. Surfaces gaps before the buyer does. Aligned with docs/workflows/enterprise-procurement-readiness.md.
disable-model-invocation: true
---

# enterprise-procurement-readiness

## When to use

A prospect requests an RFP response, security review, vendor
questionnaire, DPA, MSA, SOW, sub-processor list, or trust portal
walkthrough. Run before sending anything.

## Method

1. **Inventory the ask.** What sections of the RFP / questionnaire
   are in scope? What evidence does the prospect want
   (SOC 2 report, ISO 27001 cert, penetration test report, DPA,
   sub-processor list, BCP/DR, incident response plan)?
2. **Map to evidence.** For each item:
   - Does the evidence exist under `docs/security/`,
     `docs/iso27001/`, `docs/compliance/`, `docs/runbooks/`?
   - If yes, link it. If no, mark **gap** and triage.
3. **Answer bank check.** Update `docs/rfp/answer-bank.md` with
   the verified evidence link for each answer.
4. **Aspirational claims.** Anything we do not have today (SOC 2
   cert, HIPAA, PCI, ISO 27001 cert) gets the aspirational label
   per `docs/governance/11-commercial-claims-substantiation-policy.md`.
5. **Sub-processor list.** Confirm it reflects the current vendor
   set (Base44, Vercel, Supabase, Square, Sentry, S3, WorkOS,
   Resend / SendGrid, etc.).
6. **DPA / MSA / SOW drafts.** Use the Legal Office. Drafts only;
   counsel-review banner present.
7. **Trust portal walkthrough.** Open `src/pages/Trust.jsx` paths
   in a browser. Verify content matches the answer bank.
8. **Gap remediation plan.** For each gap: owner, ETA, blocker
   class.

## Output

- Updated `docs/rfp/answer-bank.md`.
- Gap list with owners.
- Counsel-review-bannered legal drafts under `docs/`.
- Aspirational-claim labels applied.

## Anti-patterns

- "We are SOC 2 compliant" — we are not. Aspirational labeling.
- A new RFP answer with no evidence link.
- A DPA without the counsel-review banner.
- A sub-processor list missing a vendor that ships in code.
