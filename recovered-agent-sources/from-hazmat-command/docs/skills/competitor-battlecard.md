# Skill — competitor-battlecard

## Purpose

Produce a battlecard for a single competitor — the one-pager a
sales conversation references when a buyer mentions that
competitor by name.

## Triggers

- Buyer mentions a specific competitor.
- A competitor releases a notable feature.
- A win/loss interview surfaces a new competitor pattern.

## Required Inputs

- The competitor name.
- The output of `competitor-benchmark` for this competitor.
- HazMat Command's current capability list.

## Research Required

- The competitor's public site, pricing page, security page,
  most recent product release notes.
- Public RFP responses from the competitor if available.
- Practitioner reviews (friction signal only).

## Step-by-Step Method

1. Build the battlecard on one page with these sections:
   - **Competitor at a glance** — founded, funding (public),
     primary market, public customer logos if cited.
   - **Where they win** — features where they lead HazMat
     Command, with citations.
   - **Where we win** — features where HazMat Command leads,
     with substantiated claims per `governance/11`.
   - **Common buyer objections + how to answer** — 3 specific
     objections.
   - **Pricing comparison** — like-for-like tier.
   - **Trap questions** — questions to ask the buyer that
     surface this competitor's weakness.
2. Every claim is cited (URL + date or repo file path).
3. Label aspirational items explicitly.

## Deliverable Format

A one-page battlecard under `docs/research/battlecards/
<competitor>-<YYYY-MM-DD>.md`.

## Quality Checklist

- [ ] Every claim cited
- [ ] No unsubstantiated "where we win" claim
- [ ] Pricing matches our source of truth
- [ ] No competitor IP / trade-secret content used

## Escalation Triggers

- A trap question that could expose HazMat Command to legal
  risk if used in a sales pitch → halt; route to Legal Office.

## Related Agents

- Competitor Intelligence Agent (Commercial Office)
- B2B Sales Enablement Agent (Commercial Office)
- Claims Substantiation Agent (Legal Office)

## Related Artifacts

- Output of `competitor-benchmark`
- `docs/templates/gtm-brief-template.md`
