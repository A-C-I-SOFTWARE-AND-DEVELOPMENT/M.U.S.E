# Skill — carrier-roi-model

## Purpose

Build a defensible ROI model for a hazmat carrier evaluating
HazMat Command. The model converts current carrier pain (audit
prep hours, inspection findings, training-record gaps, OCR
re-keying) into dollar value and compares to plan cost.

## Triggers

- An RFP requires ROI justification.
- A pilot conversion needs an economic case.
- A pricing study needs WTP support.

## Required Inputs

- The carrier's fleet size and rough volume (drivers, loads /
  month, hazmat classes shipped).
- HazMat Command's plan pricing (Solo / Team / Fleet /
  Enterprise).
- Industry-standard data: average DOT-PHMSA inspection finding
  cost; average safety_manager hourly cost; average audit prep
  hours / quarter for a hazmat carrier.

## Research Required

- Public PHMSA enforcement statistics (annual fines, top
  violations).
- Trucking industry compensation surveys for safety roles.
- Customer-pain themes from `customer-pain-mining` (the audit
  prep + endorsement surprise + OCR re-keying themes recur).

## Step-by-Step Method

1. Build a "before HazMat Command" baseline cost: audit prep
   hours/quarter × hourly cost; inspection-finding expected
   value (probability × cost); training-gap risk (probability
   of an undertrained driver × expected fine).
2. Build an "after HazMat Command" reduced cost using
   conservative reductions justified by feature evidence:
   - audit prep: cut by X% because audit chain provides
     timestamped evidence (`api/_lib/auditChain.mjs`)
   - inspection findings: cut by Y% because rule engine catches
     pre-trip errors (49 CFR §172.202/.504/.602/.704 coverage)
   - training gaps: cut by Z% because hazmat-endorsement guard
     (when wired into LoadDetail.jsx) blocks misassignment
3. Net savings = Before − After − Plan cost.
4. Payback period = Plan cost / monthly savings.
5. Sensitivity analysis: show ROI at low / medium / high
   reduction assumptions.
6. Label every assumption explicitly. The model is a
   credible-range estimator, not a guarantee.

## Deliverable Format

A Carrier ROI Memo under `docs/research/<YYYY-MM-DD>-roi-
<carrier-or-segment>.md` with the model worked through.

## Quality Checklist

- [ ] Every assumption labeled with source
- [ ] Sensitivity analysis present
- [ ] No "guaranteed savings" claim
- [ ] Plan cost matches source of truth
- [ ] Reductions justified by specific HazMat features

## Escalation Triggers

- Use of the ROI in external materials → route to Claims
  Substantiation Agent per `governance/11` (the ROI is a C4-
  adjacent claim).

## Related Agents

- Pricing Science Agent (Commercial Office)
- Enterprise Procurement Agent (Commercial Office)
- Claims Substantiation Agent (Legal Office)

## Related Artifacts

- `docs/templates/pricing-study-template.md`
