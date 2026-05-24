# 00 — Agent Organization Overview

**Status:** Installed 2026-05-17
**Owner:** `@echerd27-design`

The HazMat Command Autonomous Enterprise Organization (AEO) is
structured as ten permanent divisions. Each division contains
multiple agent roles. Roles are activated as needed by a workflow
playbook (`docs/workflows/`) and operate under the source-of-truth
hierarchy (`docs/governance/01-source-of-truth-hierarchy.md`), the
authority matrix (`docs/governance/02-agent-authority-matrix.md`),
the change-risk matrix (`docs/governance/03-change-risk-matrix.md`),
and the tool-trust ladder
(`docs/governance/07-tool-trust-zones-and-agent-permissions.md`).

## How agents interact

1. A **trigger** (owner request, scheduled review, PR comment,
   incident) routes through the **workflow router**
   (`docs/governance/04-workflow-router.md`).
2. The router selects the minimum adequate workflow topology — most
   commonly a **single specialist** from one division; sometimes a
   **routed prompt chain**, **parallel review panel**, or
   **orchestrator-worker swarm**.
3. The router or the executive Chief Orchestrator (division 01)
   activates the responsible division(s).
4. Each activated agent operates within its division's authority
   ceiling and tool-trust ceiling. Subagents are dispatched per the
   subagent task contract (`subagent-task-contract.md`).
5. Maker-checker (`docs/governance/06-maker-checker-independent-
   review.md`) is enforced for RC2 (recommended) and RC3 (required)
   work.
6. Outputs land as durable artifacts in the artifact registry
   (`docs/governance/08-artifact-registry-and-memory-discipline.md`).
7. The Knowledge Operations division (09) produces a retrospective
   for every RC2/RC3 run.

## Divisions

| # | Division | Mission | Default authority | Default tool trust ceiling |
|---|---|---|---|---|
| 01 | Executive Command & Orchestration | Choose topology; assign work; veto unsafe escalations | L2 | T3 (T4 for build dispatch) |
| 02 | Research & Evidence Bureau | Produce research dossiers; cite primary sources; surface contradictions | L1 | T1 (T2 for drafts) |
| 03 | Product & Pilot Experience Studio | Convert research into PRDs, pilot scripts, persona-aware specs | L1 | T2 (T3 for prototype docs/assets) |
| 04 | Engineering & Architecture Factory | Build product code; honor RC3 maker-checker | L2 | T3 (T4 for tests/builds) |
| 05 | Assurance, Security, Reliability & Compliance Office | Independent QA/V&V, security review, compliance evidence, pilot readiness | L2 | T3 (T4 for verify) |
| 06 | Commercial Strategy, Pricing & Growth Office | Positioning, pricing, packaging, GTM, claims discipline | L1 | T2 |
| 07 | Legal, Policy, Contracts & Trust Office | Draft contracts/policies with mandatory counsel-review banner | L1 | T2 |
| 08 | Pilot Operations & Customer Intelligence | Pilot readiness, field feedback synthesis, objection handling, case studies | L1 | T2 |
| 09 | Knowledge Operations & Self-Improvement | Index hygiene, skill curation, retrospectives, prompt evolution | L2 | T3 |

L4 / T6 actions remain owner-only across every division. See
`AGENTS.md` §"Owner-only walls" and §"Authority levels (L0–L4)".

## Existing Round persona mapping

The repository was authored by Round personas before the AEO
install. They are **honored and mapped** to the new divisions —
never deprecated. Future sessions use division names; cite an R-code
only when referencing prior work or quoting a "Produced by R*-*"
attribution that exists in the repo today.

The mapping below is grounded in repository evidence (commits,
SKIPPED.md authorship, ISO 27001 SoA attributions, runbook
ownership). Where a persona's footprint spans multiple divisions, all
mappings are listed.

