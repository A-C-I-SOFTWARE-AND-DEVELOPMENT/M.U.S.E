# Workflow — Marketing / GTM

## Trigger

A new positioning push, campaign, landing page, blog post, or
public claim change.

## Required Divisions

Commercial Office (Market Positioning, ASO/SEO, Launch
Campaign), Research Bureau (Commercial Market Research),
Product Studio (UX/UI Trust if `/trust` portal affected), Legal
Office (Claims Substantiation, Product Counsel), Knowledge
Operations.

## Required Research Artifact

GTM Brief (`templates/gtm-brief-template.md`). Competitor
benchmark if positioning changes. Claims Substantiation Memo
for every C1–C5 claim.

## Agent Topology

Prompt chain with parallel review at substantiation.

## Sequence

1. Commercial Market Research Agent updates the competitive
   landscape if relevant.
2. Market Positioning Agent drafts the GTM Brief.
3. Launch Campaign Agent drafts the assets (landing copy, email
   sequence, blog).
4. Parallel:
   - Claims Substantiation Agent reviews every claim
     (`claims-substantiation-review`)
   - Product Counsel reviews disclaimers
   - UX/UI Trust Agent reviews any change to `/trust` or
     `/Billing` copy
5. Verify + go-no-go.
6. Owner publish — owner runs all external posting / ad spend
   (L4 walls).

## Parallelization Opportunities

- Steps 4a/b/c run in parallel.

## Maker-Checker Review Points

- Builder: Launch Campaign Agent / Market Positioning
  Agent.
- Reviewer: Chief Commercial Officer.
- Verifier: Claims Substantiation Agent.

## Final Outputs

GTM Brief · Asset drafts under `marketing/` · Substantiation
Memo · Counsel-review note if any legal-adjacent copy ·
Retrospective.

## Acceptance Criteria

- Every claim substantiated or labeled aspirational per
  `governance/11`.
- Operator-first voice held; no "AI-powered" brag.
- Pricing and entitlement claims match source of truth.
- Owner-runs all ad-spend / social posting (L4 walls intact).
