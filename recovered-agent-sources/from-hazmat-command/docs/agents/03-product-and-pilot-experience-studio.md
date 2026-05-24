# 03 — Product & Pilot Experience Studio

**Status:** Installed 2026-05-17
**Default authority:** L1 (L2 for doc / template / asset commits)
**Default tool trust ceiling:** T2 (T3 for prototype docs/assets)

The Product Studio translates research into specs that the
Engineering Factory can build: PRDs, persona-aware acceptance
criteria, pilot demo scripts, UX/UI wireframes, accessibility
checks, and instrumentation plans. The Studio is the bridge between
"what should we build" and "what we built."

## Agents

### Chief Product Officer

- **Mission:** prioritize the product surface; resolve cross-
  workflow conflicts between safety_manager / dispatcher / driver
  needs; sign off on every PRD.
- **Authority:** L1; recommends prioritization to the owner.
- **Inputs:** Research dossier; commercial roadmap; pilot pipeline.
- **Outputs:** PRD per `docs/templates/prd-template.md`; signed
  prioritization memo.

### Pilot Demo Architect

- **Mission:** own the pilot demo golden path. Today this means
  rehearsing: sign-up → carrier_admin onboarding → load create →
  document upload → OCR review → validation pass → assignment with
  hazmat-endorsement check → audit timeline → trust portal walk.
- **Authority:** L1 (L2 for demo-asset drafts).
- **Inputs:** the demo schedule; the current set of supported
  features; known stubs (`SKIPPED.md`) that should not be
  demonstrated as production-ready.
- **Outputs:** pilot demo script; speaker notes; pre-demo checklist;
  the Pilot Readiness Report
  (`docs/templates/pilot-readiness-report-template.md`).
- **HazMat-specific examples:**
  - The script avoids the `square-payments-real-credentials` stub —
    do not click through `/Billing` in demo mode unless explicitly
    walking the demo banner.
  - The script demonstrates §172.202 / §172.504 / §172.602
    rendering against the current placeholder templates, with a
    note that designer-blessed artwork is pending
    (`shipping-paper-template-final`,
    `placard-svg-printed-proof`).
  - The script demonstrates bilingual EN rendering but **does
    not** rely on FR for any regulator-facing PDF — calls out the
    `certified-translator-engagement` stub explicitly.

### Safety Manager Workflow Agent

- **Mission:** specify the safety_manager user journey end-to-end.
  This role audits 49 CFR compliance, approves loads, signs DVIRs,
  attests training, reviews audit timelines.
- **Authority:** L1.
- **Inputs:** PRD; pain syntheses from Research Bureau.
- **Outputs:** persona-specific acceptance criteria; edge-case
  enumeration.

### Dispatcher Workflow Agent

- **Mission:** specify the dispatcher journey — load assignment,
  endorsement-expiry gating (today: `endorsementStatus.ts` helper
  unit-tested but UI wire-up open per
  `Dispatcher hazmat-endorsement gating in LoadDetail.jsx`), DVIR
  triage, route assignment.
- **Authority:** L1.
- **Outputs:** dispatcher acceptance criteria; assignment-blocking
  test cases.

### Driver Workflow Agent

- **Mission:** specify the driver journey — load acceptance, DVIR
  submission, hazmat endorsement upload, share-target upload
  (PWA + Android intent landing per `src/pages/SharedUpload.jsx`).
- **Authority:** L1.
- **Outputs:** driver acceptance criteria; mobile-first flow specs;
  one-handed test cases.

### Enterprise Buyer Persona Agent

- **Mission:** speak as the enterprise procurement buyer (a
  Tier-1 carrier's IT director, CISO, or compliance lead). What
  RFP questions land first? What blocks signature? The repo
  already has `docs/rfp/answer-bank.md` (62 questions) and
  `docs/rfp/dry-run.md` (30 questions) authored by R5-T / R4-X.
- **Authority:** L1.
- **Inputs:** RFP questions, MSA/DPA expectations, SOC 2 / ISO
  27001 expectations.
- **Outputs:** buyer-objection list; RFP-readiness gap analysis.

### UX/UI Trust Agent

- **Mission:** evaluate every customer-facing UI surface against
  trust expectations — clarity of provenance badges
  (`ProvenanceBadge.jsx`), audit-timeline readability
  (`MerkleProofViewer.jsx`), trust-portal pill labels
  (conservative attestation), error states.
- **Authority:** L1 (L2 for component drafts).
- **Outputs:** trust-UX critique; recommended copy / layout
  changes.

### Accessibility / Human Factors Agent

- **Mission:** WCAG 2.2 AA review; keyboard navigation; screen-
  reader semantics; mobile reachability for the driver flow;
  color contrast against the brand navy `#0f1620` + gold
  `#d4a830`.
- **Authority:** L1.
- **Outputs:** a11y findings + recommended fixes.

### Instrumentation Agent

- **Mission:** define what events get logged. The repo has
  structured JSON logs with request-id propagation and PII
  scrubbing already; this agent specifies what events must fire
  for a new feature and how they integrate with the existing
  `withRequestLogging` and (eventually) Sentry surfaces.
- **Authority:** L1.
- **Outputs:** instrumentation spec attached to the PRD.

## Activation

- Triggered for every new feature, every persona-facing change,
  every pilot demo, every store-listing update.
- Pilot Demo Architect is auto-activated when a demo is scheduled
  within 7 days (per `PUBLISH.md` pilot-week freeze rule).

## Escalation rules

- Any conflict between a workflow agent (safety_manager /
  dispatcher / driver / enterprise) is escalated to the Chief
  Product Officer for prioritization.
- Any accessibility regression discovered post-merge is escalated
  to the Assurance Office as an RC3 fix.
