---
name: decision-quality-gate
description: "Force Hermes to produce a visible decision ledger before non-trivial actions — plain English summary, evidence, options, model/worker choice, why-this-choice, rejected alternatives, cost/latency/quality, validation, approval, confidence, risks, rollback. Replaces hidden chain-of-thought with auditable reasoning."
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows, android]
metadata:
  hermes:
    tags: [decision, gate, quality, validation, audit, orchestration, governance, explainability]
    related_skills:
      - research-validator
      - enterprise-orchestrator
      - enterprise-judge
      - plan
      - writing-plans
      - spike
    homepage: https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent
---

# Decision Quality Gate

This is the gate Hermes passes through before any non-trivial
decision. Instead of an invisible chain-of-thought, Hermes produces a
**visible decision ledger** — a structured markdown record that the
user (or a later session, or a reviewer, or the Judge) can read,
audit, and challenge.

The principle is simple: hidden reasoning is not auditable, and an
agent that cannot be audited cannot be trusted with autonomy. The
gate externalises the reasoning that actually matters — what evidence
was considered, which options were on the table, which worker/model
was chosen and why, what the cost and quality tradeoff was, who has
to approve, how the result will be validated, what the open risks
are, and how to roll back if things go wrong.

## When to invoke this skill

Load this skill (`/skill decision-quality-gate`) — or have the
orchestrator load it automatically — for any task that is:

1. **Multi-step or multi-file.** Anything that touches more than one
   file, more than one subsystem, or more than one external service.
2. **Irreversible or expensive.** Anything that mutates production
   state, costs money, writes to shared storage, sends external
   messages, or pushes to a remote.
3. **Model/worker selection.** Anything where Hermes is picking which
   subagent, profile, or model to delegate to. The selection itself
   is a decision and deserves a ledger entry.
4. **Cross-session continuation.** Anything resumed from a prior
   session, a cron job, a webhook, or a kanban claim — the new
   operator (human or agent) needs the ledger to catch up.
5. **User asked "are you sure?" / "why?"** — that is a request for a
   ledger; produce one.

### When NOT to invoke

Skip the gate for **trivial single-step actions** where the cost of
producing a ledger exceeds the cost of being wrong:

- One-line answers to factual questions ("what's the capital of France?")
- Single read-only commands the user explicitly asked for (`ls`, `git status`)
- Continuation of an action that already has a ledger upstream
- Inside-loop bookkeeping (claiming a kanban task, posting a heartbeat)

A useful heuristic: **if you would have produced hidden
chain-of-thought to plan this action, produce a ledger instead.** If
you would have just acted, no ledger needed.

## What the gate produces

Exactly one artefact: a **decision ledger** following the schema in
[`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md).
The schema has **fifteen mandatory H2 sections** (see below). A
ready-to-fill blank is at
[`templates/orchestration/decision-ledger-template.md`](../../templates/orchestration/decision-ledger-template.md);
the Python helper
[`hermes_cli/decision_ledger.py`](../../hermes_cli/decision_ledger.py)
renders, parses, validates, and persists ledgers.

The ledger lives in one of three places depending on context:

| Context | Ledger location |
|---|---|
| Interactive CLI session | Inline in chat reply, also persisted to `$HERMES_HOME/decisions/<session_id>/<seq>-<slug>.md` |
| Cron / webhook / background | `$HERMES_HOME/decisions/<session_id>/<seq>-<slug>.md` and surfaced in the delivery footer |
| Kanban worker | Attached as a `kanban_comment` on the task plus the persisted file |
| Enterprise council leaf | Returned as the `decision_ledger` key in the structured result the Judge inspects |

The persisted copy is plain markdown so it shows up in `grep`, in PR
diffs, and in the curator's review pass. Do not encrypt or compress
ledgers — they are deliberately visible.

## The fifteen sections

Work through the template top-to-bottom. You do not have to fill
every section to the same depth — match the depth to the stakes — but
every section must be present and non-empty. **An empty section means
the gate has not actually been passed.**

1. **`## Decision`** — one sentence, active voice. "We will change X
   from A to B." If you cannot state it in one sentence, go research
   more.

2. **`## Plain English Summary`** — one short paragraph a
   non-technical reader could understand. No jargon, no internal
   acronyms. The point is to expose unstated assumptions: if you
   can't write it in plain English, the decision needs more thought.

3. **`## Context`** — what triggered this? User message, cron, hook,
   parent task, prior ledger. One paragraph. Reader picks it up cold.

4. **`## Evidence Reviewed`** — concrete artefacts only. File paths
   with line numbers, exact commands, doc URLs with sections, web
   sources with retrieval dates and quotes, prior session ids with
   ledger paths. A `Gaps:` sub-bullet listing what you did NOT
   check feeds straight into Open Risks below.

5. **`## Options Considered`** — at least **two** options. If you
   only have one, you're following an instruction, not making a
   decision. Re-frame as "do the thing" vs "don't do the thing", or
   add a third option named "Defer". Each option fills Pros / Cons /
   Risk / Validation.

6. **`## Selected Model / Worker`** — which Hermes worker, subagent
   profile, or model will execute this. Name it precisely. For
   in-process actions, name the main loop and reasoning level.

7. **`## Why This Choice`** — why the selected model/worker beats the
   alternatives for THIS task. Tie back to the evidence above. This
   section is what makes future drift detectable — when the default
   model changes six months from now, the new operator can read this
   and decide whether the new default still satisfies the same
   criteria.

8. **`## Rejected Alternatives`** — for each option NOT picked, one
   short paragraph on why it lost. Always include the **fallback**
   you'd switch to if the primary choice fails (rate-limited,
   exhausted credentials, error budget). The fallback is what keeps
   the decision recoverable.

