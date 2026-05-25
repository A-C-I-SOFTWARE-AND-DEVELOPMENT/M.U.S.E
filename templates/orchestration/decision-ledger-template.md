# Decision Ledger

## Decision
<!-- One sentence, active voice. The change you propose to make, not the
     deliberation. -->

## Plain English Summary
<!-- One short paragraph a non-technical reader could understand. Say what
     is happening and why someone should care. No jargon, no internal
     acronyms. -->

## Context
<!-- What triggered this decision? Cite the upstream artefact: user message,
     cron schedule, webhook, parent task, prior ledger. One paragraph; the
     reader picks this up cold. -->

## Evidence Reviewed
<!-- Concrete artefacts only. Hand-waving is not evidence. List as bullets:
       - Files: paths with line ranges (e.g. `agent/prompt_builder.py:142-180`)
       - Commands: verbatim, with a one-line result summary
       - Docs: path or URL + the section you used
       - Web sources: URL + retrieval date + a relevant quote
       - Prior Hermes memory / session notes: session id + ledger path
       - Gaps: what you did not check (feeds Open Risks below) -->

## Options Considered
<!-- At least two options. Each option fills Pros / Cons / Risk / Validation:

       ### Option A
       - Pros:
       - Cons:
       - Risk:
       - Validation:

       ### Option B
       - Pros:
       - Cons:
       - Risk:
       - Validation:

     "Defer" is always a legitimate option; list it if it applies. -->

## Selected Model / Worker
<!-- Which Hermes worker, subagent profile, or model will execute this?
     Name it precisely
     (e.g. `delegation` toolset -> `anthropic/claude-sonnet-4-6`). For
     in-process actions, name the main loop and its reasoning level. -->

## Why This Choice
<!-- Why the selected model/worker beats the alternatives for THIS task.
     Tie the choice back to the evidence above. -->

## Rejected Alternatives
<!-- For each option NOT picked, one short paragraph on why it lost.
     Include a fallback you would switch to if the primary choice fails. -->

## Cost / Latency / Quality Tradeoff
<!-- Estimated cost (USD or token budget), expected latency per turn, and
     the quality bar this choice clears. State the tradeoff explicitly. -->

## Validation Plan
<!-- How will you prove the decision was correct *after* acting on it?

       - Commands: runnable from a fresh shell, setup inlined
       - Manual checks: specific human observations, not "looks right"
       - Success criteria: binary "did it work?" — must be falsifiable -->

## Approval Required
<!-- Does this decision need a human approval before execution? Start with
     one of:
       - `no — <reason it's safe to proceed unattended>`
       - `yes — <named approver, e.g. user / Jeremiah>`
       - `defer — <what we're waiting on>` -->

## Final Decision
<!-- The verdict. Which option won, by name (Option A / Option B / Defer /
     Neither — re-research). -->

## Confidence
<!-- Start with one of `low` / `medium` / `high`, then one sentence of why. -->

## Open Risks
<!-- Anything the Validation Plan does not cover. Each risk gets a one-line
     mitigation or an honest "accepting this risk because…". -->

## Rollback Plan
<!-- Exact recovery procedure if the decision turns out wrong:
     `git revert <sha>`, plus any side-effect undo (cache invalidation, DB
     rollback, message recall, kanban un-claim).
     "I'll figure it out" is not acceptable. If genuinely irreversible, say
     so loudly with a HIGH-risk flag in Open Risks. -->
