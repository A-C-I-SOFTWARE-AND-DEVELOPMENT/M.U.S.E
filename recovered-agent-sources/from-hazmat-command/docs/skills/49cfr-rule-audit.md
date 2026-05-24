# Skill — 49cfr-rule-audit

## Purpose

Audit a specific 49 CFR Subchapter C section against HazMat
Command's current rule-engine coverage and identify gaps.

## Triggers

- A customer or RFP asks about a specific 49 CFR section's
  coverage.
- A PHMSA enforcement update changes a rule's effective date or
  citation.
- A new feature's design references 49 CFR — confirm coverage
  before promising.
- Quarterly compliance review.

## Required Inputs

- The 49 CFR section (e.g. §172.202, §172.504, §172.602,
  §172.704(d), §172.519, §172.201(e), §177.817, §396.11).
- Whether this is a coverage check, a defect check, or a
  rule-version update.

## Research Required

- The 49 CFR section's full current text (primary source).
- PHMSA's enforcement guidance / interpretation letters if
  available.
- The matching code paths in:
  - `src/api/localValidation.js` (49 CFR rule engine for local
    mode)
  - `base44/functions/runValidation/` (server-side rule engine)
  - `src/lib/regulatory/**` (rule data)
  - `src/lib/documents/{shippingPaper172_202,placardSheet172_504,
    ergSheet172_602,trainingDossier172_704,dvirManifest}.ts`
    (regulator-facing builders that consume the rules)

## Step-by-Step Method

1. Quote the relevant CFR clause(s) with section / paragraph
   numbers.
2. `git grep` the citation across the repo to find every code
   site that claims to cover it.
3. Read each code site; note what it enforces, what it does not,
   and where the tests live.
4. Identify gaps: missing rule branches, missing test cases,
   stale rule versions, missing UI surfaces.
5. Cross-reference any `SKIPPED.md` entry that touches the
   citation (e.g. `tc-erg-2024` cross-references §172.602 for
   Canadian-domestic shipments).
6. Cross-reference `docs/iso27001/statement-of-applicability.md`
   A.5.31 (legal / regulatory requirements).
7. Recommend changes: code additions, test additions,
   SKIPPED entries to open, or doc updates.

## Deliverable Format

A 49 CFR Audit memo under `docs/research/<YYYY-MM-DD>-49cfr-
<section>.md`. Sections: Citation, Current Coverage, Gaps,
Recommended Moves, SKIPPED / Flag impact.

## Quality Checklist

- [ ] Every code path cited with file + line
- [ ] Every gap is concrete (not "could be better")
- [ ] Recommended moves include test additions where applicable
- [ ] SKIPPED.md cross-references checked
- [ ] No claim of "full coverage" without an Independent QA
  reviewer

## Escalation Triggers

- A gap that means a regulator-facing PDF could be wrong → halt
  any related claim publication; route to Risk Controller.
- A rule version change with a regulatory effective date < 60
  days away → Pilot Readiness Judge alert.

## Related Agents

- 49 CFR Regulatory Research Agent (Research Bureau, division 02)
- Compliance Engine Engineer (Engineering Factory, division 04)
- Compliance Evidence Agent (Assurance Office, division 05)

## Related Artifacts

- `docs/templates/compliance-evidence-matrix-template.md`
