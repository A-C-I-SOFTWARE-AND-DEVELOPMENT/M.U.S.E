# Skill — shipping-paper-compliance-review

## Purpose

Audit the §172.202 / §172.203 / §172.204 shipping paper builder
(`src/lib/documents/shippingPaper172_202.ts`) for content
completeness, layout placement, and regulator-visibility
correctness.

## Triggers

- Any change to `shippingPaper172_202.ts` or its template
  (`public/templates/shipping-paper-172_202.pdf`).
- Any change to the rule engine that affects shipping-paper
  validation.
- A customer reports a missing field or layout issue.
- Designer-blessed template arrives (closes
  `shipping-paper-template-final`).

## Required Inputs

- The current state of `shippingPaper172_202.ts` and the
  template's SHA-256 (`TEMPLATE_SHA256` constant).
- The four-pronged regression harness coverage at
  `src/lib/documents/regressionHarness.ts` (golden bytes,
  extracted text, bbox placement; pixel-diff stubbed pending
  `pdf-to-image` stub).
- The golden fixtures at `tests/golden/shipping-paper-172_202.*`.

## Research Required

- 49 CFR §172.202 (basic description), §172.203 (additional
  description requirements: hazmat substances, marine pollutants,
  etc.), §172.204 (shipper certification statement).
- PHMSA preferred shipping-paper layout guidance.

## Step-by-Step Method

1. Confirm every §172.202(a) required field is rendered: proper
   shipping name, hazard class, identification number (UN),
   packing group, total quantity, number/type of packages.
2. Confirm every §172.203 conditional field renders when
   triggered (e.g. "RQ" for reportable quantities, technical
   name in parentheses for n.o.s. entries, marine-pollutant
   designation).
3. Confirm the §172.204 shipper certification statement renders
   verbatim per regulation when the shipping paper is signed.
4. Run the regression harness: `npm test -- shippingPaper172_202`.
   Confirm golden bytes pass, extracted text pass, bbox
   placement pass.
5. If the template SHA-256 has changed, confirm both
   `TEMPLATE_SHA256` in code and the hash in
   `public/templates/.template-source.md` match the new file.
6. If layout regions moved, regenerate goldens.
7. For bilingual rendering: confirm FR strings used (when
   `locale: 'fr'`) come from the bilingual layer
   (`src/lib/documents/bilingualRender.ts`) and the
   `certified-translator-engagement` stub status is honored —
   FR PDFs must not be generated for regulator-facing
   shipments until cert-log marks the section certified.

## Deliverable Format

A Shipping Paper Compliance Memo: list of fields confirmed,
fields with gaps, test status, recommended changes.

## Quality Checklist

- [ ] All §172.202(a) fields render
- [ ] Conditional §172.203 fields fire correctly
- [ ] §172.204 certification statement verbatim
- [ ] `npm test -- shippingPaper172_202` green
- [ ] Template SHA-256 consistent
- [ ] FR-locale generation respects certified-translator gate

## Escalation Triggers

- A missing required field that would produce a non-compliant
  shipping paper → Risk Controller; release freeze under
  `governance/09` trigger 3.
- FR PDF generated for a regulator-facing shipment without
  certified strings → Risk Controller.

## Related Agents

- Compliance Engine Engineer (Engineering Factory)
- 49 CFR Regulatory Research Agent (Research Bureau)
- Compliance Evidence Agent (Assurance Office)
- Pilot Readiness Judge (Assurance Office)

## Related Artifacts

- `tests/golden/shipping-paper-172_202.*`
- `docs/iso27001/statement-of-applicability.md` A.5.31
