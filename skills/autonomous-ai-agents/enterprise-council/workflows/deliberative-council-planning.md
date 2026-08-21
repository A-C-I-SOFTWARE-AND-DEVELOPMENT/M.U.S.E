# Workflow — Deliberative Council Planning

## Trigger

Owner request, autonomous-sprint kickoff, or chief-orchestrator
routing decision flags one of the Council-Mode-mandatory cases in
`docs/governance/16-deliberative-planning-and-council-mode.md`:

- Any RC3 change whose risk is strategy-weighted (new commercial
  claim, pricing redesign, regulatory positioning, vendor
  selection, major architectural shift).
- Public commercial copy rewrite at scale (landing page, trust
  center, RFP answer-bank).
- Pricing or packaging redesign.
- Legal-policy-set change touching more than one document together.
- Launch readiness sprint prior to a real customer demo or pilot
  signing.
- AEO/AOS self-modification (adding/removing a division, validator,
  hook, governance doc, or rule).

If the work is RC0/RC1, a deterministic bug fix, or covered by an
existing workflow whose sequence is fixed, **do not** run this
workflow — use the matching specialist workflow instead.

## Required Divisions

Executive Command & Orchestration (chief-orchestrator) · Research &
Evidence Bureau (evidence) · the relevant domain division for each
plan lens (Commercial · Product Studio · Engineering Factory ·
Assurance / Security / Compliance · Legal · Pilot Operations) ·
Knowledge Operations (artifact persistence and retrospective).

## Required Research Artifact

Evidence Bundle is mandatory. If the topic also triggers the
research-before-plan rule per `governance/05`, a Research Dossier
under `docs/research/<topic>-<YYYY-MM-DD>.md` is additionally
required and is referenced from the Evidence Bundle.

## Agent Topology

Routed prompt chain with parallel multi-plan generation, then
parallel cross-review, then sequential synthesis → red-team →
revision → owner approval. No agent self-approves; the synthesizer
must not red-team.

## Sequence

1. **Mission Brief** — chief-orchestrator authors using
   `templates/mission-brief-template.md`. Restates owner intent,
   scope, exclusions, known facts, unknowns, constraints, risk class,
   success criteria, definition of done. Commits to
   `docs/aos/runs/YYYY-MM-DD-<slug>/00-mission-brief.md`.
2. **Evidence Bundle** — research-evidence-bureau assembles repo
   facts, external citations (NIST / OWASP / ISO / 49 CFR / vendor
   docs with access dates), prior decisions, applicable standards,
   risks. Uses `templates/evidence-bundle-template.md`. Commits
   to `01-evidence-bundle.md`. If a Research Dossier is required,
   it is produced first and cited.
3. **Risk classification** — chief-orchestrator confirms RC class
   and Council Mode tier (Lite / Standard / RC3-strategy) per
   `governance/16`. Commits to `02-risk-classification.md`.
4. **Plan generation (parallel)** — N skills dispatched in
   parallel, each producing one plan optimized for a distinct lens
   (Market · Enterprise Trust · Product UX · Engineering Reality ·
   Minimal High-Leverage · Moonshot Differentiation, plus domain
   specialist as needed). Skill: `multi-plan-council-run` (manual
   invocation only). Uses
   `templates/multi-plan-set-template.md`. Commits to
   `03-options-or-council-plans.md`.
5. **Plan comparison and scoring (parallel)** — skill
   `plan-comparison-scorecard` scores each plan 1–10 across the
   10-criterion rubric in `governance/16` and extracts surviving
   ideas, rejected ideas, contradictions. Reviewer must be a
   different session than any plan author. Uses
   `templates/plan-comparison-matrix-template.md`. Appends to
   `03-options-or-council-plans.md` or attaches as supplement.
6. **Synthesis** — skill `master-plan-synthesis` produces the
   master plan, names adopted/rejected ideas with rationale,
   surfaces unresolved owner choices. Synthesizer must not red-team.
   Uses `templates/synthesized-master-plan-template.md`.
   Commits to `04-synthesized-plan.md`.
7. **Red-team review** — skill `red-team-plan-review` attacks the
   master plan; cites the evidence bundle for every critique. Run
   by a different agent / session than the synthesizer. Uses
   `templates/red-team-plan-review-template.md`. Commits to
   `05-red-team-review.md`.
8. **Revision (once)** — synthesizer revises the master plan based
   on red-team findings. Updates `04-synthesized-plan.md` with a
   dated revision note; preserves the original adopted/rejected
   audit trail.
9. **Owner approval gate** — owner reviews the revised master plan
   and the red-team review. Owner approval is recorded in writing
   (PR comment, commit message, or appended to the master plan with
   the owner's GitHub handle). **No implementation begins before
   this step.**
10. **Execution blueprint** — skill `execution-blueprint-compile`
    converts the approved plan into waves, PR sequence, subagent
    assignments, artifacts, validation commands, acceptance criteria,
    rollback plan, owner-only-action list. Uses
    `templates/execution-blueprint-template.md`. Commits to
    `06-execution-blueprint.md`.
11. **Handoff** — execution is routed per `governance/04` to the
    matching execution workflow (security-or-authz-change,
    compliance-rule-change, etc.). For Codex-dispatched work, the
    handoff includes the Codex Task Packet per
    `workflows/codex-implementation-fabric.md`.

## Parallelization Opportunities

- Plan generation across the N lenses runs in parallel.
- Plan comparison/scoring runs in parallel once all plans exist.
- Research Dossier (if required) can run in parallel with Mission
  Brief authorship; both must complete before the Evidence Bundle.

## Maker-Checker Review Points

- Builder of the master plan (synthesizer) ≠ red-team reviewer.
- For RC3-strategy tier: an independent verifier confirms that the
  synthesis honored the evidence and that no rejected idea was
  silently re-introduced.
- Owner is the only party who can approve execution.

## Final Outputs

Mission Brief · Evidence Bundle · Risk classification ·
N materially-distinct plans · Plan comparison matrix · Synthesized
master plan (revised once after red-team) · Red-team review ·
Execution blueprint · Owner approval record · Retrospective (after
execution completes, per `governance/16` and `governance/13`).

All committed to the run folder under `docs/aos/runs/YYYY-MM-DD-<slug>/`.

## Acceptance Criteria

- Mission Brief, Evidence Bundle, plans, scorecard, synthesized
  master plan, red-team, execution blueprint all exist as files in
  the run folder with the required numbered names.
- Plans are materially distinct (the comparison matrix surfaces
  divergent ideas; if it cannot, the set is not distinct).
- Every red-team critique cites the evidence bundle.
- Synthesizer ≠ red-team reviewer (different agent / session /
  human).
- Owner approval recorded in writing before execution.
- Validator `npm run council-codex:check` passes.

## Anti-patterns rejected on sight

- Council Mode skipped on a strategy-weighted RC3 change because
  "it was obvious."
- Six plans converging on the same recommendation without any
  divergent strength worth preserving (fake diversity).
- A red-team writeup whose critiques have no evidence citation.
- A synthesized plan that quietly re-introduces a rejected idea
  without rationale.
- Implementation starting before the owner-approval gate is
  recorded.
- Council artifacts authored outside the run folder.
- A Codex packet dispatched before the execution blueprint exists.
