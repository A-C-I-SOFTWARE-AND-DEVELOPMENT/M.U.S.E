# <Phase name> report

> Replace `<Phase name>` with one of: Research, Planning, Approval,
> Implementation, Validation, Publish, Retrospective.
>
> This template is loaded by the
> [`phase-gated-workflow`](../../skills/phase-gated-workflow/SKILL.md)
> skill and consumed by `write_phase_report` in
> [`muse_cli/workflows.py`](../../muse_cli/workflows.py). The
> `## Plain English` section below is **mandatory** — the engine
> refuses bodies that omit it.

## Context

- **Job ID:** `<job-id>`
- **Phase:** `<phase-name>`
- **Trusted local:** `<true | false>`
- **Started at:** `<ISO timestamp>`
- **Completed at:** `<ISO timestamp or 'in progress'>`

## Inputs

- Prior phase: `<which phase fed this one>`
- Evidence considered: `<bullet list of files / docs / decisions>`
- Constraints respected: `<scope, deadline, security, etc.>`

## What was done

<!--
The structured / technical write-up. Use whatever sub-sections fit
the phase:

- Research: findings, unknowns, risks, hypotheses.
- Planning: chosen approach, alternatives considered, file-level plan.
- Approval: who reviewed, what was approved or rejected, why.
- Implementation: change summary, files touched, rationale for each.
- Validation: gates run, results, judge verdict.
- Publish: what was pushed, where (branch / PR / artifact), URLs.
- Retrospective: what worked, what didn't, what changes for next time.
-->

## Decisions

- **<decision title>** — `<rationale>`
- **<decision title>** — `<rationale>`

## Risks and follow-ups

- `<risk or follow-up>` — owner: `<who>`, due: `<when>`

## Plain English

<!--
MANDATORY. The engine refuses to write the report without this section.
Write three-to-six sentences, in normal language, for a reader who has
no context. Explain *what happened* in this phase and *why*. No jargon,
no codenames — if you wouldn't use the word in a stand-up with a new
hire, don't use it here.
-->

We ran the `<phase>` phase for job `<job-id>`. The goal was to
`<one-sentence goal>`. We `<one-sentence what we did>` and the result
was `<one-sentence outcome>`. The next phase, `<next-phase>`, will
`<one-sentence next step>`.

## Approval / sign-off

<!--
Filled in for approval-gated phases (approval, publish) and any phase
escalated via require_approval (destructive / secrets actions).
-->

- **Approver:** `<name / email / 'auto via trusted_local'>`
- **Approved at:** `<ISO timestamp>`
- **Note:** `<short note from the approver>`
