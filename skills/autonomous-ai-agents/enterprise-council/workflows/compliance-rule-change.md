# Workflow — Compliance Rule Change

## Trigger

A 49 CFR / TDG regulation update, a PHMSA enforcement
clarification, an internal audit finding, an ISO 27001 control
status change, or a customer/RFP question that surfaces a
compliance gap.

## Required Divisions

Executive Command, Research Bureau (49 CFR / TDG / Security
Standards), Engineering Factory (Compliance Engine), Assurance
Office (Compliance Evidence + Independent QA), Legal Office
(Claims Substantiation if any public claim affected).

## Required Research Artifact

Research Dossier with primary-source citations from 49 CFR / TDG
/ NIST / ISO is mandatory.

## Agent Topology

Prompt chain with parallel review at verify.

## Sequence

1. **Intake** — Chief Orchestrator confirms the rule change
   scope.
2. **Citation** — 49 CFR / TDG / Security Standards Research
   produces the dossier (`49cfr-rule-audit` skill, etc.).
3. **Coverage audit** — Compliance Engine Engineer maps the
   citation to current code and tests.
4. **Implement** — code + test additions.
5. **Renderer regression** — `document-renderer-regression-
   review` skill confirms regulator-facing builders still
   pass.
6. **Evidence update** — Compliance Evidence Agent updates the
   matrix (`compliance-evidence-matrix-build`) and SoA where
   relevant.
7. **Claims check** — Claims Substantiation Agent confirms no
   public claim contradicts the new posture.
8. **Verify + go-no-go** — Independent QA + go-no-go review.
9. **Owner publish + G4**.

## Parallelization Opportunities

- Citation + Coverage audit can run in parallel.
- Renderer regression + Evidence update can run in parallel.

## Maker-Checker Review Points

- Builder: Compliance Engine Engineer.
- Reviewer: Independent QA.
- Verifier: Compliance Evidence Agent.

## Final Outputs

Research Dossier · Code + tests · Updated SoA / risk register ·
Updated `docs/rfp/answer-bank.md` if questions affected ·
Retrospective.

## Acceptance Criteria

- Tests green including new coverage.
- No regulator-facing builder regression.
- SoA matches new posture.
- No conflicting public claim.
