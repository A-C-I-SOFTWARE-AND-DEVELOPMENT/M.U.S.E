# Skill — document-renderer-regression-review

## Purpose

Run the four-pronged regression harness
(`src/lib/documents/regressionHarness.ts`) against the five
regulator-facing document builders and surface any drift.

## Triggers

- Any change to a builder under `src/lib/documents/`.
- Any change to the template under `public/templates/`.
- Any change to the placard set or ERG bundle.
- Pre-pilot rehearsal.

## Required Inputs

- The five builders: `shippingPaper172_202.ts`,
  `placardSheet172_504.ts`, `ergSheet172_602.ts`,
  `dvirManifest.ts`, `trainingDossier172_704.ts`.
- Their golden fixtures under `tests/golden/`.
- The regression harness implementation.

## Research Required

- Harness coverage: golden bytes, extracted text, bbox
  placement; pixel-diff stubbed pending `pdf-to-image` stub.

## Step-by-Step Method

1. Run `npm test -- shippingPaper172_202`,
   `npm test -- placardSheet172_504`,
   `npm test -- ergSheet172_602`,
   `npm test -- dvirManifest`,
   `npm test -- trainingDossier172_704`.
2. For each failing assertion, classify:
   - golden bytes drift (template hash changed; layout moved)
   - extracted-text drift (field content changed)
   - bbox placement drift (layout regions moved)
3. For legitimate template changes, regenerate the golden and
   document the change in an ADR (`docs/research/adrs/`).
4. Confirm the pixel-diff comparator status (today stubbed via
   `pdf-to-image` — does not fire). If
   `pdf-to-image` clears in a future sprint, re-run with it
   enabled.
5. For bilingual rendering: confirm both `locale: 'en'` and
   `locale: 'fr'` golden fixtures pass.

## Deliverable Format

Renderer Regression Memo: per-builder pass/fail table, drift
classifications, ADR links for any legitimate template change.

## Quality Checklist

- [ ] All five builders' suites green
- [ ] Any drift documented and ADR'd
- [ ] Bilingual fixtures pass
- [ ] Pixel-diff status flagged

## Escalation Triggers

- Bbox drift on a regulator-facing field (e.g. UN number
  position moved) → halt; Risk Controller.

## Related Agents

- OCR / Document Intelligence Engineer (Engineering Factory)
- Compliance Engine Engineer (Engineering Factory)
- Independent QA / V&V Agent (Assurance Office)

## Related Artifacts

- `tests/golden/**`
- `docs/templates/architecture-decision-record-template.md`
