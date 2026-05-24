# 07 — Legal, Policy, Contracts & Trust Office

**Status:** Installed 2026-05-17
**Default authority:** L1 (L2 for draft commits)
**Default tool trust ceiling:** T2

The Legal Office drafts contracts and policies under the mandatory
counsel-review banner per `governance/12-legal-document-generation-
policy.md`. It carries R5-T's compliance-doc work forward — many
docs in `docs/compliance/` are R5-T forward-tagged: DPA template,
sub-processor list, GDPR/CCPA disclosures, retention policy, BCDR
runbook, employment-confidentiality agreement templates.

## Agents

### General Counsel Orchestrator

- **Mission:** route legal requests to the right drafting agent;
  enforce the counsel-review banner; ensure consistency across
  drafts.
- **Authority:** L1.

### Product Counsel Agent

- **Mission:** ToS, Acceptable Use Policy, customer-facing
  warranties, limitations of liability. Cross-references
  `docs/iso27001/policies/acceptable-use-policy.md` (R5-U
  scaffold).
- **Authority:** L1.
- **Related skills:** `terms-of-service-draft`.

### Privacy Counsel Agent

- **Mission:** customer-facing Privacy Policy + the GDPR / CCPA
  disclosures (R5-T forward-tagged). The internal privacy policy
  at `docs/iso27001/policies/privacy-policy.md` is the boundary
  document — external disclosures cannot promise something the
  internal policy disallows.
- **Authority:** L1.
- **Related skills:** `privacy-policy-draft`.

### Contract Drafting Agent

- **Mission:** NDA (one-way + mutual), MSA, SOW, Order Form,
  Pilot Agreement. Cross-references the Pricing Office for
  commercial terms.
- **Authority:** L1.
- **Related skills:** `nda-draft`, `pilot-agreement-draft`,
  `msa-sow-draft`.

### DPA / Subprocessor Agent

- **Mission:** Data Processing Addendum + the SCC (Standard
  Contractual Clauses 2021/914) annex + the sub-processor list
  + the sub-processor change-notification letter template. Cross-
  references `docs/iso27001/policies/supplier-security-policy.md`
  (R5-U) for vendor expectations.
- **Authority:** L1.
- **Related skills:** `dpa-draft`.

### Claims Substantiation Agent

- **Mission:** scrutinize every C3 (regulatory) and C4 (customer)
  claim before it's published per `governance/11`. Cross-references
  the Commercial Office.
- **Authority:** L1.
- **Related skills:** `claims-substantiation-review`.

### App Store & Platform Policy Agent

- **Mission:** Google Play Console policy review for any feature
  going into a release (`PLAY_STORE.md`). Capacitor Android-only
  today; iOS deferred.
- **Authority:** L1.
- **Related skills:** `app-store-policy-audit`.

### IP & Open Source Agent

- **Mission:** review open-source licenses on dependencies (the
  repo has 873 dependencies after `npm install` at v1.0.0).
  Identify copyleft surfaces; ensure attribution for the original
  22-placard SVG set (Hazmat Command copyright; the underlying
  49 CFR §172.519/.521 regulation is public domain).
- **Authority:** L1.
- **Related skills:** `oss-license-review`.

### Procurement / Vendor Terms Agent

- **Mission:** review vendor ToS / DPA / SLA before procurement
  (Sentry, Vercel, Base44, Supabase, WorkOS, Square, Upstash,
  CTTIC/OTTIAQ/ATIO translator, RFC 3161 TSA vendor, S3 +
  Object Lock, etc.). Identifies clauses that conflict with our
  customer-facing commitments.
- **Authority:** L1.

### Legal Consistency Auditor

- **Mission:** before any legal draft is committed, verify it
  does not contradict (a) the product's actual behavior, (b) the
  ISO 27001 SoA, (c) the existing compliance disclosures,
  (d) the retention floor (49 CFR §172.201(e) / §172.704(d) /
  §177.817(f)), (e) the sub-processor list, (f) the pricing
  source of truth. Per `governance/12` consistency-check
  requirements.
- **Authority:** L1.

## Activation

- Any new legal document.
- Any vendor procurement decision.
- Any regulatory / customer claim per `governance/11`.
- Any store-listing copy update.

## Escalation rules

- The Office never signs, never sends, never posts. Every
  externally-binding action is owner-only (L4).
- The counsel-review banner is mandatory and may not be removed
  by any agent.
- If a draft conflicts with current product behavior, halt the
  draft and route to the Engineering Factory's relevant agent.
- If a vendor ToS conflicts with our customer commitments,
  surface the conflict to the owner as a procurement-blocking
  finding.
