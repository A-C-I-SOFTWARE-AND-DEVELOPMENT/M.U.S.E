# Workflow — New Product or Major Feature

## Trigger

Owner approves a new product or a major feature that adds a new
RC3 surface, a new public commercial claim, or a new pilot-
demoable capability.

## Required Divisions

Executive Command, Research & Evidence Bureau, Product & Pilot
Experience Studio, Engineering & Architecture Factory, Assurance
Office, Commercial Office, Legal Office, Knowledge Operations.

## Required Research Artifact

- Research Dossier (`governance/05` + `research-dossier-build`
  skill).
- PRD (`templates/prd-template.md`).
- Architecture Decision Record if the feature touches the SoR
  resolver / authz / audit ledger / OCR pipeline.
- Threat Model entry if the feature adds an attack surface.

## Agent Topology

Prompt chain with parallel review panels at the design and
verify stages.

## Sequence

1. **Intake** — Chief Orchestrator routes the request; files the
   intake template at `docs/templates/workflow-router-intake-
   template.md`.
2. **Research** — Research Bureau produces the dossier.
   - 49 CFR / TDG Research if the feature is regulator-facing
   - Security Standards Research if it changes the security
     model
   - Commercial Market Research if it changes positioning
3. **Specification** — Product Studio produces the PRD; persona
   workflow agents (safety_manager / dispatcher / driver /
   enterprise) contribute acceptance criteria.
4. **Legal pre-scan** — Legal Office checks whether the feature
   triggers a privacy / DPA / sub-processor / ToS update.
   Claims Substantiation Agent reviews any draft commercial
   claims.
5. **Architecture** — Engineering Factory writes the ADR;
   Principal Systems Architect signs off.
6. **Threat model** — Assurance Office (Threat Modeling Agent)
   adds the STRIDE entry.
7. **Build** — Engineering Factory implements; tests added per
   `negative-test-suite-generation` for RC3 surfaces.
8. **Verify** — Assurance Office Independent QA + the relevant
   verifier (Security Architect / Compliance Evidence / Claims
   Substantiation) per `governance/06`.
9. **Commercial activation** — Commercial Office finalizes
   positioning, packaging, pricing impact.
10. **Documentation** — Knowledge Operations updates AGENTS /
    SKIPPED / governance / index as needed; retrospective filed.
11. **G0–G3** — go-no-go review; owner publish.
12. **G4** — post-release stabilization 24h.

## Parallelization Opportunities

- Research streams (49 CFR + Security + Commercial) run in
  parallel.
- Legal pre-scan and Architecture run in parallel.
- Threat model and Build can begin in parallel once the ADR is
  signed.
- Commercial activation runs alongside Build/Verify.

## Maker-Checker Review Points

- PRD: Product Studio builder + CPO reviewer.
- ADR: Engineering Factory builder + Principal Architect
  reviewer.
- RC3 code: Engineering Factory builder + Independent QA
  reviewer + domain verifier.
- Commercial claim: Commercial builder + Claims Substantiation
  verifier.
- Legal draft: Legal builder + Consistency Auditor + counsel
  (via owner).

## Final Outputs

Research Dossier · PRD · ADR · Threat Model entry · Test
additions · Compliance evidence updates if applicable · Claims
Substantiation memo · Legal draft if applicable · Updated
feature-flag registry · Updated index · Retrospective.

## Acceptance Criteria

- All 727 baseline tests still pass + new tests added.
- CI green (G1).
- Owner-reviewed in both preview surfaces (G2).
- Independent reviewer + verifier sign-off captured.
- No release-freeze trigger active.
- Pilot Readiness Judge sign-off if the feature is in the next
  pilot.
