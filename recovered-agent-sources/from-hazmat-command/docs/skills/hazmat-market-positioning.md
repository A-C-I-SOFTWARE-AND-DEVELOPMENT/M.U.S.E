# Skill — hazmat-market-positioning

## Purpose

Position HazMat Command in the hazmat-carrier compliance market
without sliding into commodity SaaS or "AI-powered" marketing
cliche. The operator-first voice in `AGENTS.md` is law:
**Hazmat Compliance, Commanded.**

## Triggers

- Owner asks for a positioning refresh.
- A new competitor enters the space.
- A material capability change (e.g. RLS lands, WorkOS lands,
  TC ERG 2024 ships).
- A new ICP (ideal customer profile) emerges.

## Required Inputs

- Current positioning artifacts (`marketing/`, `/trust` portal,
  `/Billing` cards, `docs/rfp/answer-bank.md`).
- Recent competitor benchmark from `competitor-benchmark` skill.
- Pricing source of truth (`AGENTS.md` plan band; `src/pages/
  Billing.jsx`).
- Brand identity: navy `#0f1620` + metallic gold `#d4a830`;
  operator-first voice — never "AI-powered" as a brag.

## Research Required

- FTC truth-in-advertising guidance.
- Sub-vertical research: Tier-1 hazmat carriers, small-fleet
  hazmat operators, owner-operators, hazmat 3PLs, hazmat
  shippers (not carriers but adjacent).
- Buyer-persona research: safety_manager, CISO/IT director at
  a Tier-1 carrier, dispatcher, owner-operator.

## Step-by-Step Method

1. Restate ICP(s) tied to the 5 roles in the product.
2. Identify the top 3 buyer pains for each persona (use the
   `customer-pain-mining` skill as input).
3. Articulate the positioning statement: "For <ICP>, who <pain>,
   HazMat Command is <category> that <unique value>. Unlike
   <alternative>, we <differentiator>."
4. For each differentiator, identify the C1–C5 substantiation
   class per `governance/11`. C6 aspirational claims must be
   labeled.
5. Confirm the positioning is consistent with the
   operator-first voice. Reject any "AI-powered" framing as
   a brag.
6. Cross-check against the existing `/trust` portal copy and
   the current RFP answer bank.
7. Produce a GTM Brief using
   `docs/templates/gtm-brief-template.md`.

## Deliverable Format

A GTM Brief with positioning statement, ICP, pains, differentiators,
substantiation classes, and rollout sequence.

## Quality Checklist

- [ ] Operator-first voice held
- [ ] Every differentiator substantiated or labeled aspirational
- [ ] Pricing consistent with source of truth
- [ ] Brand colors and tagline preserved
- [ ] No "AI-powered" brag

## Escalation Triggers

- A differentiator that overclaims a stubbed capability → halt;
  Claims Substantiation Agent.
- A positioning move that conflicts with the existing `/trust`
  portal copy → reconcile or update the portal first.

## Related Agents

- HazMat Market Positioning Agent (Commercial Office)
- Chief Commercial Officer (Commercial Office)
- UX/UI Trust Agent (Product Studio)
- Claims Substantiation Agent (Legal Office)

## Related Artifacts

- `docs/templates/gtm-brief-template.md`
- `marketing/` (current copy)
- `docs/rfp/answer-bank.md`
