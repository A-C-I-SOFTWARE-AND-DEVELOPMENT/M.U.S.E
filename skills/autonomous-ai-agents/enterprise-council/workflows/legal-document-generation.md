# Workflow — Legal Document Generation

## Trigger

Any request for a legal document: ToS, Privacy Policy, NDA,
MSA, SOW, DPA, Pilot Agreement, Security Addendum, retention
policy, sub-processor notice, app-store disclosure, etc.

## Required Divisions

Legal Office (General Counsel Orchestrator + the relevant
drafting agent + Legal Consistency Auditor), Commercial Office
(if commercial terms involved), Assurance Office (Compliance
Evidence if compliance commitments involved).

## Required Research Artifact

Legal Document Intake using
`templates/legal-document-intake-template.md`. Research
Dossier required for any non-standard new document type.

## Agent Topology

Prompt chain.

## Sequence

1. **Intake** — General Counsel Orchestrator routes the request;
   files the intake template.
2. **Draft** — the relevant skill is invoked:
   - `privacy-policy-draft`, `terms-of-service-draft`,
     `nda-draft`, `pilot-agreement-draft`, `msa-sow-draft`,
     `dpa-draft`, `claims-substantiation-review`,
     `app-store-policy-audit`, `oss-license-review`
3. **Counsel-review banner** — mandatory per `governance/12`
   at the top of every draft.
4. **Consistency check** — Legal Consistency Auditor confirms
   no overclaim vs. current product, security, privacy, or
   commercial reality.
5. **Cross-domain review** — Commercial Office for terms;
   Compliance Evidence Agent for compliance commitments.
6. **Commit as draft** — file under `docs/compliance/` (or
   repo-appropriate path) with the banner.
7. **Owner-routed to qualified counsel** — counsel notes
   captured in the draft's revision history.
8. **Owner publishes / signs** (L4).

## Parallelization Opportunities

- Consistency check + Cross-domain review run in parallel.

## Maker-Checker Review Points

- Builder: drafting agent.
- Reviewer: Legal Consistency Auditor.
- Verifier: counsel via owner (the banner persists until counsel
  signs off).

## Final Outputs

Legal draft with banner · Consistency-check note · Cross-domain
review notes · Eventual counsel-reviewed version (owner-owned).

## Acceptance Criteria

- Counsel-review banner present and unmodified.
- No overclaim vs. capability / privacy posture / SLA.
- Cross-references resolve.
- Owner routes to counsel before any external use.