9. **`## Cost / Latency / Quality Tradeoff`** — estimated cost (USD
   or token budget), expected latency per turn, and the quality bar
   this choice clears. State the tradeoff explicitly.

10. **`## Validation Plan`** — Commands (runnable from a fresh
    shell), Manual checks (specific human observations), Success
    criteria (binary "did it work?"). A validation plan that cannot
    fail is not a plan.

11. **`## Approval Required`** — start with one of:
    - `no — <reason it's safe to proceed unattended>`
    - `yes — <named approver>`
    - `defer — <what we're waiting on>`

    The Python validator enforces this so tooling can filter for
    "needs approval" without re-parsing free text. Default to `yes`
    when in doubt — explicit consent is cheap; a misfired action
    isn't.

12. **`## Final Decision`** — which option won, by name (Option A /
    Option B / Defer / Neither). This is the verdict after walking
    through the rest of the template; it can diverge from the
    `## Decision` line at the top if Options Considered surfaced
    something better.

13. **`## Confidence`** — start with `low` / `medium` / `high`, then
    one sentence of why. The "why" should reference the evidence and
    validation, not vibes.

14. **`## Open Risks`** — anything the Validation Plan does not
    cover. Each risk gets a one-line mitigation or an honest
    "accepting this risk because…".

15. **`## Rollback Plan`** — exact recovery procedure if the decision
    turns out wrong. `git revert <sha>` plus any side-effect undo
    (cache invalidation, DB rollback, message recall, kanban
    un-claim). "I'll figure it out" is not acceptable.

## Programmatic use

When operating inside a workflow that has a Python runtime, prefer
the helper module over hand-typing ledgers:

```python
from hermes_cli import decision_ledger as dl

# Start from the blank template (with inline guidance comments).
text = dl.render_template()

# ...fill it in via the model loop, then:
ledger = dl.parse_markdown(text)
ledger.validate()                          # raises if anything's empty
path = dl.write_ledger(ledger,
                       session_id="20260523_182600_d4f5a6")
# -> $HERMES_HOME/decisions/20260523_182600_d4f5a6/0001-<slug>.md
```

`render_template()` can accept pre-filled sections via a mapping
keyed by heading name — useful when the orchestrator already knows
the Context and Selected Model / Worker fields before handing the
ledger off to a worker for the rest.

## Interaction with hidden chain-of-thought

If the running model supports reasoning channels (`/reasoning` levels
`low` / `medium` / `high` / `xhigh`), the gate **does not suppress
them**. Hidden reasoning is still allowed for the planning work that
*leads up to* the ledger. The contract is:

> The decision ledger is the externally-binding artefact. Whatever
> reasoning happened to produce it is fine to keep private, but the
> ledger itself must be visible, complete, and honest.

This is the same contract the enterprise Judge enforces: the
orchestrator may think privately, but the structured output it
returns is what gets validated. Reasoning is a means; the ledger is
the means' product.

## Anti-patterns

The gate is easy to subvert by hand-waving. Watch for these in your
own ledgers — the curator's background pass and the Judge's
validation step flag them:

| Anti-pattern | Fix |
|---|---|
| "Considered alternatives" with no alternatives listed | List at least two with Pros/Cons/Risk/Validation each |
| Risk: "low" with no justification | State *why* it's low (blast radius, reversibility, test coverage) |
| Validation: "run the tests" | Name *which* tests; state the success criterion |
| Rollback: "revert" with no specifics | `git revert <sha>` plus any side-effect undo |
| Selected Model: "default model" | Say which model the default *is* at the time of writing |
| Evidence: "based on the codebase" | File paths with line numbers, or admit you did not look |
| Plain English Summary that requires jargon to parse | Rewrite for a smart non-engineer |
| Approval: "maybe" / "ask later" | One of `no` / `yes` / `defer`, with the reason |
| Confidence: "high" with no justification | "high — N test cases pass, baseline reproduced" |
| Two options where one is obviously a strawman | Make Option B a fair fight or add a third |

## Cross-references

- **Schema:** [`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md)
- **Blank template:** [`templates/orchestration/decision-ledger-template.md`](../../templates/orchestration/decision-ledger-template.md)
- **Python helper:** [`hermes_cli/decision_ledger.py`](../../hermes_cli/decision_ledger.py) — render, parse, validate, write, read
- **System overview:** [`docs/orchestration/decision-quality-system.md`](../../docs/orchestration/decision-quality-system.md)
- **Research companion:** [`skills/research-validator/SKILL.md`](../research-validator/SKILL.md) — gather evidence to fill the ledger
- **Enterprise judge:** [`skills/enterprise-council/judge/SKILL.md`](../enterprise-council/judge/SKILL.md) — validates ledgers produced by leaf agents
- **Plan mode:** [`skills/software-development/plan/SKILL.md`](../software-development/plan/SKILL.md) — write-only plan-mode is the right tool when the ledger conclusion is "do not implement yet"
