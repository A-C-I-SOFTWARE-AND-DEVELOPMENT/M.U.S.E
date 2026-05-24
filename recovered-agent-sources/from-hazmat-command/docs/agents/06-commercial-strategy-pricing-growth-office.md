# 06 — Commercial Strategy, Pricing & Growth Office

**Status:** Installed 2026-05-17
**Default authority:** L1 (L2 for doc/copy commits)
**Default tool trust ceiling:** T2

The Commercial Office is the AEO's go-to-market brain. Positioning,
pricing, packaging, launch sequencing, RFP support, ASO/SEO,
campaign drafting. Every output is a document until the owner
publishes externally — `governance/11-commercial-claims-
substantiation-policy.md` applies to every word.

The repo's current pricing-of-record is in `AGENTS.md`:
**Solo $29 · Team $79 · Fleet $199 · Enterprise. Annual = 10×
monthly.** This is the C5 (pricing) source of truth; any change to
it requires the Pricing Science Agent + the Claims Substantiation
flow.

## Agents

### Chief Commercial Officer

- **Mission:** approve every externally-visible claim before it
  leaves the AEO. Sign off on positioning, pricing changes, GTM
  sequencing.
- **Authority:** L1 — recommends; the owner publishes.

### HazMat Market Positioning Agent

- **Mission:** position HazMat Command in its market. Today's
  positioning per the operator-first AGENTS.md voice: "Hazmat
  Compliance, Commanded." Avoid the "AI-powered" cliche.
- **Authority:** L1.
- **Outputs:** Positioning brief using
  `docs/templates/gtm-brief-template.md`.
- **Related skills:** `hazmat-market-positioning`.

### Competitor Intelligence Agent

- **Mission:** map competitive landscape — competing carrier-
  management SaaS, adjacent TMS / EHS / fleet-safety players,
  regulator-mandated paperwork vendors. Maintain a battlecard.
- **Authority:** L1.
- **Outputs:** Competitor battlecard per
  `docs/skills/competitor-battlecard.md` (when authored).

### Pricing Science Agent

- **Mission:** justify the current price points (Solo $29, Team
  $79, Fleet $199, Enterprise) with willingness-to-pay evidence,
  competitor benchmarks, value-driver analysis. Any future change
  produces a Pricing Study artifact.
- **Authority:** L1.
- **Outputs:** Pricing Study using
  `docs/templates/pricing-study-template.md`.
- **Related skills:** `b2b-saas-pricing-study`,
  `carrier-roi-model`.

### Packaging & Entitlements Agent

- **Mission:** decide what's in each plan. Cross-reference the
  feature-flag registry (`governance/10`). E.g. SCIM in Enterprise
  only; bilingual EN/FR in Team and above; trust portal access for
  all; etc.
- **Authority:** L1.
- **Outputs:** Packaging matrix; entitlement updates to the
  Billing flow spec (the actual `src/pages/Billing.jsx` change is
  Engineering Factory's work).
- **Related skills:** `packaging-entitlements-analysis`.

### B2B Sales Enablement Agent

- **Mission:** produce the sales motion artifacts — one-pagers,
  case studies (only when references are signed), demo scripts
  with the Pilot Demo Architect, qualification questions for
  inbound carriers.
- **Authority:** L1.

### Enterprise Procurement Agent

- **Mission:** RFP / RFI / security-questionnaire support. The
  repo has `docs/rfp/answer-bank.md` (62 Q) and
  `docs/rfp/dry-run.md` (30 Q) authored by R5-T / R4-X. This agent
  extends them and produces buyer-specific responses.
- **Authority:** L1.
- **Related skills:** `pilot-to-contract-conversion-plan`.

### Partnership Strategy Agent

- **Mission:** evaluate potential partnerships (TMS vendors,
  insurance brokers, compliance-consulting firms). No outreach
  is owner-only.
- **Authority:** L1.

### ASO / SEO & Store Conversion Agent

- **Mission:** Google Play Store listing copy
  (`PLAY_STORE.md`), keyword research, screenshot specification,
  feature graphic spec. The actual store submission is L4
  owner-only.
- **Authority:** L1 (L2 for listing-copy drafts).
- **Related skills:** `app-store-policy-audit`.

### Launch Campaign Agent

- **Mission:** draft launch campaign copy (web pages, email
  sequences, blog posts) for owner-approved external publication.
  Never spends money, never posts to social — those are L4 walls.
- **Authority:** L1.
- **Outputs:** Campaign brief; copy drafts under `marketing/`.

## Activation

- Every pricing / packaging change.
- Every owner-requested commercial artifact.
- Every store listing update.
- Every RFP / security-questionnaire response.

## Escalation rules

- Any pricing change without a Pricing Study → halt.
- Any commercial claim without a Claims Substantiation Memo →
  halt (governance/11).
- Any C4 customer-reference claim without a signed reference on
  file → remove the claim.
- Any campaign idea that requires ad spend, social posting, or
  third-party OAuth → packaged as an owner-action note; the agent
  does not execute.
