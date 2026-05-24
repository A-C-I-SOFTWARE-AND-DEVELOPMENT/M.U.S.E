# Skill — placard-threshold-review

## Purpose

Audit the §172.504 placard threshold logic, the 22-placard SVG set
(`public/placards/`), and the `placardSheet172_504` builder
(`src/lib/documents/placardSheet172_504.ts`) for correctness
against 49 CFR §172.504, §172.519, §172.521.

## Triggers

- Any change to the placard table, loader, or sheet builder.
- A PHMSA update to placard thresholds or hazard-class
  classification.
- A customer reports an incorrect placarding decision.
- Designer/consultant sign-off on the SVG set arrives
  (closes `placard-svg-printed-proof`).

## Required Inputs

- The placard table data (`src/lib/regulatory/placards.*` —
  confirm path with `git grep`).
- The 22 SVG files at `public/placards/*.svg`.
- The `REQUIRED_PLACARD_CLASSES` constant.
- The §172.504 threshold rules (Table 1 and Table 2).

## Research Required

- 49 CFR §172.504 (placard thresholds: 454 kg for Table 1;
  varies for Table 2).
- 49 CFR §172.519 (placard specifications — color, symbol,
  proportions, minimum size 273 mm).
- 49 CFR §172.521 (DANGER placard usage).
- PHMSA color reference plates (PMS 151 orange, 186 red, 356
  green, 286 blue, 109 yellow).

## Step-by-Step Method

1. Walk each hazard class through the §172.504 decision tree:
   does the placard fire at the right threshold for Table 1
   (any quantity for materials in Table 1) and Table 2 (over
   454 kg aggregate)?
2. Confirm the DANGER placard option (§172.504(b)) is supported
   when shipping mixed Table 2 materials.
3. Walk each of the 22 SVG placards against the regulatory
   reference: colors within §172.519 PMS bands, symbols match,
   class digit present, hazard-class word present, UN number
   slot exists.
4. Confirm `placardSheet172_504` overlays the placards
   correctly on the PDF with the regulatory dimension
   (10.8" / 273 mm side).
5. Run `npm test -- placards` and `npm test -- placardSheet`.
6. If the `placard-svg-printed-proof` stub closes, attach the
   consultant sign-off to the SKIPPED entry's evidence link.

## Deliverable Format

A Placard Audit memo: per-class table of (1) threshold logic
correctness, (2) SVG conformance, (3) test status.

## Quality Checklist

- [ ] §172.504 Table 1 / Table 2 / DANGER decision tree complete
- [ ] All 22 SVGs visually match the regulatory reference
- [ ] Color values in PMS bands
- [ ] Class digit + hazard-class word + UN slot present
- [ ] Tests green
- [ ] Compliance-consultant sign-off recorded if available

## Escalation Triggers

- A threshold that would result in wrong-placarding a placarded
  load → Risk Controller; release freeze under `governance/09`
  trigger 3.
- A color shift in an SVG that exceeds the §172.519 band → fix
  before any new release.

## Related Agents

- Compliance Engine Engineer (Engineering Factory)
- PHMSA / ERG Source Agent (Research Bureau)
- Compliance Evidence Agent (Assurance Office)

## Related Artifacts

- `tests/lib/regulatory/placards.test.js`
- `docs/iso27001/statement-of-applicability.md` A.5.31
