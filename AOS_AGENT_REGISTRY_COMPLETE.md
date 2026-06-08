# AOS Agent Registry — Complete

> **Generated:** 2026-05-24 from `categorized-roles.tsv`. Companion files:
> `AOS_SUBAGENT_REGISTRY_COMPLETE.md`, `AOS_FULL_SOURCE_INVENTORY.md`,
> `AOS_DUPLICATE_AND_CONFLICT_REPORT.md`. Every distinct frontmatter `name:` from a
> SKILL.md or agent .md across both repos is here — nothing is collapsed.
>
> Three buckets per category, per the owner-confirmed scope:
> - **Canonical** — the file with the most complete role text. First occurrence wins.
> - **Aliases** — other files defining the same `name:` (a true duplicate or a variant).
> - **Mentioned** — names that appear without a complete frontmatter — recorded for posterity,
>   not promoted to canonical. (See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` for the deeper sub-agent set.)
>
> Recovery labels for each entry:
> - `DIRECTLY RECOVERED` — frontmatter `name:` is present and the file is the canonical spec.
> - `PARTIALLY RECOVERED` — a frontmatter name exists but the spec is thin or a stub.
> - `RECONSTRUCTED FROM CONTEXT` — name extracted from a containing doc (no standalone spec).
> - `NEEDS USER REVIEW` — categorization or role text could not be confidently assigned.

**Distinct names registered:** 233
**Total entries (incl. duplicates across sources):** 248

> **Routed-catalog tally, not a file count** (WC-4 honesty propagation,
> following FU-18). The 233 figure counts distinct frontmatter `name:`
> entries across both source repos — canonical, alias, *and* mentioned
> buckets, plus reconstructed-from-context entries. It is **not** 233
> standalone council-agent files. On disk, the installed pack at
> `skills/aos-enterprise-council/agents/` holds **261** `.md` files, of
> which **177** are the general `agents/hermes/` skill library
> (`1password.md`, `arxiv.md`, …), not council agents — leaving **~84**
> genuine council category agents across the 16 non-`hermes` category
> folders. The registries route to specs that may be defined inline,
> reconstructed from context, or shared with the general skill library.

## A. Executive / Operator Layer

### Canonical

- **`aos-council-director`** — Director: decomposes goal, dispatches AoS council, decides.
  - Canonical source: `recovered-agent-sources/from-hermes-agent/aos-council-director/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`aos-full-agent-team`** — Full AoS council: spin up all 16 specialists end-to-end.
  - Canonical source: `recovered-agent-sources/from-hermes-agent/aos-full-agent-team/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`chief-orchestrator`** — Top-level coordinator for HazMat Command. Use proactively whenever a session spans multiple domains (engineering + security + compliance + commercial + legal + release), or whenever the request is ambiguous about whic...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/agents/chief-orchestrator.md`
  - Source repo / subsystem: `hazmat-agent` / `snapshot-agents`
  - Confidence: `DIRECTLY RECOVERED`
- **`execution-blueprint-compile`** — Use after owner approves the revised synthesized master plan. Converts the approved plan into the implementation contract — epics, waves, PR sequence, subagent assignments, Codex packets, validation commands, acceptan...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/execution-blueprint-compile/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`full-autonomous-sprint-router`** — Use at the start of a multi-domain or ambiguous request to classify the work, route to the right workflow and subagents, and avoid overbuilding. Inspects the request, names the risk class, picks the workflow, names th...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/full-autonomous-sprint-router/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`master-plan-synthesis`** — Use after plan-comparison-scorecard. Produces 04-synthesized-plan.md by curating surviving ideas into a single master plan, naming rejected ideas with rationale, and surfacing unresolved owner choices rather than sile...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/master-plan-synthesis/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`mission-brief-build`** — Use at the start of any Council Mode run or any substantive sprint that lands in a run folder under docs/aos/runs/. Produces 00-mission-brief.md by instantiating docs/templates/mission-brief-template.md. Restates owne...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/mission-brief-build/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`multi-plan-council-run`** — Manual-only. Owner-triggered. Dispatches N parallel plan-generation passes for Council Mode (Lite 3 / Standard 4–6 / RC3-strategy 6+) each under a distinct lens — Market Domination, Enterprise Trust, Product Experienc...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/multi-plan-council-run/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`plan-comparison-scorecard`** — Use after multi-plan-council-run produces N materially-distinct plans. Scores each plan 1–10 across the 10-criterion rubric in governance/16, extracts surviving ideas, rejected ideas, assumptions needing proof, contra...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/plan-comparison-scorecard/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`red-team-plan-review`** — Use after master-plan-synthesis. Independently attacks the synthesized master plan for amateur-feeling content, AI-theater, under-research, buyer/architect/security-lead objections, overbuild, under-build, unsupported...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/red-team-plan-review/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`

### Aliases

- **`aos-council-director`** (alias) — Director: decomposes goal, dispatches AoS council, decides.
  - Alternate source: `skills/aos-council-director/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.
- **`aos-full-agent-team`** (alias) — Full AoS council: spin up all 16 specialists end-to-end.
  - Alternate source: `skills/aos-full-agent-team/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § A. Executive / Operator Layer for names that appear in source bodies but lack their own frontmatter._

## B. Product Strategy Layer

### Canonical

- **`competitive-feature-harvester`** — Harvest competitor agent features into a Hermes backlog.
  - Canonical source: `skills/competitive-feature-harvester/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § B. Product Strategy Layer for names that appear in source bodies but lack their own frontmatter._

## C. Software Architecture Layer

### Canonical

- **`engineering-architecture-factory`** — Primary implementation agent for HazMat Command product code. Use for code changes to src/, api/, base44/, scripts/, supabase/, tests/, and CI workflows. Respects existing architecture, writes commercial-grade code an...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/agents/engineering-architecture-factory.md`
  - Source repo / subsystem: `hazmat-agent` / `snapshot-agents`
  - Confidence: `DIRECTLY RECOVERED`
- **`principal-systems-architect`** — Owns system architecture: components, interfaces, data flow.
  - Canonical source: `skills/principal-systems-architect/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § C. Software Architecture Layer for names that appear in source bodies but lack their own frontmatter._

## D. Security / Compliance Layer (Security)

### Canonical

- **`assurance-risk-director`** — Risk director: safety, security, legal, compliance, veto.
  - Canonical source: `skills/assurance-risk-director/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`assurance-security-compliance-office`** — Independent reviewer for security, compliance, reliability, and regulator-facing change. Use on every RC3 change (authz, audit ledger, OCR provenance, regulator-facing builders, Square, SCIM, RLS, claims, legal, relea...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/agents/assurance-security-compliance-office.md`
  - Source repo / subsystem: `hazmat-agent` / `snapshot-agents`
  - Confidence: `DIRECTLY RECOVERED`
- **`security-or-authz-change`** — Use when changing authz, RBAC, RLS, audit ledger, OCR provenance, secret handling, SCIM, SSO, CSP, supply-chain dependencies, or any RC3 security surface listed in docs/governance/03-change-risk-matrix.md. Enforces ma...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/security-or-authz-change/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § D. Security / Compliance Layer (Security) for names that appear in source bodies but lack their own frontmatter._

## D2. Security / Compliance Layer (Compliance)

### Canonical

- **`claims-substantiation-review`** — Use whenever externally-visible copy is being added or edited (marketing, RFP, trust portal, in-app onboarding text). Classifies each claim C1–C6 per docs/governance/11-commercial-claims-substantiation-policy.md and e...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/claims-substantiation-review/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`compliance-rule-change`** — Use when changing 49 CFR / TDG rule-engine logic, ERG data, placard thresholds, shipping-paper builders, training dossier (172 Subpart H), bilingual rendering, or any regulator-facing artifact. Requires regulator-text...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/compliance-rule-change/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`enterprise-procurement-readiness`** — Use when preparing for an enterprise procurement / RFP / security review. Walks RFP answer bank, ISO 27001 / compliance evidence matrix, sub-processor list, DPA / MSA drafts, and trust-portal content. Surfaces gaps be...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/enterprise-procurement-readiness/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § D2. Security / Compliance Layer (Compliance) for names that appear in source bodies but lack their own frontmatter._

## E. Psychology / UX / Behavior Layer (Psychology)

### Canonical

- **`humanizer`** — Humanize text: strip AI-isms and add real voice.
  - Canonical source: `skills/creative/humanizer/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`neuroskill-bci`** — >
  - Canonical source: `optional-skills/health/neuroskill-bci/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § E. Psychology / UX / Behavior Layer (Psychology) for names that appear in source bodies but lack their own frontmatter._

## E2. Psychology / UX / Behavior Layer (UX)

### Canonical

- **`developer-ux-command-center`** — Developer-facing surface for the Hermes orchestration pipeline. Use to drive scripts/hermes-orchestrate.sh from a terminal: scaffold a job, list jobs, inspect status, and explain artifacts in plain prose.
  - Canonical source: `skills/developer-ux-command-center/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`product-experience-architect`** — Owns product/UX: journeys, jobs, experience quality.
  - Canonical source: `skills/product-experience-architect/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`product-pilot-experience-studio`** — Use when a request is about user experience, founder demo, pilot/customer walkthrough, onboarding clarity, or visual presentation flow. Reviews PRDs, demo scripts, pilot readiness reports, and onboarding artifacts. Op...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/agents/product-pilot-experience-studio.md`
  - Source repo / subsystem: `hazmat-agent` / `snapshot-agents`
  - Confidence: `DIRECTLY RECOVERED`

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § E2. Psychology / UX / Behavior Layer (UX) for names that appear in source bodies but lack their own frontmatter._

## F. QA / Release / Testing Layer (QA)

### Canonical

- **`commercial-grade-implementation`** — The default implementation workflow for any code-bearing task in this repo. Enforces architecture awareness, scoped change design, negative-path tests, documentation alignment, and the final evidence package. Builder ...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/commercial-grade-implementation/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`complex-bug-fix`** — Use when a defect spans more than one file, more than one role, or appears to involve a regression in a tested surface. Walks the bug from reproduction through root cause, fix, negative test, regression test, and roll...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/complex-bug-fix/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`contrarian-red-flag-analyst`** — Alias of contrarian-reviewer (legacy upstream name).
  - Canonical source: `skills/contrarian-red-flag-analyst/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`contrarian-reviewer`** — Devil's advocate: red flags, weak arguments, blind spots.
  - Canonical source: `skills/contrarian-reviewer/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`decision-quality-gate`** — Force Hermes to produce a visible decision ledger before non-trivial actions — evidence, options, model/worker choice, validation plan, risk, rollback. Replaces hidden chain-of-thought with auditable reasoning.
  - Canonical source: `skills/decision-quality-gate/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`local-quality-gate`** — Run local validation gates against a workspace before publishing — git/secrets/lang/Hermes checks with a publish-block on critical failures.
  - Canonical source: `skills/local-quality-gate/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`principal-code-reviewer`** — Hard-nosed independent code reviewer. Use on every code-bearing PR before owner review. Catches AI slop, architecture shortcuts, weak tests, missing edge cases, silent behavioral drift, scope creep, and the looks done...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/agents/principal-code-reviewer.md`
  - Source repo / subsystem: `hazmat-agent` / `snapshot-agents`
  - Confidence: `DIRECTLY RECOVERED`

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § F. QA / Release / Testing Layer (QA) for names that appear in source bodies but lack their own frontmatter._

## F2. QA / Release / Testing Layer (Release)

### Canonical

- **`pilot-demo-readiness`** — Use to prepare for and judge readiness of a real customer demo or pilot session. Walks the demo end-to-end including failure paths, bilingual rendering, audit-ledger export, OCR low-confidence path, and verifies no ow...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/pilot-demo-readiness/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`pilot-readiness-judge`** — Use before a real customer demo or pilot session. Produces a binary go / no-go verdict with named blockers. Walks the demo / pilot script end-to-end, including failure paths. Cannot be bribed by almost ready — either ...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/agents/pilot-readiness-judge.md`
  - Source repo / subsystem: `hazmat-agent` / `snapshot-agents`
  - Confidence: `DIRECTLY RECOVERED`
- **`post-merge-verification`** — Use immediately after an owner-approved merge to main. Confirms the merge commit, the CI state on main, the documented baseline, the relevant docs, and any release notes / tags needed. Recommends the next work without...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/post-merge-verification/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`pr-readiness-and-owner-handoff`** — Use at the end of every substantive run to assemble the final PR body and the owner review checklist. Produces what changed, why, what was tested, what to inspect, what risk remains, exact next move — the owner handof...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/pr-readiness-and-owner-handoff/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`release-go-no-go-review`** — Use before tagging or shipping a release. Verifies G0–G4 release governance per PUBLISH.md, runs the freeze-trigger check, and produces a binary GO / NO-GO recommendation for the owner. Aligned with docs/skills/releas...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/release-go-no-go-review/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § F2. QA / Release / Testing Layer (Release) for names that appear in source bodies but lack their own frontmatter._

## G. Data / Memory / Knowledge Layer (Memory)

### Canonical

- **`evidence-architect`** — Builds the evidence base: facts, citations, provenance.
  - Canonical source: `skills/evidence-architect/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`evidence-bundle-build`** — Use immediately after mission-brief-build. Assembles repo facts, external citations, prior decisions, applicable standards, and risks into 01-evidence-bundle.md using docs/templates/evidence-bundle-template.md. Every ...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/evidence-bundle-build/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`knowledge-operations-self-improvement`** — Use to maintain durable artifacts — the index, the doc-freshness ledger, the agent-run retrospective, the prompt/system quality log. Reconciles contradictions, removes stale claims, updates HANDOFF.md only when materi...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/agents/knowledge-operations-self-improvement.md`
  - Source repo / subsystem: `hazmat-agent` / `snapshot-agents`
  - Confidence: `DIRECTLY RECOVERED`

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § G. Data / Memory / Knowledge Layer (Memory) for names that appear in source bodies but lack their own frontmatter._

## G2. Data / Memory / Knowledge Layer (Research)

### Canonical

- **`ai-improvement-radar`** — Track AI coding-agent improvements (Codex, Claude Code, Aider, Goose, Continue, OpenHands, Gemini/Jules/Antigravity, OpenClaw-style personal agents) and recommend updates to Hermes' routing policy, model registry, and...
  - Canonical source: `skills/ai-improvement-radar/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`research-dossier-build`** — Use when an RC3 change, new commercial claim, new legal document, pricing decision, vendor choice, regulator-facing change, or 49 CFR / TDG rule-engine change is being proposed. Produces a research dossier under docs/...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/research-dossier-build/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`research-evidence-bureau`** — Read-only research and evidence agent. Use whenever a task requires verifying an external standard (49 CFR, TDG, NIST SP, OWASP, ISO 27001, vendor documentation), comparing claims to sources, building a research dossi...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/agents/research-evidence-bureau.md`
  - Source repo / subsystem: `hazmat-agent` / `snapshot-agents`
  - Confidence: `DIRECTLY RECOVERED`
- **`research-validator`** — Gather evidence and validate claims before Hermes commits to a decision. Companion to decision-quality-gate — fills the Evidence Reviewed and Validation Plan sections with concrete, verifiable artefacts.
  - Canonical source: `skills/research-validator/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`self-improvement-loop`** — Close every job with a learning pass: read artifacts + scorecard, propose updates to skills/prompts/routing, record what to keep, what to drop, and what to try next.
  - Canonical source: `skills/self-improvement-loop/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § G2. Data / Memory / Knowledge Layer (Research) for names that appear in source bodies but lack their own frontmatter._

## H. Claude Code / Codex / Developer Workflow Layer (Claude Code)

### Canonical

- **`claude-code`** — Delegate coding to Claude Code CLI (features, PRs).
  - Canonical source: `recovered-agent-sources/from-hermes-agent/autonomous-ai-agents/claude-code/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**

### Aliases

- **`claude-code`** (alias) — Delegate coding to Claude Code CLI (features, PRs).
  - Alternate source: `skills/autonomous-ai-agents/claude-code/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § H. Claude Code / Codex / Developer Workflow Layer (Claude Code) for names that appear in source bodies but lack their own frontmatter._

## H2. Claude Code / Codex / Developer Workflow Layer (Codex)

### Canonical

- **`codex`** — Delegate coding to OpenAI Codex CLI (features, PRs).
  - Canonical source: `recovered-agent-sources/from-hermes-agent/autonomous-ai-agents/codex/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`codex-dispatch-governor`** — Routes coding tasks to Codex/external agents safely.
  - Canonical source: `skills/codex-dispatch-governor/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`codex-implementation-fabric`** — Thin wrapper for the Codex bounded-implementation fabric. Authority cap L3, trust zones T3+T4 only — never L4 or T5/T6. Owner-only walls forbidden. Dispatches scoped Codex Task Packets, validates the return envelope, ...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/agents/codex-implementation-fabric.md`
  - Source repo / subsystem: `hazmat-agent` / `snapshot-agents`
  - Confidence: `DIRECTLY RECOVERED`
- **`codex-return-envelope-verify`** — Use after a Codex Task Packet execution returns. Parses the return envelope, asserts schema validity, asserts allow-list adherence, asserts forbidden-list adherence, re-runs the claimed test commands locally, cross-ch...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/codex-return-envelope-verify/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`codex-task-packet-dispatch`** — Manual-only. Owner-triggered. Drafts and dispatches a Codex Task Packet per docs/templates/codex-task-package-template.md and docs/governance/17-codex-bounded-implementation-fabric.md. Wave 1 is contract-only — valida...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/skills/codex-task-packet-dispatch/SKILL.md`
  - Source repo / subsystem: `hazmat-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`kanban-codex-lane`** — Use when a Hermes Kanban worker wants to run Codex CLI as an isolated implementation lane while Hermes keeps ownership of task lifecycle, reconciliation, testing, and handoff.
  - Canonical source: `recovered-agent-sources/from-hermes-agent/autonomous-ai-agents/kanban-codex-lane/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**

### Aliases

- **`codex`** (alias) — Delegate coding to OpenAI Codex CLI (features, PRs).
  - Alternate source: `skills/autonomous-ai-agents/codex/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.
- **`kanban-codex-lane`** (alias) — Use when a Hermes Kanban worker wants to run Codex CLI as an isolated implementation lane while Hermes keeps ownership of task lifecycle, reconciliation, testing, and handoff.
  - Alternate source: `skills/autonomous-ai-agents/kanban-codex-lane/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § H2. Claude Code / Codex / Developer Workflow Layer (Codex) for names that appear in source bodies but lack their own frontmatter._

## I. HazMat Command-Specific Layer

### Canonical

- **`merger-model`** — Build accretion/dilution (merger) models in Excel — pro-forma P&L, synergies, financing mix, EPS impact. Pairs with excel-author. Use for M&A pitches, board materials, or deal evaluation.
  - Canonical source: `optional-skills/finance/merger-model/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § I. HazMat Command-Specific Layer for names that appear in source bodies but lack their own frontmatter._

## J. Nourish-Specific Layer

### Canonical

- **`fitness-nutrition`** — >
  - Canonical source: `optional-skills/health/fitness-nutrition/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § J. Nourish-Specific Layer for names that appear in source bodies but lack their own frontmatter._

## K. Hermes-Specific Skills Layer

### Canonical

- **`1password`** — Set up and use 1Password CLI (op). Use when installing the CLI, enabling desktop app integration, signing in, and reading/injecting secrets for commands.
  - Canonical source: `optional-skills/security/1password/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`3-statement-model`** — Build fully-integrated 3-statement models (IS, BS, CF) in Excel with working capital schedules, D&A roll-forwards, debt schedule, and the plugs that make cash and retained earnings tie. Pairs with excel-author.
  - Canonical source: `optional-skills/finance/3-statement-model/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`adversarial-ux-test`** — Roleplay the most difficult, tech-resistant user for your product. Browse the app as that persona, find every UX pain point, then filter complaints through a pragmatism layer to separate real problems from noise. Crea...
  - Canonical source: `optional-skills/dogfood/adversarial-ux-test/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`agentmail`** — Give the agent its own dedicated email inbox via AgentMail. Send, receive, and manage email autonomously using agent-owned email addresses (e.g. hermes-agent@agentmail.to).
  - Canonical source: `optional-skills/email/agentmail/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`airtable`** — Airtable REST API via curl. Records CRUD, filters, upserts.
  - Canonical source: `skills/productivity/airtable/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`aos-enterprise-council`** — AOS Enterprise Council — full 11-division autonomous-enterprise smart team (chief orchestrator, engineering, security/compliance, product/pilot, research/evidence, commercial, legal, knowledge-ops, code-review, codex ...
  - Canonical source: `skills/aos-enterprise-council/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`apple-notes`** — Manage Apple Notes via memo CLI: create, search, edit.
  - Canonical source: `skills/apple/apple-notes/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`apple-reminders`** — Apple Reminders via remindctl: add, list, complete.
  - Canonical source: `skills/apple/apple-reminders/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`architecture-diagram`** — Dark-themed SVG architecture/cloud/infra diagrams as HTML.
  - Canonical source: `skills/creative/architecture-diagram/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`arxiv`** — Search arXiv papers by keyword, author, category, or ID.
  - Canonical source: `skills/research/arxiv/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`ascii-art`** — ASCII art: pyfiglet, cowsay, boxes, image-to-ascii.
  - Canonical source: `skills/creative/ascii-art/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`ascii-video`** — ASCII video: convert video/audio to colored ASCII MP4/GIF.
  - Canonical source: `skills/creative/ascii-video/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`audiocraft-audio-generation`** — AudioCraft: MusicGen text-to-music, AudioGen text-to-sound.
  - Canonical source: `skills/mlops/models/audiocraft/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`axolotl`** — Axolotl: YAML LLM fine-tuning (LoRA, DPO, GRPO).
  - Canonical source: `optional-skills/mlops/training/axolotl/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`baoyu-article-illustrator`** — Article illustrations: type × style × palette consistency.
  - Canonical source: `skills/creative/baoyu-article-illustrator/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`baoyu-comic`** — Knowledge comics (知识漫画): educational, biography, tutorial.
  - Canonical source: `skills/creative/baoyu-comic/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`baoyu-infographic`** — Infographics: 21 layouts x 21 styles (信息图, 可视化).
  - Canonical source: `skills/creative/baoyu-infographic/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`best-coding-tool-mission`** — Anchor every job to Hermes' mission as the best private local-first developer command center: one prompt, routed work, scored output, reversible publishes, learning loop.
  - Canonical source: `skills/best-coding-tool-mission/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`bioinformatics`** — Gateway to 400+ bioinformatics skills from bioSkills and ClawBio. Covers genomics, transcriptomics, single-cell, variant calling, pharmacogenomics, metagenomics, structural biology, and more. Fetches domain-specific r...
  - Canonical source: `optional-skills/research/bioinformatics/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`blackbox`** — Delegate coding tasks to Blackbox AI CLI agent. Multi-model agent with built-in judge that runs tasks through multiple LLMs and picks the best result. Requires the blackbox CLI and a Blackbox AI API key.
  - Canonical source: `optional-skills/autonomous-ai-agents/blackbox/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`blender-mcp`** — Control Blender directly from Hermes via socket connection to the blender-mcp addon. Create 3D objects, materials, animations, and run arbitrary Blender Python (bpy) code. Use when user wants to create or modify anyth...
  - Canonical source: `optional-skills/creative/blender-mcp/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`blogwatcher`** — Monitor blogs and RSS/Atom feeds via blogwatcher-cli tool.
  - Canonical source: `skills/research/blogwatcher/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`canvas`** — Canvas LMS integration — fetch enrolled courses and assignments using API token authentication.
  - Canonical source: `optional-skills/productivity/canvas/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`chroma`** — Open-source embedding database for AI applications. Store embeddings and metadata, perform vector and full-text search, filter by metadata. Simple 4-function API. Scales from notebooks to production clusters. Use for ...
  - Canonical source: `optional-skills/mlops/chroma/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`claude-design`** — Design one-off HTML artifacts (landing, deck, prototype).
  - Canonical source: `skills/creative/claude-design/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`clip`** — OpenAI's model connecting vision and language. Enables zero-shot image classification, image-text matching, and cross-modal retrieval. Trained on 400M image-text pairs. Use for image search, content moderation, or vis...
  - Canonical source: `optional-skills/mlops/clip/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`codebase-inspection`** — Inspect codebases w/ pygount: LOC, languages, ratios.
  - Canonical source: `skills/github/codebase-inspection/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`comfyui`** — Generate images, video, and audio with ComfyUI — install, launch, manage nodes/models, run workflows with parameter injection. Uses the official comfy-cli for lifecycle and direct REST/WebSocket API for execution.
  - Canonical source: `skills/creative/comfyui/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`comps-analysis`** — Build comparable company analysis in Excel — operating metrics, valuation multiples, statistical benchmarking vs peer sets. Pairs with excel-author. Use for public-company valuation, IPO pricing, sector benchmarking, ...
  - Canonical source: `optional-skills/finance/comps-analysis/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`concept-diagrams`** — Generate flat, minimal light/dark-aware SVG diagrams as standalone HTML files, using a unified educational visual language with 9 semantic color ramps, sentence-case typography, and automatic dark mode. Best suited fo...
  - Canonical source: `optional-skills/creative/concept-diagrams/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`darwinian-evolver`** — Evolve prompts/regex/SQL/code with Imbue's evolution loop.
  - Canonical source: `optional-skills/research/darwinian-evolver/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`dcf-model`** — Build institutional-quality DCF valuation models in Excel — revenue projections, FCF build, WACC, terminal value, Bear/Base/Bull scenarios, 5x5 sensitivity tables. Pairs with excel-author. Use for intrinsic-value equi...
  - Canonical source: `optional-skills/finance/dcf-model/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`debugging-hermes-tui-commands`** — Debug Hermes TUI slash commands: Python, gateway, Ink UI.
  - Canonical source: `skills/software-development/debugging-hermes-tui-commands/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`delivery-scope-controller`** — Owns scope, sequencing, dependencies, delivery shape.
  - Canonical source: `skills/delivery-scope-controller/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`design-md`** — Author/validate/export Google's DESIGN.md token spec files.
  - Canonical source: `skills/creative/design-md/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`distributed-llm-pretraining-torchtitan`** — Provides PyTorch-native distributed LLM pretraining using torchtitan with 4D parallelism (FSDP2, TP, PP, CP). Use when pretraining Llama 3.1, DeepSeek V3, or custom models at scale from 8 to 512+ GPUs with Float8, tor...
  - Canonical source: `optional-skills/mlops/torchtitan/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`docker-management`** — Manage Docker containers, images, volumes, networks, and Compose stacks — lifecycle ops, debugging, cleanup, and Dockerfile optimization.
  - Canonical source: `optional-skills/devops/docker-management/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`dogfood`** — Exploratory QA of web apps: find bugs, evidence, reports.
  - Canonical source: `skills/dogfood/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`domain-intel`** — Passive domain reconnaissance using Python stdlib. Subdomain discovery, SSL certificate inspection, WHOIS lookups, DNS records, domain availability checks, and bulk multi-domain analysis. No API keys required.
  - Canonical source: `optional-skills/research/domain-intel/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`drug-discovery`** — >
  - Canonical source: `optional-skills/research/drug-discovery/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`dspy`** — DSPy: declarative LM programs, auto-optimize prompts, RAG.
  - Canonical source: `skills/mlops/research/dspy/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`duckduckgo-search`** — Free web search via DuckDuckGo — text, news, images, videos. No API key needed. Prefer the `ddgs` CLI when installed; use the Python DDGS library only after verifying that `ddgs` is available in the current runtime.
  - Canonical source: `optional-skills/research/duckduckgo-search/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`enterprise-finance`** — Finance leaf: invoicing, budgeting, reporting against Stripe/NetSuite/QuickBooks.
  - Canonical source: `recovered-agent-sources/from-hermes-agent/enterprise-council/finance/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`enterprise-hr`** — HR leaf: recruitment screening, policy lookup, offer + termination workflows.
  - Canonical source: `recovered-agent-sources/from-hermes-agent/enterprise-council/hr/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`enterprise-judge`** — Validator / Judge: schema + policy + parallel-pass cross-checks on every leaf result.
  - Canonical source: `recovered-agent-sources/from-hermes-agent/enterprise-council/judge/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`enterprise-monitor`** — Post-run reviewer: scans the audit trail, proposes improvements, hands them to the curator.
  - Canonical source: `recovered-agent-sources/from-hermes-agent/enterprise-council/monitor/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`enterprise-operations`** — Operations leaf: logistics planning + execution, compliance checks + filings, incident declaration.
  - Canonical source: `recovered-agent-sources/from-hermes-agent/enterprise-council/operations/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`enterprise-orchestrator`** — Decompose a one-tap enterprise goal into autonomous tasks across domain agents.
  - Canonical source: `recovered-agent-sources/from-hermes-agent/enterprise-council/orchestrator/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`enterprise-sales`** — Sales leaf: lead tracking, proposal drafting + sending, contract execution, discounting.
  - Canonical source: `recovered-agent-sources/from-hermes-agent/enterprise-council/sales/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`evaluating-llms-harness`** — lm-eval-harness: benchmark LLMs (MMLU, GSM8K, etc.).
  - Canonical source: `skills/mlops/evaluation/lm-evaluation-harness/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`evm`** — Read-only EVM client: wallets, tokens, gas across 8 chains.
  - Canonical source: `optional-skills/blockchain/evm/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`excalidraw`** — Hand-drawn Excalidraw JSON diagrams (arch, flow, seq).
  - Canonical source: `skills/creative/excalidraw/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`excel-author`** — Build auditable Excel workbooks headless with openpyxl — blue/black/green cell conventions, formulas over hardcodes, named ranges, balance checks, sensitivity tables. Use for financial models, audit outputs, reconcili...
  - Canonical source: `optional-skills/finance/excel-author/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`faiss`** — Facebook's library for efficient similarity search and clustering of dense vectors. Supports billions of vectors, GPU acceleration, and various index types (Flat, IVF, HNSW). Use for fast k-NN search, large-scale vect...
  - Canonical source: `optional-skills/mlops/faiss/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`fastmcp`** — Build, test, inspect, install, and deploy MCP servers with FastMCP in Python. Use when creating a new MCP server, wrapping an API or database as MCP tools, exposing resources or prompts, or preparing a FastMCP server ...
  - Canonical source: `optional-skills/mcp/fastmcp/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`findmy`** — Track Apple devices/AirTags via FindMy.app on macOS.
  - Canonical source: `skills/apple/findmy/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`fine-tuning-with-trl`** — TRL: SFT, DPO, PPO, GRPO, reward modeling for LLM RLHF.
  - Canonical source: `optional-skills/mlops/training/trl-fine-tuning/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`gif-search`** — Search/download GIFs from Tenor via curl + jq.
  - Canonical source: `skills/media/gif-search/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`github-auth`** — GitHub auth setup: HTTPS tokens, SSH keys, gh CLI login.
  - Canonical source: `skills/github/github-auth/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`github-code-review`** — Review PRs: diffs, inline comments via gh or REST.
  - Canonical source: `skills/github/github-code-review/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`github-issues`** — Create, triage, label, assign GitHub issues via gh or REST.
  - Canonical source: `skills/github/github-issues/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`github-pr-workflow`** — GitHub PR lifecycle: branch, commit, open, CI, merge.
  - Canonical source: `skills/github/github-pr-workflow/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`github-publisher`** — Promote a Hermes orchestration job's github/ artifacts (branch, commit message, PR title, PR body) into a real branch and pull request. Phase-02-aware: the artifacts exist but must not be pushed until later phases pop...
  - Canonical source: `skills/github-publisher/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`github-repo-management`** — Clone/create/fork repos; manage remotes, releases.
  - Canonical source: `skills/github/github-repo-management/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`gitnexus-explorer`** — Index a codebase with GitNexus and serve an interactive knowledge graph via web UI + Cloudflare tunnel.
  - Canonical source: `optional-skills/research/gitnexus-explorer/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`godmode`** — Jailbreak LLMs: Parseltongue, GODMODE, ULTRAPLINIAN.
  - Canonical source: `skills/red-teaming/godmode/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`google-workspace`** — Gmail, Calendar, Drive, Docs, Sheets via gws CLI or Python.
  - Canonical source: `skills/productivity/google-workspace/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`guidance`** — Control LLM output with regex and grammars, guarantee valid JSON/XML/code generation, enforce structured formats, and build multi-step workflows with Guidance - Microsoft Research's constrained generation framework
  - Canonical source: `optional-skills/mlops/guidance/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`heartmula`** — HeartMuLa: Suno-like song generation from lyrics + tags.
  - Canonical source: `skills/media/heartmula/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`here.now`** — Publish static sites to {slug}.here.now and store private files in cloud Drives for agent-to-agent handoff.
  - Canonical source: `optional-skills/productivity/here-now/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`hermes-agent`** — Configure, extend, or contribute to Hermes Agent.
  - Canonical source: `recovered-agent-sources/from-hermes-agent/autonomous-ai-agents/hermes-agent/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`hermes-agent-skill-authoring`** — Author in-repo SKILL.md: frontmatter, validator, structure.
  - Canonical source: `skills/software-development/hermes-agent-skill-authoring/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`hermes-orchestration-pipeline`** — Phase-02 foundation contract for the Hermes multi-worker orchestration pipeline. Use when scaffolding a job folder, deciding what artifacts a worker is allowed to read or write, or when planning the controller that wi...
  - Canonical source: `skills/hermes-orchestration-pipeline/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`himalaya`** — Himalaya CLI: IMAP/SMTP email from terminal.
  - Canonical source: `skills/email/himalaya/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`honcho`** — Configure and use Honcho memory with Hermes -- cross-session user modeling, multi-profile peer isolation, observation config, dialectic reasoning, session summaries, and context budget enforcement. Use when setting up...
  - Canonical source: `optional-skills/autonomous-ai-agents/honcho/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`huggingface-accelerate`** — Simplest distributed training API. 4 lines to add distributed support to any PyTorch script. Unified API for DeepSpeed/FSDP/Megatron/DDP. Automatic device placement, mixed precision (FP16/BF16/FP8). Interactive config...
  - Canonical source: `optional-skills/mlops/accelerate/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`huggingface-hub`** — HuggingFace hf CLI: search/download/upload models, datasets.
  - Canonical source: `skills/mlops/huggingface-hub/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`huggingface-tokenizers`** — Fast tokenizers optimized for research and production. Rust-based implementation tokenizes 1GB in <20 seconds. Supports BPE, WordPiece, and Unigram algorithms. Train custom vocabularies, track alignments, handle paddi...
  - Canonical source: `optional-skills/mlops/huggingface-tokenizers/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`hyperframes`** — Create HTML-based video compositions, animated title cards, social overlays, captioned talking-head videos, audio-reactive visuals, and shader transitions using HyperFrames. HTML is the source of truth for video. Use ...
  - Canonical source: `optional-skills/creative/hyperframes/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`hyperliquid`** — Hyperliquid market data, account history, trade review.
  - Canonical source: `optional-skills/blockchain/hyperliquid/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`ideation`** — Generate project ideas via creative constraints.
  - Canonical source: `skills/creative/creative-ideation/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`imessage`** — Send and receive iMessages/SMS via the imsg CLI on macOS.
  - Canonical source: `skills/apple/imessage/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`inference-sh-cli`** — Run 150+ AI apps via inference.sh CLI (infsh) — image generation, video creation, LLMs, search, 3D, social automation. Uses the terminal tool. Triggers: inference.sh, infsh, ai apps, flux, veo, image generation, video...
  - Canonical source: `optional-skills/devops/cli/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`instructor`** — Extract structured data from LLM responses with Pydantic validation, retry failed extractions automatically, parse complex JSON with type safety, and stream partial results with Instructor - battle-tested structured o...
  - Canonical source: `optional-skills/mlops/instructor/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`jupyter-live-kernel`** — Iterative Python via live Jupyter kernel (hamelnb).
  - Canonical source: `skills/data-science/jupyter-live-kernel/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`kanban-orchestrator`** — Decomposition playbook + anti-temptation rules for an orchestrator profile routing work through Kanban. The don't do the work yourself rule and the basic lifecycle are auto-injected into every kanban worker's system p...
  - Canonical source: `skills/devops/kanban-orchestrator/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`kanban-video-orchestrator`** — Plan, set up, and monitor a multi-agent video production pipeline backed by Hermes Kanban. Use when the user wants to make ANY video — narrative film, product/marketing, music video, explainer, ASCII/terminal art, abs...
  - Canonical source: `optional-skills/creative/kanban-video-orchestrator/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`kanban-worker`** — Pitfalls, examples, and edge cases for Hermes Kanban workers. The lifecycle itself is auto-injected into every worker's system prompt as KANBAN_GUIDANCE (from agent/prompt_builder.py); this skill is what you load when...
  - Canonical source: `skills/devops/kanban-worker/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`lambda-labs-gpu-cloud`** — Reserved and on-demand GPU cloud instances for ML training and inference. Use when you need dedicated GPU instances with simple SSH access, persistent filesystems, or high-performance multi-node clusters for large-sca...
  - Canonical source: `optional-skills/mlops/lambda-labs/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`lbo-model`** — Build leveraged buyout models in Excel — sources & uses, debt schedule, cash sweep, exit multiple, IRR/MOIC sensitivity. Pairs with excel-author. Use for PE screening, sponsor-case valuation, or illustrative LBO in a ...
  - Canonical source: `optional-skills/finance/lbo-model/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`linear`** — Linear: manage issues, projects, teams via GraphQL + curl.
  - Canonical source: `skills/productivity/linear/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`llama-cpp`** — llama.cpp local GGUF inference + HF Hub model discovery.
  - Canonical source: `skills/mlops/inference/llama-cpp/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`llava`** — Large Language and Vision Assistant. Enables visual instruction tuning and image-based conversations. Combines CLIP vision encoder with Vicuna/LLaMA language models. Supports multi-turn image chat, visual question ans...
  - Canonical source: `optional-skills/mlops/llava/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`llm-wiki`** — Karpathy's LLM Wiki: build/query interlinked markdown KB.
  - Canonical source: `skills/research/llm-wiki/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`macos-computer-use`** — |
  - Canonical source: `skills/apple/macos-computer-use/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`manim-video`** — Manim CE animations: 3Blue1Brown math/algo videos.
  - Canonical source: `skills/creative/manim-video/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`maps`** — Geocode, POIs, routes, timezones via OpenStreetMap/OSRM.
  - Canonical source: `skills/productivity/maps/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`mcporter`** — Use the mcporter CLI to list, configure, auth, and call MCP servers/tools directly (HTTP or stdio), including ad-hoc servers, config edits, and CLI/type generation.
  - Canonical source: `optional-skills/mcp/mcporter/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`meme-generation`** — Generate real meme images by picking a template and overlaying text with Pillow. Produces actual .png meme files.
  - Canonical source: `optional-skills/creative/meme-generation/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`memento-flashcards`** — >-
  - Canonical source: `optional-skills/productivity/memento-flashcards/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`minecraft-modpack-server`** — Host modded Minecraft servers (CurseForge, Modrinth).
  - Canonical source: `skills/gaming/minecraft-modpack-server/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`modal-serverless-gpu`** — Serverless GPU cloud platform for running ML workloads. Use when you need on-demand GPU access without infrastructure management, deploying ML models as APIs, or running batch jobs with automatic scaling.
  - Canonical source: `optional-skills/mlops/modal/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`model-router`** — Choose the best worker/model mix for each Hermes workflow. Considers task type, local tool availability, quality, cost, speed, validation needs, and fallback options.
  - Canonical source: `skills/model-router/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`nano-pdf`** — Edit PDF text/typos/titles via nano-pdf CLI (NL prompts).
  - Canonical source: `skills/productivity/nano-pdf/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`native-mcp`** — MCP client: connect servers, register tools (stdio/HTTP).
  - Canonical source: `skills/mcp/native-mcp/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`nemo-curator`** — GPU-accelerated data curation for LLM training. Supports text/image/video/audio. Features fuzzy deduplication (16× faster), quality filtering (30+ heuristics), semantic deduplication, PII redaction, NSFW detection. Sc...
  - Canonical source: `optional-skills/mlops/nemo-curator/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`node-inspect-debugger`** — Debug Node.js via --inspect + Chrome DevTools Protocol CLI.
  - Canonical source: `skills/software-development/node-inspect-debugger/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`notion`** — Notion API + ntn CLI: pages, databases, markdown, Workers.
  - Canonical source: `skills/productivity/notion/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`obliteratus`** — OBLITERATUS: abliterate LLM refusals (diff-in-means).
  - Canonical source: `skills/mlops/inference/obliteratus/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`obsidian`** — Read, search, create, and edit notes in the Obsidian vault.
  - Canonical source: `skills/note-taking/obsidian/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`ocr-and-documents`** — Extract text from PDFs/scans (pymupdf, marker-pdf).
  - Canonical source: `skills/productivity/ocr-and-documents/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`one-three-one-rule`** — >
  - Canonical source: `optional-skills/communication/one-three-one-rule/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`openclaw-migration`** — Migrate a user's OpenClaw customization footprint into Hermes Agent. Imports Hermes-compatible memories, SOUL.md, command allowlists, user skills, and selected workspace assets from ~/.openclaw, then reports exactly w...
  - Canonical source: `optional-skills/migration/openclaw-migration/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`opencode`** — Delegate coding to OpenCode CLI (features, PR review).
  - Canonical source: `recovered-agent-sources/from-hermes-agent/autonomous-ai-agents/opencode/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`openhue`** — Control Philips Hue lights, scenes, rooms via OpenHue CLI.
  - Canonical source: `skills/smart-home/openhue/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`optimizing-attention-flash`** — Optimizes transformer attention with Flash Attention for 2-4x speedup and 10-20x memory reduction. Use when training/running transformers with long sequences (>512 tokens), encountering GPU memory issues with attentio...
  - Canonical source: `optional-skills/mlops/flash-attention/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`osint-investigation`** — Public-records OSINT investigation framework — SEC EDGAR filings, USAspending contracts, Senate lobbying, OFAC sanctions, ICIJ offshore leaks, NYC property records (ACRIS), OpenCorporates registries, CourtListener cou...
  - Canonical source: `optional-skills/research/osint-investigation/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`oss-forensics`** — |
  - Canonical source: `optional-skills/security/oss-forensics/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`outlines`** — Outlines: structured JSON/regex/Pydantic LLM generation.
  - Canonical source: `optional-skills/mlops/inference/outlines/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`p5js`** — p5.js sketches: gen art, shaders, interactive, 3D.
  - Canonical source: `skills/creative/p5js/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`page-agent`** — Embed alibaba/page-agent into your own web application — a pure-JavaScript in-page GUI agent that ships as a single <script> tag or npm package and lets end-users of your site drive the UI with natural language (click...
  - Canonical source: `optional-skills/web-development/page-agent/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`parallel-cli`** — Optional vendor skill for Parallel CLI — agent-native web search, extraction, deep research, enrichment, FindAll, and monitoring. Prefer JSON output and non-interactive flows.
  - Canonical source: `optional-skills/research/parallel-cli/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`peft-fine-tuning`** — Parameter-efficient fine-tuning for LLMs using LoRA, QLoRA, and 25+ methods. Use when fine-tuning large models (7B-70B) with limited GPU memory, when you need to train <1% of parameters with minimal accuracy loss, or ...
  - Canonical source: `optional-skills/mlops/peft/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`pinecone`** — Managed vector database for production AI applications. Fully managed, auto-scaling, with hybrid search (dense + sparse), metadata filtering, and namespaces. Low latency (<100ms p95). Use for production RAG, recommend...
  - Canonical source: `optional-skills/mlops/pinecone/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`pinggy-tunnel`** — Zero-install localhost tunnels over SSH via Pinggy.
  - Canonical source: `optional-skills/devops/pinggy-tunnel/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`pixel-art`** — Pixel art w/ era palettes (NES, Game Boy, PICO-8).
  - Canonical source: `skills/creative/pixel-art/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`plan`** — Plan mode: write markdown plan to .hermes/plans/, no exec.
  - Canonical source: `skills/software-development/plan/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`pokemon-player`** — Play Pokemon via headless emulator + RAM reads.
  - Canonical source: `skills/gaming/pokemon-player/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`polymarket`** — Query Polymarket: markets, prices, orderbooks, history.
  - Canonical source: `skills/research/polymarket/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`popular-web-designs`** — 54 real design systems (Stripe, Linear, Vercel) as HTML/CSS.
  - Canonical source: `skills/creative/popular-web-designs/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`powerpoint`** — Create, read, edit .pptx decks, slides, notes, templates.
  - Canonical source: `skills/productivity/powerpoint/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`pptx-author`** — Build PowerPoint decks headless with python-pptx. Pairs with excel-author for model-backed decks where every number traces to a workbook cell. Use for pitch decks, IC memos, earnings notes.
  - Canonical source: `optional-skills/finance/pptx-author/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`pretext`** — Use when building creative browser demos with @chenglou/pretext — DOM-free text layout for ASCII art, typographic flow around obstacles, text-as-geometry games, kinetic typography, and text-powered generative art. Pro...
  - Canonical source: `skills/creative/pretext/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`python-debugpy`** — Debug Python: pdb REPL + debugpy remote (DAP).
  - Canonical source: `skills/software-development/python-debugpy/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`pytorch-fsdp`** — Expert guidance for Fully Sharded Data Parallel training with PyTorch FSDP - parameter sharding, mixed precision, CPU offloading, FSDP2
  - Canonical source: `optional-skills/mlops/pytorch-fsdp/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`pytorch-lightning`** — High-level PyTorch framework with Trainer class, automatic distributed training (DDP/FSDP/DeepSpeed), callbacks system, and minimal boilerplate. Scales from laptop to supercomputer with same code. Use when you want cl...
  - Canonical source: `optional-skills/mlops/pytorch-lightning/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`qdrant-vector-search`** — High-performance vector similarity search engine for RAG and semantic search. Use when building production RAG systems requiring fast nearest neighbor search, hybrid search with filtering, or scalable vector storage w...
  - Canonical source: `optional-skills/mlops/qdrant/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`qmd`** — Search personal knowledge bases, notes, docs, and meeting transcripts locally using qmd — a hybrid retrieval engine with BM25, vector search, and LLM reranking. Supports CLI and MCP integration.
  - Canonical source: `optional-skills/research/qmd/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`requesting-code-review`** — Pre-commit review: security scan, quality gates, auto-fix.
  - Canonical source: `skills/software-development/requesting-code-review/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`research-paper-writing`** — Write ML papers for NeurIPS/ICML/ICLR: design→submit.
  - Canonical source: `skills/research/research-paper-writing/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`rest-graphql-debug`** — Debug REST/GraphQL APIs: status codes, auth, schemas, repro.
  - Canonical source: `optional-skills/software-development/rest-graphql-debug/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`scrapling`** — Web scraping with Scrapling - HTTP fetching, stealth browser automation, Cloudflare bypass, and spider crawling via CLI and Python.
  - Canonical source: `optional-skills/research/scrapling/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`searxng-search`** — Free meta-search via SearXNG — aggregates results from 70+ search engines. Self-hosted or use a public instance. No API key needed. Falls back automatically when the web search toolset is unavailable.
  - Canonical source: `optional-skills/research/searxng-search/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`segment-anything-model`** — SAM: zero-shot image segmentation via points, boxes, masks.
  - Canonical source: `skills/mlops/models/segment-anything/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`serving-llms-vllm`** — vLLM: high-throughput LLM serving, OpenAI API, quantization.
  - Canonical source: `skills/mlops/inference/vllm/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`sherlock`** — OSINT username search across 400+ social networks. Hunt down social media accounts by username.
  - Canonical source: `optional-skills/security/sherlock/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`shop-app`** — Shop.app: product search, order tracking, returns, reorder.
  - Canonical source: `optional-skills/productivity/shop-app/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`shopify`** — Shopify Admin & Storefront GraphQL APIs via curl. Products, orders, customers, inventory, metafields.
  - Canonical source: `optional-skills/productivity/shopify/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`simpo-training`** — Simple Preference Optimization for LLM alignment. Reference-free alternative to DPO with better performance (+6.4 points on AlpacaEval 2.0). No reference model needed, more efficient than DPO. Use for preference align...
  - Canonical source: `optional-skills/mlops/simpo/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`siyuan`** — SiYuan Note API for searching, reading, creating, and managing blocks and documents in a self-hosted knowledge base via curl.
  - Canonical source: `optional-skills/productivity/siyuan/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`sketch`** — Throwaway HTML mockups: 2-3 design variants to compare.
  - Canonical source: `skills/creative/sketch/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`slime-rl-training`** — Provides guidance for LLM post-training with RL using slime, a Megatron+SGLang framework. Use when training GLM models, implementing custom data generation workflows, or needing tight Megatron-LM integration for RL sc...
  - Canonical source: `optional-skills/mlops/slime/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`solana`** — Query Solana blockchain data with USD pricing — wallet balances, token portfolios with values, transaction details, NFTs, whale detection, and live network stats. Uses Solana RPC + CoinGecko. No API key required.
  - Canonical source: `optional-skills/blockchain/solana/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`songsee`** — Audio spectrograms/features (mel, chroma, MFCC) via CLI.
  - Canonical source: `skills/media/songsee/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`songwriting-and-ai-music`** — Songwriting craft and Suno AI music prompts.
  - Canonical source: `skills/creative/songwriting-and-ai-music/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`sparse-autoencoder-training`** — Provides guidance for training and analyzing Sparse Autoencoders (SAEs) using SAELens to decompose neural network activations into interpretable features. Use when discovering interpretable features, analyzing superpo...
  - Canonical source: `optional-skills/mlops/saelens/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`spike`** — Throwaway experiments to validate an idea before build.
  - Canonical source: `skills/software-development/spike/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`spotify`** — Spotify: play, search, queue, manage playlists and devices.
  - Canonical source: `skills/media/spotify/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`stable-diffusion-image-generation`** — State-of-the-art text-to-image generation with Stable Diffusion models via HuggingFace Diffusers. Use when generating images from text prompts, performing image-to-image translation, inpainting, or building custom dif...
  - Canonical source: `optional-skills/mlops/stable-diffusion/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`stocks`** — Stock quotes, history, search, compare, crypto via Yahoo.
  - Canonical source: `optional-skills/finance/stocks/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`subagent-driven-development`** — Execute plans via delegate_task subagents (2-stage review).
  - Canonical source: `skills/software-development/subagent-driven-development/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`systematic-debugging`** — 4-phase root cause debugging: understand bugs before fixing.
  - Canonical source: `skills/software-development/systematic-debugging/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`teams-meeting-pipeline`** — Operate the Teams meeting summary pipeline via Hermes CLI — summarize meetings, inspect pipeline status, replay jobs, manage Microsoft Graph subscriptions.
  - Canonical source: `skills/productivity/teams-meeting-pipeline/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`telephony`** — Give Hermes phone capabilities without core tool changes. Provision and persist a Twilio number, send and receive SMS/MMS, make direct calls, and place AI-driven outbound calls through Bland.ai or Vapi.
  - Canonical source: `optional-skills/productivity/telephony/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`tensorrt-llm`** — Optimizes LLM inference with NVIDIA TensorRT for maximum throughput and lowest latency. Use for production deployment on NVIDIA GPUs (A100/H100), when you need 10-100x faster inference than PyTorch, or for serving mod...
  - Canonical source: `optional-skills/mlops/tensorrt-llm/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`test-driven-development`** — TDD: enforce RED-GREEN-REFACTOR, tests before code.
  - Canonical source: `skills/software-development/test-driven-development/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`touchdesigner-mcp`** — Control a running TouchDesigner instance via twozero MCP — create operators, set parameters, wire connections, execute Python, build real-time visuals. 36 native tools.
  - Canonical source: `skills/creative/touchdesigner-mcp/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`unsloth`** — Unsloth: 2-5x faster LoRA/QLoRA fine-tuning, less VRAM.
  - Canonical source: `optional-skills/mlops/training/unsloth/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`watchers`** — Poll RSS, JSON APIs, and GitHub with watermark dedup.
  - Canonical source: `optional-skills/devops/watchers/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`webhook-subscriptions`** — Webhook subscriptions: event-driven agent runs.
  - Canonical source: `skills/devops/webhook-subscriptions/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`weights-and-biases`** — W&B: log ML experiments, sweeps, model registry, dashboards.
  - Canonical source: `skills/mlops/evaluation/weights-and-biases/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`whisper`** — OpenAI's general-purpose speech recognition model. Supports 99 languages, transcription, translation to English, and language identification. Six model sizes from tiny (39M params) to large (1550M params). Use for spe...
  - Canonical source: `optional-skills/mlops/whisper/SKILL.md`
  - Source repo / subsystem: `hermes-optional-skill` / `live-optional-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`writing-plans`** — Write implementation plans: bite-sized tasks, paths, code.
  - Canonical source: `skills/software-development/writing-plans/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`xurl`** — X/Twitter via xurl CLI: post, search, DM, media, v2 API.
  - Canonical source: `skills/social-media/xurl/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`youtube-content`** — YouTube transcripts to summaries, threads, blogs.
  - Canonical source: `skills/media/youtube-content/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`yuanbao`** — Yuanbao (元宝) groups: @mention users, query info/members.
  - Canonical source: `skills/yuanbao/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`

### Aliases

- **`enterprise-finance`** (alias) — Finance leaf: invoicing, budgeting, reporting against Stripe/NetSuite/QuickBooks.
  - Alternate source: `skills/enterprise-council/finance/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.
- **`enterprise-hr`** (alias) — HR leaf: recruitment screening, policy lookup, offer + termination workflows.
  - Alternate source: `skills/enterprise-council/hr/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.
- **`enterprise-judge`** (alias) — Validator / Judge: schema + policy + parallel-pass cross-checks on every leaf result.
  - Alternate source: `skills/enterprise-council/judge/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.
- **`enterprise-monitor`** (alias) — Post-run reviewer: scans the audit trail, proposes improvements, hands them to the curator.
  - Alternate source: `skills/enterprise-council/monitor/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.
- **`enterprise-operations`** (alias) — Operations leaf: logistics planning + execution, compliance checks + filings, incident declaration.
  - Alternate source: `skills/enterprise-council/operations/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.
- **`enterprise-orchestrator`** (alias) — Decompose a one-tap enterprise goal into autonomous tasks across domain agents.
  - Alternate source: `skills/enterprise-council/orchestrator/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.
- **`enterprise-sales`** (alias) — Sales leaf: lead tracking, proposal drafting + sending, contract execution, discounting.
  - Alternate source: `skills/enterprise-council/sales/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.
- **`hermes-agent`** (alias) — Configure, extend, or contribute to Hermes Agent.
  - Alternate source: `skills/autonomous-ai-agents/hermes-agent/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.
- **`opencode`** (alias) — Delegate coding to OpenCode CLI (features, PR review).
  - Alternate source: `skills/autonomous-ai-agents/opencode/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § K. Hermes-Specific Skills Layer for names that appear in source bodies but lack their own frontmatter._

## K2. Business / Commercial / Legal Layer

### Canonical

- **`commercial-strategist`** — Owns commercial angle: market, GTM, pricing, competition.
  - Canonical source: `skills/commercial-strategist/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Confidence: `DIRECTLY RECOVERED`
- **`commercial-strategy-growth-office`** — Use only for pricing, packaging, positioning, claims, GTM messaging, competitor positioning, RFP answer drafting. Does NOT write product code. Activated whenever externally-visible commercial copy or pricing changes. ...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/agents/commercial-strategy-growth-office.md`
  - Source repo / subsystem: `hazmat-agent` / `snapshot-agents`
  - Confidence: `DIRECTLY RECOVERED`
- **`enterprise-customer-service`** — CS leaf: ticket classification, knowledge base retrieval, escalation, mass communications.
  - Canonical source: `recovered-agent-sources/from-hermes-agent/enterprise-council/customer-service/SKILL.md`
  - Source repo / subsystem: `recovered-hermes-skill` / `snapshot-skills`
  - Confidence: `DIRECTLY RECOVERED`
  - **Has 1 alias(es) below.**
- **`legal-policy-contracts-trust-office`** — Use only for legal, policy, trust, and contractual artifacts (ToS, Privacy, NDA, MSA, SOW, DPA, Pilot Agreement, Security Addendum, sub-processor list, retention policy, store disclosures, trust portal copy). Every ou...
  - Canonical source: `recovered-agent-sources/from-hazmat-command/agents/legal-policy-contracts-trust-office.md`
  - Source repo / subsystem: `hazmat-agent` / `snapshot-agents`
  - Confidence: `DIRECTLY RECOVERED`

### Aliases

- **`enterprise-customer-service`** (alias) — CS leaf: ticket classification, knowledge base retrieval, escalation, mass communications.
  - Alternate source: `skills/enterprise-council/customer-service/SKILL.md`
  - Source repo / subsystem: `hermes-skill` / `live-skills`
  - Variant note: alias of the canonical entry above. See `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for the diff.

### Mentioned

_See `AOS_SUBAGENT_REGISTRY_COMPLETE.md` § K2. Business / Commercial / Legal Layer for names that appear in source bodies but lack their own frontmatter._
