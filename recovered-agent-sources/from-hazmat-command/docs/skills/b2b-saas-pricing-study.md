# Skill — b2b-saas-pricing-study

## Purpose

Produce an evidence-based pricing study for HazMat Command. The
current pricing is **Solo $29 · Team $79 · Fleet $199 ·
Enterprise** (per `AGENTS.md`). Annual = 10× monthly. Any change
to these numbers requires a study.

## Triggers

- Owner asks for a pricing change.
- Competitor pricing changes materially.
- A new tier is proposed (e.g. Premium between Fleet and
  Enterprise).
- A value driver lands (e.g. real-time SCIM, certified FR
  rendering) that changes WTP.

## Required Inputs

- Current pricing source of truth (`AGENTS.md` + `src/pages/
  Billing.jsx` + the entitlements table from
  `packaging-entitlements-analysis`).
- Competitor benchmark (`competitor-benchmark` skill output).
- Customer pain synthesis (`customer-pain-mining` output).
- Carrier ROI model (`carrier-roi-model` skill output).
- The feature-flag registry
  (`governance/10-feature-flag-and-beta-gate-registry.md`)
  reflecting what's actually enabled per plan today.

## Research Required

- Public pricing pages of 3–6 comparable B2B SaaS competitors.
- WTP literature for safety/compliance software in trucking.
- Annual vs. monthly discount norms in B2B SaaS (8x to 12x
  monthly is the typical band).

## Step-by-Step Method

1. Restate the current plan band with entitlements.
2. Build the WTP model per persona (solo, team, fleet,
   enterprise) using competitor benchmarks + ROI model.
3. Test the current price points against the WTP model. Where
   does HazMat Command leave money on the table? Where might it
   be priced over the market?
4. Propose 1–2 changes with explicit rationale. Each change
   carries:
   - new price
   - WTP justification
   - competitor cross-reference
   - expected impact on conversion (estimated)
   - migration plan for existing customers
5. Confirm the change is consistent with packaging
   (`packaging-entitlements-analysis`).
6. Confirm the change does not require updating any
   already-published commercial claim that contradicts the new
   price.
7. Produce a Pricing Study artifact.

## Deliverable Format

`docs/templates/pricing-study-template.md` populated, saved to
`docs/research/pricing/<YYYY-MM-DD>-<slug>.md`.

## Quality Checklist

- [ ] WTP model cites at least 3 competitor benchmarks
- [ ] Annual / monthly band consistent with B2B SaaS norms
- [ ] Migration plan for existing customers
- [ ] Consistent with packaging
- [ ] No public-claim conflict

## Escalation Triggers

- A change > 25% in any single tier → owner judgment + Chief
  Commercial Officer veto check.
- A change that requires PCI-scope changes (e.g. real Square
  flip while stubbed) → halt; route to Engineering Factory +
  Legal.

## Related Agents

- Pricing Science Agent (Commercial Office)
- Packaging & Entitlements Agent (Commercial Office)
- Chief Commercial Officer (Commercial Office)
- Claims Substantiation Agent (Legal Office)

## Related Artifacts

- `docs/templates/pricing-study-template.md`
- `src/pages/Billing.jsx` (current implementation)
