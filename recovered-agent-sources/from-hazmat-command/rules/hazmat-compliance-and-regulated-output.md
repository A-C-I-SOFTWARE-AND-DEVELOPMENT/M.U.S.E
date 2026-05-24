---
paths:
  - "src/lib/regulatory/**"
  - "src/api/localValidation.js"
  - "base44/functions/runValidation/**"
  - "src/lib/documents/shippingPaper172_202.ts"
  - "src/lib/documents/placardSheet172_504.ts"
  - "src/lib/documents/ergSheet172_602.ts"
  - "src/lib/documents/dvirManifest.ts"
  - "src/lib/documents/trainingDossier172_704.ts"
  - "src/lib/documents/bilingualRender.ts"
  - "src/api/ergData.js"
  - "docs/compliance/**"
---

# HazMat compliance and regulated output

**Path scope (auto-activates):** the regulator-facing surfaces in
the `paths` frontmatter above. Auto-loaded when Claude reads files
matching them. Original list: `src/lib/regulatory/**`,
`src/api/localValidation.js`, `base44/functions/runValidation/**`,
`src/lib/documents/shippingPaper172_202.ts`,
`src/lib/documents/placardSheet172_504.ts`,
`src/lib/documents/ergSheet172_602.ts`,
`src/lib/documents/dvirManifest.ts`,
`src/lib/documents/trainingDossier172_704.ts`,
`src/lib/documents/bilingualRender.ts`,
`src/api/ergData.js`,
`docs/compliance/**`.

**Authority:** `AGENTS.md`,
`docs/governance/03-change-risk-matrix.md` (RC3 — regulator-facing),
`docs/governance/05-research-dossier-standard.md`,
`docs/skills/49cfr-rule-audit.md`,
`docs/skills/erg-source-validation.md`,
`docs/skills/shipping-paper-compliance-review.md`,
`docs/skills/placard-threshold-review.md`,
`docs/skills/tdg-crossborder-review.md`.

Regulator-facing logic and documents are RC3. They control whether a
real shipment can move legally. Mistakes here are not "feature
bugs" — they are non-conformance. The Research & Evidence Bureau is
the third verifier on every change here.

## Discipline on these paths

1. **Research dossier first.** Before changing rule-engine logic,
   ERG data, placard thresholds, or any regulator-facing builder,
   produce a research dossier per
   `docs/governance/05-research-dossier-standard.md`. Cite the
   exact 49 CFR section, the TDG paragraph, the UN/DOT number, the
   ERG page, the relevant special provision. Do not paraphrase
   regulation in the dossier — quote it.
2. **Regression tests are mandatory.** Every changed code path adds
   tests covering:
   - the canonical compliant case (does not regress to flagged),
   - the canonical non-compliant case (does not regress to
     compliant),
   - at least one near-boundary case (placard threshold, exception
     limit, packaging group boundary).
3. **Preserve provenance.** Every regulator-facing artifact carries
   the source citation (49 CFR section, ERG guide page, TDG
   schedule). Do not strip citations from generated output. Do not
   merge two distinct citations into one line.
4. **No casual wording changes.** Regulator-facing text (shipping
   paper headings, placard text, ERG-derived response language)
   matches the regulation verbatim or matches a documented house
   style under `docs/compliance/`. Do not "improve clarity" without
   a citation showing the new wording is also valid.
5. **Bilingual rendering parity.** Bilingual surfaces
   (`bilingualRender.ts`) must render both languages from the same
   source citation. Translating only one side or silently dropping
   the other is non-conformance.
6. **Training and certification logic.** Changes to the training
   dossier or 49 CFR § 172 Subpart H artifacts require evidence
   that the dossier still satisfies the regulation's content
   requirements. Cite the regulation in the PR.

## Pre-merge gates for this scope

- All commercial-delivery-standard gates.
- Negative tests added or referenced for every changed branch.
- Research dossier link in PR body for any rule-engine or
  builder change.
- Independent reviewer note from Assurance Office.
- Verifier note from Research & Evidence Bureau confirming citations.

## Anti-patterns rejected on sight

- Adding a placard threshold without citing § 172.504.
- Editing ERG data without citing the ERG edition and page.
- Changing rule-engine behavior with no negative test.
- Generating regulator-facing prose with no citation.
- Removing a citation because "the test file got long".
- Translating one language and not the other.
- Using the rule engine to silently coerce a "close enough" case
  into compliant.