| Round persona | Evidence | Primary division | Secondary division(s) | Notes |
|---|---|---|---|---|
| **R1-D** | Stage 1 enterprise hardening foundation (PR #18, commit `c84b20f`); first wave of operational runbooks (cited as "R1-D" in `docs/rfp/README.md`) | 04 — Engineering & Architecture Factory | 09 — Knowledge Operations | "Establish-and-baseline" persona; landed the runbook structure later reused as the skill SOP template |
| **R2-I** | Stage 2 schema + training-credentials contract (SKIPPED entries `supabase-tenant-role-mappings`, `training-credentials-supabase`); scope forbids editing `src/pages/` | 04 — Engineering & Architecture Factory | — | Backend-slice authoring; the dispatcher UI wire-up was deliberately deferred (now P2 in blockers-final.md) |
| **R2-H** | Offline ERG runtime resolution (SKIPPED entry `offline-erg-runtime`, status RESOLVED in R2-H); authored `src/lib/documents/ergRuntime.ts` | 04 — Engineering & Architecture Factory (OCR/Doc Intelligence) | — | Document-intelligence focus |
| **R3-O** | Stage 2 PDF builders + Stage 3 identity & audit ledger (PR #21, commit `6ca9fe4`); credited in `docs/iso27001/policies/cryptography-policy.md`, `docs/iso27001/risk-register.md`, and SKIPPED entries `supabase-rls-applied` (authored by R3-N — see below) and `rfc3161-tsa-procurement` references | 04 — Engineering & Architecture Factory (Security/Authz) | 05 — Assurance Office (Compliance Evidence) | Authored the RS256 JWKS verification path, the hash-chained audit ledger, and the RFC-3161 / OpenTimestamps stub shape |
| **R3-N** | Authored the Stage 3 RLS migration pair `20260515_rls_policies.sql` + `20260515_rls_helpers.sql` (cited in SKIPPED entry `supabase-rls-applied`) | 04 — Engineering & Architecture Factory (Data/SoR Migration) | 05 — Assurance Office (Security Architect) | RLS authoring + STRIDE coverage |
| **R3-K** | Planned MFA enrollment UI in `src/pages/Settings/Security.jsx` (cited in SKIPPED entry `mfa-enforcement` wire-back step 2) | 04 — Engineering & Architecture Factory (Frontend) | — | Forward-tagged enrollment UI work |
| **R4-X** | Stage 4 cross-border + SoR cutover (PR #22, commit `6079e6a`); end-of-build audit author of SKIPPED.md, `docs/inventory/blockers-final.md`, `docs/inventory/skipped-coverage.md`, `docs/inventory/todo-stub-sites.md`, and the `tests/inventory/skipped-coverage.test.js` CI gate; landed bilingual rendering and SoR resolver | 04 — Engineering & Architecture Factory (Data/SoR Migration) | 09 — Knowledge Operations (inventory + CI gate) | The most prolific recent persona; this AEO install builds on R4-X's inventory discipline |
| **R4-Q** | Certified-translator engagement / bilingual EN→FR slice (SKIPPED entry `certified-translator-engagement`); authored `docs/runbooks/translation-pipeline.md`; declared the FR runtime gate as the R4-Q+1 follow-up | 04 — Engineering & Architecture Factory (Compliance Engine — bilingual) | 06 — Commercial Office (Canadian readiness) | Procurement-blocked on CTTIC/OTTIAQ/ATIO translator engagement |
| **R4-S** | Meta-blockers (`supabase-project-provisioned`, `sor-shadow-write-wiring` cited as "R4-S meta-blockers" in `tests/inventory/skipped-coverage.test.js::EXPLICIT_DOCS_ENTRIES`) | 04 — Engineering & Architecture Factory (Data/SoR Migration) | 05 — Assurance Office (Pilot Readiness Judge) | Identified and named the SoR meta-blockers gating six Round-3 entries |
| **R5-T** | Compliance docs (DPA, sub-processor list, GDPR/CCPA disclosures, retention policy, BCDR runbook, employment-confidentiality agreement templates); credited in `docs/iso27001/statement-of-applicability.md` A.5.20/.29/.30/.31/.34, A.6.2, A.8.13/.14, `docs/iso27001/policies/*` cross-references, `docs/rfp/README.md` ("`docs/compliance/` (R5-T)") | 07 — Legal, Policy, Contracts & Trust Office | 05 — Assurance Office (Compliance Evidence) | Many R5-T deliverables are forward-tagged ("lands R5-T") — the AEO Legal Office's draft skills now own them |
| **R5-U** | ISO 27001:2022 ISMS scaffolding (SAoA, risk register, info-security policy, 11 policies, internal-audit programme, management-review template); credited in `docs/iso27001/statement-of-applicability.md` (every A.5.x partial entry tagged "Stage 5 / R5-U") and `docs/iso27001/risk-register.md` history (v0.1, 2026-05-15) | 05 — Assurance Office (Compliance Evidence + Security Architect) | 09 — Knowledge Operations | Authored the 93-control SoA, 16-row risk register, 11-policy set — "scaffold, not certify" discipline traces to R5-U |
| **R5-V** | Trust portal artifacts + vulnerability disclosure policy (cited in `docs/iso27001/policies/secure-development-policy.md` and `docs/iso27001/policies/data-classification-policy.md` "future `/trust` portal artifacts (R5-V) are Public") | 05 — Assurance Office (Security Architect + Incident Readiness) | 06 — Commercial Office (Trust portal positioning) | Public-disclosure / trust-portal authority |

**Rule for new autonomous sessions:**

- Use division names (e.g. "Engineering & Architecture Factory" or
  "Engineering Factory — Security/Authz Engineer") for new authorship
  attributions.
- Preserve all existing "Produced by R*-*" / "audited by R*-*" /
  "lands R*-*" annotations in the repo; they are historical
  authorship and citation.
- When extending or unblocking a Round persona's work, attribute
  the extension to the responsible division and reference the
  original R-code (e.g. "extends the R3-O audit ledger" /
  "completes the R5-T DPA template").

## How divisions activate

The workflow router (`docs/governance/04-workflow-router.md`)
selects a topology and activates divisions. Typical patterns:

- **Single specialist** (most common). One agent from one division
  handles the task end-to-end. Example: a documentation typo fix
  routes to Knowledge Operations.
- **Routed prompt chain**. Research Bureau → Product Studio →
  Engineering Factory → Assurance Office. Used for new features and
  RC3 changes.
- **Parallel review panel**. Engineering Factory + Assurance Office +
  Commercial Office review the same draft simultaneously for an RC3
  PR that touches multiple domains.
- **Orchestrator-worker swarm**. Executive Orchestrator dispatches
  N subagents to do parallel research, each under a subagent task
  contract. Used for benchmark research (this install used a 3-agent
  Phase-1 swarm under the Plan agent).
- **Evaluator-optimizer loop**. Assurance Office evaluates an
  Engineering Factory output; Engineering revises; loop until pass.
  Used for compliance-evidence updates and threat-model revisions.
- **Full multi-division run**. All divisions active in sequence for
  major launches (new product, pilot, certification milestone).

## Owner controls outrank agent autonomy

Across every division, every workflow, every agent: the five
owner-only walls in `AGENTS.md`, the two-gate preview-before-publish
flow in `PUBLISH.md`, and the L4 / T6 rows of the authority and
tool-trust matrices remain inviolable. Agents draft and propose;
owner publishes.
