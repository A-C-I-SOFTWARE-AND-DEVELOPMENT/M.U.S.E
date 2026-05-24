# 16 — Deliberative Planning and Council Mode

**Status:** Installed 2026-05-18 (Wave 1, additive to governance 00–15)
**Companion:** `docs/governance/17-codex-bounded-implementation-fabric.md`
**Implements:** `docs/workflows/deliberative-council-planning.md`
**Backing research:** `docs/research/council-mode-and-codex-fabric-design-2026-05-18.md`

This doc codifies when the AEO is required to run **Council Mode** —
a structured pre-execution deliberation pass — before authorizing
implementation. It does **not** redefine the change-risk matrix
(`governance/03`), the authority ladder (`governance/02`), the trust
zones (`governance/07`), or the maker-checker rule (`governance/06`).
Council Mode sits *upstream* of all of those.

## Why this matters here specifically

The existing AEO is strong on **execution** discipline (research
dossier, maker-checker, RC3 enumeration, claims substantiation,
counsel-review banner). It is thinner on **pre-execution decision
quality** — the moment between owner intent and the first PR. When
a single agent produces a single plausible-looking plan and
implementation begins from that plan, the AEO's downstream gates
catch defects but not strategic mistakes. Council Mode adds an
upstream gate so that for high-stakes work the plan itself is
generated from multiple lenses, scored against a rubric, synthesized,
and red-teamed before any code is touched.

## Definition

**Council Mode** is a workflow topology that runs the following loop
before implementation:

1. **Mission Brief** — owner intent restated, scope, non-negotiables,
   known facts, unknowns, success criteria, definition of done.
   Template: `docs/templates/mission-brief-template.md`.
2. **Evidence Bundle** — repo facts, external citations, prior
   decisions, applicable standards, risks. Template:
   `docs/templates/evidence-bundle-template.md`.
3. **Multi-plan generation** — N materially distinct plans, each
   optimized for a different lens (see §"Plan diversity" below).
   Template: `docs/templates/multi-plan-set-template.md`.
4. **Plan comparison and scoring** — rubric-driven scorecard plus
   extracted strengths, weaknesses, contradictions. Template:
   `docs/templates/plan-comparison-matrix-template.md`.
5. **Synthesis** — single master plan that adopts the strongest
   surviving ideas, names rejected ideas with rationale, and surfaces
   unresolved owner choices. Template:
   `docs/templates/synthesized-master-plan-template.md`.
6. **Red-team review** — independent attack on the synthesized plan
   (different agent/session than the synthesizer). Template:
   `docs/templates/red-team-plan-review-template.md`.
7. **Revision** — synthesizer revises once based on red-team.
8. **Owner approval gate** — owner reviews and signs off in writing
   before any implementation begins.
9. **Execution blueprint** — only after owner approval; converts the
   approved plan into waves, PRs, tests, artifacts. Template:
   `docs/templates/execution-blueprint-template.md`.

The execution blueprint may then be packaged for Codex per
governance/17.

## When Council Mode is required

Council Mode is **mandatory** for:

- Any RC3 change whose risk is strategy-weighted (not just
  implementation-weighted) — e.g. a new commercial claim, a pricing
  redesign, a regulatory positioning change, a new vendor selection,
  a major architectural shift.
- Any change that touches **public commercial copy** at scale (full
  landing page rewrite, trust-center rewrite, RFP answer-bank
  rewrite).
- Any **pricing or packaging redesign**.
- Any **legal-policy-set change** (ToS + Privacy + DPA together,
  MSA/SOW template change, sub-processor list change).
- Any **launch readiness sprint** prior to a real customer demo or
  pilot signing.
- Any **AEO/AOS self-modification** that adds or removes a division,
  validator, hook, governance doc, or rule.

Council Mode is **optional but recommended** for:

- RC2 changes that span more than two divisions.
- New product capabilities whose UX shape is not yet decided.
- Migrations with multiple viable paths.

Council Mode is **explicitly not required** for:

- RC0/RC1 changes.
- Bug fixes with one obvious root cause.
- Doc-freshness reconciliations.
- Anything covered by an existing workflow playbook whose sequence
  is already deterministic.

## Council Mode tiers

