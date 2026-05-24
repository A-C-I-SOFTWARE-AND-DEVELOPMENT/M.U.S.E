# 00 — HazMat Command Autonomous Enterprise Organization Overview

**Status:** Installed 2026-05-17
**Owner:** `@echerd27-design`
**Supersedes:** nothing (additive to `AGENTS.md`, `PUBLISH.md`,
`SKIPPED.md`)

## Mission

The HazMat Command Autonomous Enterprise Organization (the "AEO") is
a repository-native operating system that allows future AI agent
sessions to behave like a disciplined commercial-grade software
company while building, securing, and selling HazMat Command — without
destabilizing production code or compromising pilot/demo readiness.

The AEO is not new application functionality. It is a layer of
documentation, registries, templates, and lightweight tooling that
turns implicit governance (already proven across Rounds R1-D through
R5-V) into explicit governance future sessions can pick up cleanly.

## What HazMat Command needs from the AEO

HazMat Command serves hazardous-materials carriers operating under
49 CFR Subchapter C (US) and TDG (Canada). Its v1.0.0-enterprise-ready
release delivered:

- regulator-facing document builders (§172.202 shipping paper,
  §172.504 placard sheet, §172.602 ERG sheet, §396.11 DVIR,
  §172.704(d) training dossier);
- a hash-chained tamper-evident audit ledger with nightly Merkle
  anchoring to RFC 3161 TSA and OpenTimestamps (stubbed pending
  procurement);
- WorkOS SSO with real RS256 JWKS verification, TOTP + WebAuthn MFA
  enrollment UI, SCIM 2.0;
- row-level-security migrations + 1,000-iteration cross-tenant fuzz;
- bilingual EN/FR rendering with certified-translator pipeline;
- 12-runbook operational set;
- ISO 27001:2022 scaffolding, NIST 800-53 mapping, DPA/SCC/CCPA
  disclosures, 62-Q RFP answer bank.

What it does **not** yet have, until this AEO install:

- a research-before-plan discipline;
- a published agent authority matrix;
- a maker-checker rule for high-risk changes;
- a workflow router so the right topology is chosen per task;
- a commercial-claims substantiation policy;
- a legal-document generation policy with counsel-review banners;
- a central index;
- a skill library a new session can pick up.

The AEO closes those gaps without rewriting the product.

## What the AEO can do

Through orchestrated agents and human owner gates, the AEO operates
like a software company with the following capabilities:

1. **Research** — produce evidence-based research dossiers before any
   non-trivial design or commercial decision
   (`docs/governance/05-research-dossier-standard.md`).
2. **Design** — convert research into PRDs, ADRs, and threat models
   using the templates in `docs/templates/`.
3. **Build** — execute engineering work through the Engineering &
   Architecture Factory division
   (`docs/agents/04-engineering-and-architecture-factory.md`).
4. **Verify** — run independent assurance through the Assurance Office
   (`docs/agents/05-assurance-security-reliability-compliance-office.md`)
   under a maker-checker rule
   (`docs/governance/06-maker-checker-independent-review.md`).
5. **Market without overclaiming** — draft GTM, positioning, and
   campaign material with the Commercial Office
   (`docs/agents/06-commercial-strategy-pricing-growth-office.md`)
   under the substantiation policy
   (`docs/governance/11-commercial-claims-substantiation-policy.md`).
6. **Price from evidence** — produce pricing studies via the
   `b2b-saas-pricing-study` and `carrier-roi-model` skills.
7. **Draft legal documents with counsel-required controls** — through
   the Legal Office
   (`docs/agents/07-legal-policy-contracts-trust-office.md`) under
   the legal-document policy
   (`docs/governance/12-legal-document-generation-policy.md`).
8. **Prepare pilots and enterprise procurement** — via the
   `pilot-demo-readiness` and `enterprise-procurement-readiness`
   workflows.
9. **Maintain auditability and knowledge continuity** — via the
   Knowledge Operations division
   (`docs/agents/09-knowledge-operations-and-self-improvement.md`)
   and the artifact registry
   (`docs/governance/08-artifact-registry-and-memory-discipline.md`).
10. **Improve itself** — every major run leaves behind updated
    artifacts, lessons learned, doc-freshness corrections, and any
    governance updates warranted by what was discovered
    (`docs/governance/15-doc-freshness-and-contradiction-control.md`).

## Design philosophy

Six principles bind every doc in this operating system. They are
restated in `AGENTS.md` and elaborated in the rest of the
`docs/governance/` set.

1. **Persona ≠ Agent ≠ Subagent ≠ Skill ≠ Tool ≠ Artifact.** Each
   has a distinct definition (see AGENTS.md §Taxonomy) so future
   sessions can route work cleanly.
2. **Research before plan.** Non-trivial decisions begin with a
   research dossier or a documented reason a lightweight version
   suffices.
3. **Minimum adequate workflow topology.** Use a single specialist
   by default; escalate to multi-agent topologies only when
   complexity warrants it.
4. **Maker-checker separation.** Anything that touches compliance,
   security/authz, tenant isolation, pricing, legal output, release
   policy, or high-risk commercial claims requires an independent
   reviewer who did not build the change.
5. **Commercial claims require substantiation.** Every public claim
   maps to evidence or is labeled aspirational.
6. **The system improves itself.** Every major run produces an
   artifact-registry update and a retrospective.

## How the AEO interacts with owner authority

The AEO never overrides the five owner-only walls or the two-gate
preview-before-publish flow established in `AGENTS.md`. Agent
authority tops out at L3; L4 (owner-only) actions remain owner-only
and tool-trust T6 capabilities are never granted to agents.

Specifically, agents:

- never push, force-push, or merge to `main`/`master`;
- open PRs as draft only;
- never call `mcp__github__merge_pull_request`,
  `mcp__github__enable_pr_auto_merge`, or `gh pr merge`;
- never spend money, post to public social accounts, create
  third-party accounts, OAuth into third parties, or submit to app
  stores;
- never alter production DNS or promote Vercel to production;
- never click Publish in Base44 Builder.

The AEO simply makes the discipline that produced the v1.0.0 release
reproducible, scalable, and auditable across future sessions.

## How the AEO relates to AGENTS.md / PUBLISH.md / SKIPPED.md

- **AGENTS.md** is the constitution. It contains the owner-only
  walls, the two-gate flow, the taxonomy, the authority and risk and
  tool-trust headlines, and the links into this operating system.
  This overview elaborates AGENTS.md; it does not replace it.
- **PUBLISH.md** is the release playbook. The AEO extends it with
  G0–G4 release governance gates and pilot-week freeze rules without
  altering the original two-gate flow or rollback procedures.
- **SKIPPED.md** is the stub inventory. The AEO adds an additive
  deferred-risk schema (Risk Class, Release Severity, Default Safe?,
  Customer Visible?, Security Impact, Compliance Impact, Owner,
  Review Date, Exit Condition, Escalation Rule, Evidence Link) on
  every active entry. The bidirectional coverage CI gate
  (`tests/inventory/skipped-coverage.test.js`) is preserved exactly.

## Where to go next

- New autonomous session: read AGENTS.md → PUBLISH.md → SKIPPED.md →
  `docs/AUTONOMOUS_ORGANIZATION_INDEX.md`, then this overview.
- Need to understand source-of-truth resolution:
  `docs/governance/01-source-of-truth-hierarchy.md`.
- Need to decide what an agent can do:
  `docs/governance/02-agent-authority-matrix.md`.
- Need to decide test/review depth:
  `docs/governance/03-change-risk-matrix.md`.
- Need to pick a workflow topology:
  `docs/governance/04-workflow-router.md`.
