# 08 — Artifact Registry and Memory Discipline

**Status:** Installed 2026-05-17

Chat memory and session context are not durable. Every RC2/RC3
agent run must leave behind durable artifacts so future agents can
audit decisions and reuse evidence.

## Required durable artifacts

| Artifact | Template | Lives at | Required when |
|---|---|---|---|
| Research Dossier | `docs/templates/research-dossier-template.md` | `docs/research/YYYY-MM-DD-<slug>.md` | RC3 work; new commercial claim; new vendor; new legal doc; new pricing decision; regulator-facing builder change; 49 CFR / TDG rule-engine change |
| PRD | `docs/templates/prd-template.md` | `docs/research/prds/<slug>.md` or workflow-specific path | New feature; major feature change |
| Architecture Decision Record | `docs/templates/architecture-decision-record-template.md` | `docs/research/adrs/<NNNN>-<slug>.md` | Architectural decision (e.g. SoR cutover, OCR provider swap, dependency removal) |
| Threat Model entry | `docs/templates/threat-model-template.md` (extension; main lives at `docs/security/threat-model.md`) | `docs/security/threat-model.md` (single growing doc) | RC3 security/authz/data change |
| Compliance Evidence Matrix | `docs/templates/compliance-evidence-matrix-template.md` | `docs/compliance/<scope>-evidence-matrix.md` or `docs/iso27001/` cross-references | RC3 compliance evidence change |
| Pricing Study | `docs/templates/pricing-study-template.md` | `docs/research/pricing/<YYYY-MM-DD>-<slug>.md` | Pricing or packaging decision |
| GTM Brief | `docs/templates/gtm-brief-template.md` | `docs/research/gtm/<YYYY-MM-DD>-<slug>.md` | Positioning / launch campaign |
| Claims Substantiation memo | `docs/templates/claims-substantiation-template.md` | `docs/research/claims/<YYYY-MM-DD>-<slug>.md` | Any externally-visible claim per `governance/11` |
| Legal document draft | `docs/templates/legal-document-intake-template.md` (intake) → final draft in `docs/compliance/` or repo-appropriate path | per draft | Any legal doc per `governance/12` |
| Pilot Readiness Report | `docs/templates/pilot-readiness-report-template.md` | `docs/research/pilots/<YYYY-MM-DD>-<pilot>.md` | Before every pilot demo |
| Agent Run Retrospective | `docs/templates/agent-run-retrospective-template.md` | `docs/research/retros/<YYYY-MM-DD>-<slug>.md` | After every RC2/RC3 run |
| Workflow Router Intake | `docs/templates/workflow-router-intake-template.md` | filed alongside the artifact it produced | Recommended for orchestrator-worker / parallel-review topologies |

## Index requirement

Benchmark-class artifacts (research dossiers like
`docs/research/autonomous-enterprise-organization-benchmark-2026-
05-17.md`, major ADRs, significant claims memos) are linked from
`docs/AUTONOMOUS_ORGANIZATION_INDEX.md` so future sessions can
discover them. The Agent OS Librarian (`docs/agents/09`) maintains
the index.

## Naming convention

`YYYY-MM-DD-<short-kebab-slug>.md`. The date is the publication
date (not the file-creation date). Slugs are descriptive enough to
read in `git log` (`pricing-team-plan-79-to-99` not `pricing-v2`).

## Linking discipline

- Every artifact references the PR that produced it.
- Every PR that requires an artifact links to it from the
  template's "Research artifacts" field.
- Cross-artifact references use repo-relative paths with backticks.
- External sources are cited by URL **and** captured publication
  date (URLs rot).

## Why memory discipline matters here specifically

The AEO has already produced 4+ Round sprints (R1-D through R4-X)
plus subsequent R5-T/R5-U/R5-V scaffolding. Without durable
artifacts a new session has no way to discover:

- Why the SoR resolver was designed env-flag-driven rather than
  config-file-driven (R4-X decision).
- Why bilingual rendering treats FR as "draft-not-certified" until
  CTTIC/OTTIAQ/ATIO sign-off (R4-Q decision).
- Why the SKIPPED.md retrofit was additive rather than a schema
  rewrite (this install's decision, captured in
  `docs/research/autonomous-enterprise-organization-benchmark-
  2026-05-17.md`).

A `git log` is a poor substitute for an ADR.

## Anti-patterns

- Capturing important decisions only in commit messages or chat
  threads — they vanish from future agent context.
- Writing a research dossier and then making a different decision
  in the implementation without updating the dossier.
- Letting `docs/research/` become a write-only graveyard. The Doc
  Freshness Auditor periodically prunes / archives.
- Naming artifacts with cryptic slugs (`memo-3-final-FINAL.md`).