| Tier | Use for | Minimum plans | Red-team |
|---|---|---|---|
| **Lite** | Bounded RC2 work with a single primary lens | 3 | Optional |
| **Standard** | Major feature redesign, public commercial pages, architecture changes, pricing changes | 4–6 | Required |
| **RC3-strategy** | Auth/security/compliance/legal/release-sensitive changes with strategy weight; AEO/AOS self-modification | 6 minimum | Required + independent verifier |

## Plan diversity

Plans must be **materially distinct**. Six plans saying the same
thing is worse than one plan saying it clearly. Distinct lenses
typically include:

- **Market lens** — category leadership, premium narrative,
  differentiation.
- **Enterprise-trust lens** — procurement confidence, no
  overclaiming, citation discipline.
- **Product-experience lens** — UX flow, information architecture,
  CTA hierarchy.
- **Engineering-reality lens** — clean implementation, maintainability,
  risk containment, strong tests.
- **Minimal-leverage lens** — maximum perceived maturity, minimum
  risky change, best ROI for one sprint.
- **Moonshot-differentiation lens** — moat, category creation,
  what makes the product genuinely defensible.

For domain-specific decisions add the relevant specialist lens —
HazMat regulatory, data-privacy, fintech model-risk, etc.

## Scoring rubric

Score each plan from 1–10 on:

| Criterion |
|---|
| Strategic clarity |
| Market leadership potential |
| User value |
| Differentiation |
| Evidence grounding |
| Technical feasibility |
| Scope discipline |
| Risk management |
| Commercial credibility |
| Long-term extensibility |

Total possible score: 100. Scores alone are insufficient — each
review must also extract surviving ideas, rejected ideas,
assumptions needing proof, contradictions with repo reality, and
the most-cited buyer/engineer objection.

## Maker-checker discipline inside Council Mode

- The **synthesizer** of the master plan must not also red-team the
  plan. Different agent / session / human required.
- For RC3-strategy tier, the **verifier** is a third party who
  validates that the synthesis honored the cited evidence and that
  no rejected idea was silently re-introduced.
- The **owner** is the only party who can approve execution. No
  agent self-approves Council Mode output to start implementation.

## Trust-zone implications

- All Council Mode work is T1 (trusted reference read) and T2
  (internal draft write). No T3+ writes happen during Council Mode.
- Council Mode artifacts do **not** become source of truth (per
  `governance/01`); they sit at hierarchy tier 10–12 as evidence.
  Live code, AGENTS.md, PUBLISH.md, SKIPPED.md, governance docs
  remain authoritative.
- Council Mode never authorizes an owner-only wall override. If the
  synthesized plan would require an L4 action, the plan stops at
  the owner-approval gate with the L4 action surfaced separately.

## Failure modes Council Mode does **not** solve

- **False confidence from rubric scores.** Scores reflect the
  rubric, not ground truth. Treat as a discussion frame.
- **Persuasive-but-flawed critique.** Red-team writeups must cite
  evidence per `governance/05`. A critique without citation is
  rejected on review.
- **Council theater.** Six cosmetically-different plans converging
  on the same recommendation is failure, not consensus. Force the
  comparison matrix to surface divergent ideas; if it cannot, the
  plan set was not materially distinct.
- **Memory replacing documents.** Per `governance/08`, durable
  artifacts persist. Council Mode artifacts go into the run folder
  (`docs/aos/README.md`); they do not replace existing artifact
  templates.

## Run-folder integration

Every Council Mode session must commit its artifacts to a run folder
under `docs/aos/runs/YYYY-MM-DD-<slug>/` per `docs/aos/README.md`.
The numbered artifacts 00–06 are produced during Council Mode.
Artifacts 07–13 are produced during execution.

## Validator

`scripts/check-council-and-codex.mjs` (run via
`npm run council-codex:check`) asserts the templates and supporting
skills exist. It does **not** semantically score plans — that is
human + agent judgment per `governance/13`.

## Anti-patterns rejected on sight

- Council Mode skipped on a strategy-weighted RC3 change because
  "it was obvious."
- A "council" of agents all sharing the same lens (fake diversity).
- A red-team writeup that does not cite the evidence bundle.
- A synthesized plan that quietly re-introduces a rejected idea
  without rationale.
- Implementation starting before the owner-approval gate is
  recorded.
- A council artifact set committed without a corresponding entry
  in `docs/aos/runs/`.
