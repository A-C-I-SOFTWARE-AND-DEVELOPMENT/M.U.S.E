---
name: enterprise-council
description: "Route work through a governed multi-agent review council."
version: 3.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [council, orchestrator, audit, review, governance, release, compliance, security, product, qa]
    activation_phrases:
      - "audit repo"
      - "audit the repo"
      - "audit this repo"
      - "enterprise hardening"
      - "launch readiness"
      - "activate the council"
      - "run the council"
      - "convene the council"
      - "council review"
      - "go / no-go review"
      - "red team this plan"
    related_skills: [claude-code, codex, hermes-agent, opencode, merge-reconciler]
---

# Enterprise Council

A governed review council you convene over a goal, a repo, or a plan.
It is a **routing and gating layer**: it classifies risk, picks a
workflow, dispatches a small set of role prompts as sub-agents, and
refuses to let the run finish without evidence and an owner gate.

Use it when a request touches more than one of: engineering, UX,
security, compliance, legal, pricing, release, regulated output,
pilot readiness. For single-domain work, do the work directly. A
council on a one-file change is pure overhead.

## Layout

```
enterprise-council/
|- SKILL.md                     <- you are here
|- runnable-agents/             <- the 6 always-on council seats + the roster
|- agents/                      <- 9 full role prompts (dispatch these)
|- specialists/                 <- 6 on-demand expert cards (when to use / not use)
|- workers/                     <- 8 files: 7 execution lanes (no vote) + worker-templates.md
|- workflows/                   <- 12 playbooks; start at 00-workflow-overview.md
|- rules/                       <- 6 path-scoped constitutional rules
|- templates/                   <- 22 artifact templates (the output shapes)
|- prompts/                     <- 5 copy-paste driver prompts
|- slack/                       <- team usage rules for the Slack surface
`- super-specialist-skills.md   <- narrow procedures that are skills, not agents
```

The four tiers are not interchangeable:

| Tier | Directory | Votes? | Cardinality |
| --- | --- | --- | --- |
| Council seat | `runnable-agents/` | yes | capped at 6, always on |
| Role prompt | `agents/` | yes | dispatched per request |
| Specialist | `specialists/` | advisory | summoned on demand only |
| Worker | `workers/` | no | executes an approved lane |

`runnable-agents/active-council.md` is the roster and the cap.

## How to activate

### Step 0 - Load context

1. The repo's own `AGENTS.md` and `CLAUDE.md`, if present.
2. `runnable-agents/active-council.md`.
3. Only the `rules/` that match the request paths. They are
   path-scoped, not all-on. `rules/00-commercial-delivery-standard.md`
   is the one unconditional rule.

### Step 1 - Routing decision (your first message)

Emit, before doing anything else:

- **Risk class** RC0-RC4, per the scale in
  `templates/mission-brief-template.md`. **RC4 stops here** - convert
  it to a planning note and surface to the owner.
- **Workflow** picked from `workflows/`. If none fits, escalate rather
  than improvise.
- **Goal slug** - lowercased, hyphenated, 40 chars or fewer. Memory
  namespace `council/<slug>`.
- **Members to dispatch** - name each by file path.
- **Owner-only walls** that this request touches.
- **Todo list** - one entry per member, one per gate.

### Step 2 - Dispatch

Use `delegate_task` with the chosen `agents/<name>.md` (or
`specialists/<name>.md`) as the system prompt for the sub-agent. Track
with `todo`. Persist artifacts with `memory` under
`council/<slug>/<role>`. Use `session_search` to find prior councils
on the same slug.

### Step 3 - Run the sequence

Full Council Mode is 12 stages. Do not skip stage 7 or 8.

1. Mission brief - `templates/mission-brief-template.md`
2. Evidence bundle - `templates/evidence-bundle-template.md`
3. Risk classification
4. Multi-plan run - `templates/multi-plan-set-template.md`
5. Plan comparison - `templates/plan-comparison-matrix-template.md`
6. Synthesis - `templates/synthesized-master-plan-template.md`
7. Red-team review - `templates/red-team-plan-review-template.md`
8. **Owner-approval gate. STOP. Surface to the owner.**
9. Execution blueprint - `templates/execution-blueprint-template.md`
10. Implementation, via a `workers/` lane. Codex packets use
    `templates/codex-task-package-template.md`.
11. Verification - tests, security review at RC3, release handoff
12. Retrospective - `templates/agent-run-retrospective-template.md`

For a light ask the sequence collapses to 1, 2, 3, 7, 8.

`workflows/deliberative-council-planning.md` is the long form of this
sequence; `workflows/codex-implementation-fabric.md` is the long form
of stage 10.

## Owner-only walls (absolute)

1. Spending money on ads.
2. Posting to public social accounts.
3. Creating new third-party accounts.
4. OAuth into any third-party service.
5. Submitting to an app store.

Plus the release walls: merges to `main`/`master`, force-push,
production deploys, package publishes, DNS changes. PRs the council
opens are draft-only. If a deny hook or a missing permission blocks an
action, **the deny is correct**. Surface it; do not route around it.

## Routing

| Request signal | Dispatch | Workflow |
| --- | --- | --- |
| audit a repo | `agents/executive-operator.md`, then `agents/senior-fullstack-architect.md` + `agents/security-compliance-auditor.md` + `agents/product-strategy-agent.md` + `agents/qa-release-commander.md` | - |
| build a feature | `agents/executive-operator.md`, then `agents/senior-fullstack-architect.md`, then `agents/qa-release-commander.md` | `workflows/new-product-or-major-feature.md` |
| a cross-cutting defect | `agents/senior-fullstack-architect.md` + `agents/qa-release-commander.md` | `workflows/complex-bug-fix.md` |
| authz / RLS / trust boundary | `agents/security-compliance-auditor.md` | `workflows/security-or-authz-change.md` |
| launch, demo, or pilot go/no-go | `agents/qa-release-commander.md`, rubric `specialists/release-readiness-judge.md` | `workflows/pilot-demo-readiness.md` |
| enterprise hardening, RFP, DPA | `agents/security-compliance-auditor.md` + `specialists/research-evidence-bureau.md` | `workflows/enterprise-procurement-readiness.md` |
| regulated output | `specialists/research-evidence-bureau.md` + `agents/security-compliance-auditor.md` | `workflows/compliance-rule-change.md` |
| product or UX judgment | `agents/product-strategy-agent.md` + `agents/psychology-ux-agent.md` | - |
| pricing or packaging change | `specialists/commercial-strategist.md` | `workflows/pricing-and-packaging.md` |
| positioning or public copy | `specialists/commercial-strategist.md` | `workflows/marketing-gtm.md` |
| contract or policy draft | `agents/executive-operator.md` + `specialists/research-evidence-bureau.md` | `workflows/legal-document-generation.md` |
| Claude Code / Codex orchestration | `agents/claude-codex-orchestrator.md` | `workflows/codex-implementation-fabric.md` |
| knowledge capture, run history | `agents/memory-knowledge-curator.md` | - |
| full council | `runnable-agents/active-council.md`, all 6 seats | `workflows/deliberative-council-planning.md` |

`agents/chief-orchestrator.md` is an alias of `executive-operator`;
either name resolves to the same role.

## Anti-patterns the council rejects

- Answering a specialist question yourself instead of dispatching.
- Skipping the red-team or owner-approval gate "for speed".
- Marking work complete without showing verification command output.
- A compliance, security, commercial, or legal claim with no citation.
- Widening scope; refactoring what was not broken.
- Bundling unrelated changes into one PR.
- Bypassing an owner-only wall or branch protection.
- Convening the council on work that one agent could finish.
