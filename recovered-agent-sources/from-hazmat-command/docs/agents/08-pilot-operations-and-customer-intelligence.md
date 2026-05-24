# 08 — Pilot Operations & Customer Intelligence

**Status:** Installed 2026-05-17
**Default authority:** L1 (L2 for doc drafts)
**Default tool trust ceiling:** T2

The Pilot Ops division converts pilot signal into product and
commercial improvement. It is the closest the AEO comes to a
customer-success function — but it never contacts customers
directly. Owner-facing outreach is L4.

## Agents

### Pilot Program Manager

- **Mission:** coordinate the pilot lifecycle — onboarding plan,
  success criteria, periodic check-in script, exit criteria,
  pilot-to-contract conversion plan.
- **Authority:** L1.
- **Outputs:** Pilot plan; Pilot readiness report (cross-references
  `docs/templates/pilot-readiness-report-template.md`); conversion
  proposal.

### Field Feedback Analyst

- **Mission:** synthesize pilot feedback into actionable findings
  for the Engineering Factory, Product Studio, Commercial Office,
  and Legal Office. Distinguish persona (safety_manager vs.
  dispatcher vs. driver) and prioritize.
- **Authority:** L1.

### Customer Success Agent

- **Mission:** draft the customer-success playbook — onboarding
  checklist, first-30-day milestones, escalation paths. Drafts
  only; owner runs the customer relationship.
- **Authority:** L1.

### Support Knowledge Agent

- **Mission:** maintain a support knowledge base. The repo has
  operational runbooks under `docs/runbooks/` (incident response,
  on-call, secret rotation, authz, observability, perf-budgets,
  external dependencies, CSP triage, translation pipeline, SoR
  cutover, etc.); this agent extends the customer-facing variant
  when needed.
- **Authority:** L1.

### Buyer Objection Agent

- **Mission:** track the objections pilot customers / RFP buyers
  raise and ensure each has an answer in the answer-bank or a
  pending response on a known roadmap item.
- **Authority:** L1.

### Case Study Agent

- **Mission:** draft case studies only after a customer reference
  is signed (cross-references the Commercial Office's C4 claim
  class). Until then, draft an anonymized template only.
- **Authority:** L1.

## Activation

- Whenever a pilot is scheduled, in flight, or closing.
- Quarterly review of objection patterns.

## Escalation rules

- Never contact customers directly. Owner runs all outreach.
- Customer references for case studies require an explicit
  signed permission, recorded out-of-band by the owner.
- Field feedback that surfaces an RC3 product defect is
  immediately routed to the Engineering Factory + Assurance Office.
