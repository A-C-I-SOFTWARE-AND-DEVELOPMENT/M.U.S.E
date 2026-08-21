# Workflow — Pricing and Packaging

## Trigger

A pricing or packaging change is proposed (new tier, price
adjustment, entitlement reshuffle).

## Required Divisions

Commercial Office (Pricing Science, Packaging & Entitlements,
Chief Commercial Officer), Research Bureau (Commercial Market
Research), Engineering Factory (Frontend Product Engineer for
`/Billing`), Legal Office (Claims Substantiation, Product
Counsel), Knowledge Operations.

## Required Research Artifact

Pricing Study (`b2b-saas-pricing-study` skill) mandatory.
Carrier ROI model (`carrier-roi-model`) supports the WTP
assertion.

## Agent Topology

Prompt chain.

## Sequence

1. Pricing Study produced by Pricing Science Agent.
2. Packaging Matrix updated by Packaging & Entitlements Agent.
3. Chief Commercial Officer approves direction.
4. Frontend Product Engineer updates `src/pages/Billing.jsx`.
5. Feature-flag registry (`governance/10`) updated.
6. Claims Substantiation Agent reviews any external-facing
   pricing copy (C5 claim).
7. Product Counsel reviews ToS for any subscription term
   implication.
8. Verify + go-no-go.
9. Owner publish + G4.

## Parallelization Opportunities

- Frontend update + flag registry update can run in parallel.
- Claims Substantiation review + Product Counsel review run in
  parallel.

## Maker-Checker Review Points

- Builder: Pricing Science Agent.
- Reviewer: Chief Commercial Officer.
- Verifier: Claims Substantiation Agent.

## Final Outputs

Pricing Study · Packaging Matrix · `src/pages/Billing.jsx`
change · Updated flag registry · ToS update if needed ·
Substantiation memo · Retrospective.

## Acceptance Criteria

- Billing UI matches Pricing Study.
- No external claim contradicts the new pricing.
- No customer-migration ambiguity.
