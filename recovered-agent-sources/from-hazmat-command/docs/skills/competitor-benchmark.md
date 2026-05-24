# Skill — competitor-benchmark

## Purpose

Produce an evidence-backed competitor benchmark for HazMat
Command's market — carrier-management SaaS, hazmat compliance,
fleet safety, EHS, TMS adjacencies.

## Triggers

- A pricing decision is pending.
- A positioning question is being researched.
- An RFP requires a competitive analysis.
- A new entrant is reported in the market.

## Required Inputs

- The set of competitors to benchmark (3–6 is the sweet spot).
- The dimensions to compare (feature coverage, pricing tier,
  enterprise readiness, mobile, regulator-document scope, audit
  trail, bilingual, etc.).

## Research Required

- Each competitor's public pricing page (capture URL + date).
- Each competitor's feature list (public site only — no scraping
  private trials).
- Public RFP/SOC 2/ISO 27001 attestation pages.
- Practitioner reviews (friction signal only).

## Step-by-Step Method

1. List the competitors with one-sentence descriptions.
2. Build a Feature × Competitor matrix. Rows: features grounded
   in HazMat Command's actual surface (49 CFR document set,
   audit chain, OCR provenance, SSO/SCIM, bilingual, mobile,
   trust portal). Columns: competitors.
3. Cell values are evidence references (URL + date), not
   adjectives. If a competitor "claims X but no evidence,"
   record that.
4. Build a Pricing × Competitor matrix. Rows: solo / team /
   fleet / enterprise tiers. Columns: competitors.
5. Note enterprise-readiness signals: SOC 2, ISO 27001, BAA,
   SCIM, DPA, sub-processor list, security portal.
6. Surface 3 deltas where HazMat Command leads, 3 where a
   competitor leads, 3 where parity is contested.
7. Recommend positioning moves based on the deltas.

## Deliverable Format

A markdown report under `docs/research/<YYYY-MM-DD>-competitor-
benchmark-<topic>.md` with the two matrices and the deltas
section.

## Quality Checklist

- [ ] Every cell cites evidence with date
- [ ] Pricing matrix matches HazMat Command's source of truth
  (`src/pages/Billing.jsx` + `AGENTS.md`)
- [ ] No competitor claim copied without independent verification
- [ ] Deltas tied to a positioning move, not just listed

## Escalation Triggers

- A competitor delta that suggests HazMat Command overclaims a
  capability → halt; route to Claims Substantiation Agent.

## Related Agents

- Competitor Intelligence Agent (Commercial Office, division 06)
- HazMat Market Positioning Agent (Commercial Office)

## Related Artifacts

- `docs/templates/gtm-brief-template.md`
- `competitor-battlecard.md` skill (companion)
