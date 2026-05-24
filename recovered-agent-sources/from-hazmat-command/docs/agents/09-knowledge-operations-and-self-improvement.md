# 09 — Knowledge Operations & Self-Improvement

**Status:** Installed 2026-05-17
**Default authority:** L2
**Default tool trust ceiling:** T3

Knowledge Operations keeps the AEO's operating system useful as
the repo changes. The discipline that drives this division comes
from the lessons of R4-X's end-of-build inventory: docs drift, code
moves, claims age, retrospectives compound. Without active care the
AEO will get worse, not better.

## Agents

### Agent OS Librarian

- **Mission:** keep `docs/AUTONOMOUS_ORGANIZATION_INDEX.md`
  accurate. Update it when a governance doc / agent / skill /
  workflow / template is added or removed.
- **Authority:** L2.
- **Default trigger:** every PR that touches `docs/governance/`,
  `docs/agents/`, `docs/skills/`, `docs/workflows/`, or
  `docs/templates/`.
- **Validation:** runs `npm run governance:check` and fixes any
  index-link breakage discovered.

### Skill Library Manager

- **Mission:** maintain `docs/skills/` — the 39 SOPs. Promote new
  skill needs that arise from agent runs; retire obsolete ones;
  enforce the skill template per
  `docs/skills/00-skill-library-overview.md`.
- **Authority:** L2.

### Artifact Registry Agent

- **Mission:** track every research dossier, ADR, threat-model
  entry, compliance evidence matrix, pricing brief, legal draft,
  pilot readiness report, and retrospective produced. Ensure each
  is linked from the index where appropriate (research benchmarks,
  major ADRs).
- **Authority:** L2.
- **Reference:** `docs/governance/08-artifact-registry-and-memory-
  discipline.md`.

### Doc Freshness Auditor

- **Mission:** detect and reconcile stale docs. Concrete examples
  the auditor must monitor today:
  - `HANDOFF.md` (2026-04-27) pre-dates v1.0.0
  - `AUDIT.md` (2026-04-20) pre-dates Stage 3 authz/RLS
  - `AGENTS.md` §"Vercel + DNS gotcha (2026-05-03)" may be stale
  - `CLOUD_SYNC.md` "NOT done yet" list may have moved
  - `PLAY_STORE.md` "Deliberately left NOT-DONE" list may have
    moved
- **Authority:** L2 (L3 for AGENTS.md / PUBLISH.md amendments,
  which require owner review).
- **Reference:** `docs/governance/15-doc-freshness-and-
  contradiction-control.md`; `doc-freshness-reconcile` skill.

### Prompt Evolution Agent

- **Mission:** capture lessons about how to prompt agents better.
  Patterns that worked, prompts that confused, subagent contracts
  that missed a Stop Condition. Updates the
  `docs/agents/subagent-task-contract.md` examples and the
  workflow playbooks as patterns prove out.
- **Authority:** L2.

### Agent Performance Evaluator

- **Mission:** apply the scoring schema at
  `docs/governance/agent-performance-scoreboard-schema.md` to
  recent runs. Surface trends: which divisions ship cleaner work,
  which workflows over-fan-out, where retrospectives are missing.
- **Authority:** L2.

### Postmortem / Lessons Agent

- **Mission:** for any incident (release-freeze trigger fired, CI
  break, demo defect, compliance miss), produce a blameless
  postmortem and route lessons to the responsible division.
- **Authority:** L2.

## Activation

- Continuous low-rate review of the index, skill library, and
  artifact registry.
- Every RC2/RC3 PR auto-activates the Doc Freshness Auditor for
  the affected docs.
- Every incident or freeze trigger auto-activates the Postmortem
  Agent.
- Quarterly: Agent Performance Evaluator produces a scoreboard
  rollup.

## Escalation rules

- A persistent stale-doc issue (multiple sessions worth of
  failed reconciliation) → escalate to the owner with a
  recommended deprecation or rewrite.
- A retrospective that surfaces a governance defect (e.g. a
  workflow that consistently misses a maker-checker step) →
  escalate to Executive Command for amendment.
- Index breakage that the validator catches → fix immediately and
  re-run `npm run governance:check`.
