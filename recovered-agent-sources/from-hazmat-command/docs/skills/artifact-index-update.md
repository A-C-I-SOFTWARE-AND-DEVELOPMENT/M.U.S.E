# Skill — artifact-index-update

## Purpose

Keep `docs/AUTONOMOUS_ORGANIZATION_INDEX.md` accurate as
governance docs / agents / skills / workflows / templates /
benchmark research artifacts land.

## Triggers

- A new file is added under `docs/governance/`, `docs/agents/`,
  `docs/skills/`, `docs/workflows/`, `docs/templates/`, or
  `docs/research/` (benchmark class).
- A file is renamed or removed.
- The validator `npm run governance:check` reports broken
  links.

## Required Inputs

- The current index.
- The file(s) added / changed.
- The validator output.

## Research Required

- The validator scope (file existence + required sections —
  it does NOT do semantic checks).

## Step-by-Step Method

1. Add the new file to the appropriate section of the index
   (governance / agents / skills / workflows / templates /
   research benchmarks).
2. Use the same formatting as adjacent entries (table row or
   bullet).
3. Run `npm run governance:check`; confirm exit 0.
4. If a file was removed, remove its link from the index and
   confirm no other doc references it (cross-grep).
5. Commit the index change in the same PR as the file change.

## Deliverable Format

The updated index plus the file change. Both land in the same
PR.

## Quality Checklist

- [ ] `npm run governance:check` exit 0
- [ ] New file linked in the right section
- [ ] No dangling reference to a removed file

## Escalation Triggers

- Validator persistently failing → halt; investigate root cause
  (broken file, missing section, validator misfire).
- Renaming a governance doc → L3 maker-checker because other
  files almost certainly reference it.

## Related Agents

- Agent OS Librarian (Knowledge Operations)
- Release Engineering Agent (Engineering Factory)

## Related Artifacts

- `docs/AUTONOMOUS_ORGANIZATION_INDEX.md`
- `scripts/check-governance-index.mjs`
