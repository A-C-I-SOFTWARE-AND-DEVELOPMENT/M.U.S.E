# 04 — Workflow Router

**Status:** Installed 2026-05-17

The Workflow Router picks the minimum-adequate topology for a
task. Default to a single specialist; escalate only when complexity
warrants it.

## Topologies

| Topology | When | HazMat Command example |
|---|---|---|
| **Single specialist** | Localized task; one division; no cross-cutting impact | A typo fix in `docs/runbooks/secret-rotation.md` → Knowledge Operations / Doc Freshness Auditor; a `tests/lib/regulatory/placards.test.js` case → Engineering Factory / Compliance Engine Engineer |
| **Prompt chain** | Linear dependency: research → spec → build → verify | New 49 CFR rule coverage: 49 CFR Research Agent → CPO → Compliance Engine Engineer → Independent QA → Compliance Evidence Agent |
| **Routed task** | Single specialist whose identity depends on classification | A PR opened by an outside contributor (today: hypothetical — single-owner repo) routes to the right specialist based on `Affected domains` in the PR template |
| **Parallel review panel** | Multi-domain RC3 change needing simultaneous review | A change to `src/components/trust/MerkleRootViewer.jsx` reviewed in parallel by UX/UI Trust Agent (Product Studio), Security Architect (Assurance), Claims Substantiation Agent (Legal), Pilot Readiness Judge |
| **Orchestrator-worker swarm** | Independent subtasks that can run in parallel | Phase-1 of this AEO install dispatched 3 Explore subagents in parallel under a single Chief Orchestrator |
| **Evaluator-optimizer loop** | Iterate until pass | Compliance Evidence Agent evaluates a control narrative; Compliance Engine Engineer revises; loop until evidence cites pass |
| **Full multi-division enterprise run** | Major launch (new product, certification milestone, full pilot prep) | Pre-pilot orchestration: Pilot Demo Architect + Pilot Readiness Judge + every division contributes a checklist item |

## Decision tree

1. **Is the change RC0/RC1 and localized?** → Single specialist.
2. **Does the change require new evidence (research, compliance,
   commercial substantiation)?** → Prompt chain starting with the
   Research & Evidence Bureau.
3. **Does the change touch multiple RC3 surfaces simultaneously?** →
   Parallel review panel.
4. **Are there N independent subtasks worth running concurrently?**
   → Orchestrator-worker swarm; each subagent dispatched under the
   subagent task contract.
5. **Is there a quality gap that requires revision until pass?** →
   Evaluator-optimizer loop.
6. **Is this a pilot, launch, certification milestone, or pricing
   change?** → Full multi-division run.

## Intake template

Every dispatched workflow is captured using
`docs/templates/workflow-router-intake-template.md`. Required
fields: Trigger · Affected RC class · Affected divisions · Chosen
topology · Justification · Expected artifacts.

## Anti-patterns

- "Multi-agent because the task feels big." If the task is
  sequential by nature, a chain is fine; do not parallelize for
  show.
- Activating the full Commercial Office for a typo fix on
  `marketing/04-launch-checklist.md` — that's a single-specialist
  Knowledge Operations job.
- Using an evaluator-optimizer loop without a clear pass condition
  — declare exit criteria before starting.
- Skipping the intake template "because it's obvious." The
  template doubles as the retrospective input.
