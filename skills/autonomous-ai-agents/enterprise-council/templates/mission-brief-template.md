# Mission Brief — <short title>

**Date:** YYYY-MM-DD
**Author:** <chief-orchestrator / division>
**Run folder:** `docs/aos/runs/YYYY-MM-DD-<slug>/`
**Artifact slot:** `00-mission-brief.md`
**Companion governance:** `docs/governance/16-deliberative-planning-and-council-mode.md`

> A Mission Brief is the input contract for Council Mode and for any
> sprint that lands in a run folder. It restates the owner's intent
> in terms the AEO can act on without re-interpreting later. Fill
> every section; omit only when explicitly inapplicable and say so.

## Owner request (verbatim)

<paste the owner's words; do not paraphrase>

## Product / business objective

<one paragraph; what changes in the world if this lands>

## User / customer objective

<one paragraph; whose day gets better and how>

## Technical objective

<one paragraph; what the system does after this lands that it does
not do today>

## Explicit exclusions

- <thing this run will NOT do, even though it may seem in scope>
- <...>

## Known facts (cite source)

| Fact | Source | Date checked |
|---|---|---|
| | | |

## Uncertain assumptions

| Assumption | What changes if it's wrong |
|---|---|
| | |

## Required research

- [ ] Research Dossier under `docs/research/<topic>-<YYYY-MM-DD>.md`
- [ ] Lightweight variant of the research dossier (cite the
  decision per `governance/05`)
- [ ] No new research required; cite existing dossier:
  `docs/research/____.md`

## Constraints

- Time budget: <sprint length>
- Owner-only walls this run touches: <list or "none">
- Branch: <branch name>
- Validators that must remain green:
  `lint`, `typecheck`, `test`, `build`, `governance:check`,
  `agentos:check`, `council-codex:check`, `readiness:check`, `i18n:check`

## Risk class

- [ ] RC0 (cosmetic)
- [ ] RC1 (localized, well-covered)
- [ ] RC2 (material product / governance change)
- [ ] RC3 (security / compliance / commercial / legal / release-sensitive)
- [ ] RC4 (owner-only — stop; convert to planning note)

## Council Mode tier (if applicable)

- [ ] Not required (justify against `governance/16`)
- [ ] Lite (3 plans, optional red-team)
- [ ] Standard (4–6 plans, red-team required)
- [ ] RC3-strategy (6+ plans, red-team + independent verifier)

## Success criteria

- <criterion 1 — measurable>
- <criterion 2 — measurable>
- <criterion 3 — measurable>

## Non-negotiables

- Five owner-only walls preserved per `AGENTS.md`.
- Source-of-truth hierarchy preserved per `governance/01`.
- Maker-checker discipline preserved per `governance/06`.
- <run-specific non-negotiables>

## Definition of done

A bulleted list, written so a different agent / session could verify
each item without re-deriving intent:

- [ ] <observable outcome 1>
- [ ] <observable outcome 2>
- [ ] PR opened as draft per `AGENTS.md`
- [ ] Run folder contains all 13 numbered artifacts (per
  `docs/aos/README.md`)
- [ ] Owner handoff produced

## Out-of-band notes

<anything the synthesizer / red-team / reviewers must know that
doesn't fit the structured fields above>
