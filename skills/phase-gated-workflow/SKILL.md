---
name: phase-gated-workflow
description: "Drive a Hermes job through the eight phase-gated stages — intake, research, planning, approval, implementation, validation, publish, retrospective — with audit-trail-grade transitions. Refuses to let a session 'just keep going' without leaving a recorded reason for each gate."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows, android]
metadata:
  hermes:
    tags:
      - workflow
      - gate
      - approval
      - audit
      - orchestration
      - governance
      - phase-gated
    related_skills:
      - decision-quality-gate
      - local-quality-gate
      - hermes-orchestration-pipeline
    homepage: https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent
---

# Phase-gated workflow

This skill teaches Hermes how to drive a single job through the
**eight phase-gated stages**: `intake`, `research`, `planning`,
`approval`, `implementation`, `validation`, `publish`,
`retrospective`. Each phase has a status, each transition leaves a
reason in an audit trail, and certain phases simply cannot be entered
without explicit approval.

The engine lives in
[`hermes_cli/workflows.py`](../../hermes_cli/workflows.py); the data
shapes live in
[`hermes_cli/workflow_models.py`](../../hermes_cli/workflow_models.py);
the full contract is in
[`docs/orchestration/phase-gated-workflows.md`](../../docs/orchestration/phase-gated-workflows.md).

## When to load this skill

Load `/phase-gated-workflow` whenever you are:

- Driving a brand-new orchestrator job from `submit_job` to
  `publish_job`.
- Resuming a job and you don't know which phase it is on.
- Reviewing whether a phase is allowed to advance (especially
  `implementation` or `publish`).
- Writing a phase report and want the canonical template to follow.

If the only thing you need is "what phase am I on", call
`get_current_phase(job)` and stop — you don't need the skill loaded.

## The contract, in one screen

1. **Always call `initialize_phases(job)` first.** It is idempotent.
2. **Every phase report includes a `## Plain English` section.** No
   plain English, no write — the engine will refuse the body.
3. **Approval is explicit.** `approve_phase(job, phase, approver,
   note)` is the only way to flip an approval-gated phase to
   `approved`. Do not write `phase.status = "approved"` by hand;
   `status.json` is hand-editable but the audit trail must record who
   approved and why.
4. **Destructive and secrets actions always escalate.** If you are
   about to call something that deletes data, force-pushes,
   manipulates credentials, or touches anything in
   `ALWAYS_APPROVED_ACTIONS`, you **must** call
   `require_approval(job, phase, action, reason=...)` first.
   `trusted_local` does not exempt you.
5. **Publishing always needs a human.** The `publish` phase lands in
   `needs_approval` on transition. `trusted_local` does not downgrade
   this — anything visible to other humans needs a human green light.

## Canonical walk through the phases

```python
from hermes_cli.workflows import (
    initialize_phases, transition_phase, complete_phase,
    approve_phase, write_phase_report,
)
from hermes_cli.workflow_models import (
    RESEARCH, PLANNING, APPROVAL, IMPLEMENTATION,
    VALIDATION, PUBLISH, RETROSPECTIVE,
)

initialize_phases(job)

# Research — auto-startable.
transition_phase(job, RESEARCH, RESEARCH, "kicking off")
write_phase_report(job, RESEARCH, research_report_md)
complete_phase(job, RESEARCH, reason="evidence collected")

# Planning — needs research evidence (handled by the engine).
transition_phase(job, RESEARCH, PLANNING, "evidence is in")
write_phase_report(job, PLANNING, plan_md)
complete_phase(job, PLANNING, reason="plan complete")

# Approval — lands in needs_approval until a human signs off.
transition_phase(job, PLANNING, APPROVAL, "submit plan for review")
write_phase_report(job, APPROVAL, approval_md)
approve_phase(job, APPROVAL, approver="alice@example.com",
              note="approach LGTM")

# Implementation — only allowed once APPROVAL is approved
# (or trusted_local is true).
transition_phase(job, APPROVAL, IMPLEMENTATION, "approved → go")
write_phase_report(job, IMPLEMENTATION, impl_md)
complete_phase(job, IMPLEMENTATION, reason="patch applied")

# Validation — auto-startable after implementation completes.
transition_phase(job, IMPLEMENTATION, VALIDATION, "gates")
write_phase_report(job, VALIDATION, validation_md)
complete_phase(job, VALIDATION, reason="all gates green")

# Publish — needs_approval again, no matter the trust level.
transition_phase(job, VALIDATION, PUBLISH, "promote artifact")
write_phase_report(job, PUBLISH, publish_md)
approve_phase(job, PUBLISH, approver="alice@example.com", note="ship")

# Retrospective — auto-startable.
transition_phase(job, PUBLISH, RETROSPECTIVE, "wrap up")
write_phase_report(job, RETROSPECTIVE, retro_md)
complete_phase(job, RETROSPECTIVE, reason="lessons captured")
```

## Writing a phase report

Use [`templates/orchestration/phase-plan.md`](../../templates/orchestration/phase-plan.md)
as the starting point. The mandatory `## Plain English` section
explains, in normal language with no jargon, *what happened in this
phase and why*. Keep it short — three to six sentences is the right
length. If you find yourself wanting to write a paragraph for every
sub-decision, those belong in the higher-level sections of the
report.

The Plain English section is for the future reader who has none of
your context: a human reviewer, a Judge invocation a week from now,
or a later Hermes session that resumes this job. If the section reads
cleanly to a person who has never seen this codebase, it's done.

## Common pitfalls

- **Skipping the approval phase.** The engine refuses transitions
  that skip a phase in `PHASE_ORDER`. Walk one step at a time.
- **Starting `publish` in place.** `publish` is approval-gated; you
  cannot call `transition_phase(job, publish, publish, …)`. Advance
  into it from `validation`, then call `approve_phase`.
- **Forgetting the Plain English section.** `write_phase_report`
  raises `WorkflowError` if it is missing. The fix is to write the
  section, not to disable the check.
- **Using `trusted_local` for publish.** It does not apply. Publish
  always needs explicit approval.
- **Editing `status.json` by hand to "skip the gate".** You will lose
  the audit trail and the next call into the engine may reject the
  state. Use the public API.

## Cross-references

- [`docs/orchestration/phase-gated-workflows.md`](../../docs/orchestration/phase-gated-workflows.md) — full contract.
- [`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md) — where the per-phase history feeds in.
- [`docs/orchestration/local-validation-gates.md`](../../docs/orchestration/local-validation-gates.md) — what runs during the `validation` phase.
- [`templates/orchestration/phase-plan.md`](../../templates/orchestration/phase-plan.md) — report template.
- [`hermes_cli/workflows.py`](../../hermes_cli/workflows.py) — engine.
- [`hermes_cli/workflow_models.py`](../../hermes_cli/workflow_models.py) — shapes.
