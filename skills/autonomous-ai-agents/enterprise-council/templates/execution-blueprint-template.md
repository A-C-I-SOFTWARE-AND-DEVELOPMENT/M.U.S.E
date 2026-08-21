# Execution Blueprint — <short title>

**Date:** YYYY-MM-DD
**Author:** <chief-orchestrator after owner approval of master plan>
**Run folder:** `docs/aos/runs/YYYY-MM-DD-<slug>/`
**Artifact slot:** `06-execution-blueprint.md`
**Companion governance:** `docs/governance/04-workflow-router.md`,
`docs/governance/16-deliberative-planning-and-council-mode.md`,
`docs/governance/17-codex-bounded-implementation-fabric.md`

> The Execution Blueprint converts an owner-approved Synthesized
> Master Plan into the implementation contract: epics, phases,
> PR sequence, subagent assignments, validation commands, acceptance
> criteria, rollback plan, and the owner-only action list. It is
> the bridge between Council Mode and the deterministic execution
> workflows. No new strategic decisions belong here.

## Owner approval reference

- Approval recorded at: <PR comment URL / commit SHA / appended
  approval block in master plan>
- Approver: <owner GitHub handle>
- Date: YYYY-MM-DD

If this section is empty, the blueprint is not yet authorized.
Implementation does not begin.

## Epics

| Epic | Wave | Owner subagent / division | Reviewer | Verifier (RC3) |
|---|---|---|---|---|
| E1 | 1 | | | |
| E2 | 1 | | | |
| E3 | 2 | | | |

## PR sequence

| Order | PR title (target) | Branch | Risk class | Workflow playbook | Builder | Reviewer | Verifier |
|---|---|---|---|---|---|---|---|
| 1 | | `claude/____` | RC___ | `docs/workflows/____.md` | | | |
| 2 | | `claude/____` | RC___ | `docs/workflows/____.md` | | | |

For each PR, name:

- Files that will change (allow-list).
- Files that must NOT change (forbidden-list — always includes
  constitutional surfaces).
- Tests added or changed.
- Validators that must remain green.
- Acceptance check.
- Rollback procedure.

## Codex packets (if any)

For each Codex packet to be dispatched in this run, instantiate
`templates/codex-task-package-template.md` and reference it:

| Packet | Target PR | Allow-list | Forbidden-list | Acceptance | Reviewer | Verifier |
|---|---|---|---|---|---|---|
| P1 | | | | | | |

Constitutional surfaces (AGENTS.md, PUBLISH.md, SKIPPED.md, CLAUDE.md,
`.claude/rules/`, `.claude/agents/`, `.claude/skills/`,
`.claude/hooks/`, `.claude/settings.json`) are **always** in the
forbidden-list per `governance/17`.

## Validation commands (must remain green)

- `npm run lint`
- `npm run typecheck`
- `npm test` (named baseline)
- `npm run build`
- `npm run governance:check`
- `npm run agentos:check`
- `npm run council-codex:check`
- `npm run readiness:check`
- `npm run i18n:check` (if i18n affected)
- `npm run test:e2e` (if e2e-covered)
- `npx vitest run tests/claude-os` (hook regression)

## Acceptance criteria (sprint-wide)

- [ ] Every PR merged or explicitly deferred with reason.
- [ ] Every run-folder artifact present (00–13 per
  `docs/aos/README.md`).
- [ ] No owner-only wall touched without surfacing for owner.
- [ ] All validators green on every merged PR.
- [ ] Retrospective authored in `13-retrospective.md`.

## Rollback plan

| Wave | Revert SHA or PR | Doc procedure | Time-to-rollback target |
|---|---|---|---|
| 1 | | `docs/runbooks/____.md` | |
| 2 | | `docs/runbooks/____.md` | |

If any wave lacks a stated rollback, the blueprint is incomplete.

## Owner-only action list

| Action | Why | Runbook | Blocks which wave |
|---|---|---|---|
| (e.g. set env var on Vercel) | | `docs/runbooks/____.md` | |
| (e.g. flip GrowthBook flag) | | | |
| (e.g. DNS change) | | | |

Per `AGENTS.md`, agents never perform these actions. Each is
surfaced for the owner; the dependent wave does not begin until
the owner reports completion.

## Doc updates

| Doc | Reason | Wave | Author |
|---|---|---|---|
| `docs/AUTONOMOUS_ORGANIZATION_INDEX.md` | new entries from this sprint | last | Knowledge Ops |
| `HANDOFF.md` | only if session-resumption context materially moved | last | Knowledge Ops |
| Compliance / ISMS evidence | if RC3 security/compliance touched | per wave | Assurance Office |

## Anti-patterns rejected on sight

- A blueprint with no owner approval reference.
- A PR sequence whose builder == reviewer.
- A Codex packet allow-list that includes a constitutional surface.
- A wave with no stated rollback.
- New strategic decisions made in the blueprint that were not in
  the synthesized master plan.
- An owner-only action embedded in a PR instead of surfaced for
  owner.
