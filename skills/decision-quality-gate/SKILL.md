---
name: decision-quality-gate
description: "Force Hermes to produce a visible decision ledger before non-trivial actions — evidence, options, model/worker choice, validation plan, risk, rollback. Replaces hidden chain-of-thought with auditable reasoning."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows, android]
metadata:
  hermes:
    tags: [decision, gate, quality, validation, audit, orchestration, governance, private-local]
    related_skills:
      - hermes-orchestration-pipeline
      - aos-full-agent-team
      - model-router
      - research-validator
      - ai-improvement-radar
      - self-improvement-loop
      - github-publisher
      - best-coding-tool-mission
      - enterprise-orchestrator
      - enterprise-judge
      - plan
      - writing-plans
      - spike
    related_docs:
      - docs/orchestration/decision-ledger.md
      - docs/orchestration/decision-quality-system.md
      - docs/orchestration/hermes-orchestration-pipeline.md
      - docs/orchestration/self-improvement-loop.md
      - docs/ai-intelligence/model-registry.yaml
      - docs/mission/best-coding-tool-mission.md
    homepage: https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent
---

# Decision Quality Gate

This is the gate Hermes passes through before any non-trivial decision.
Instead of an invisible chain-of-thought, Hermes produces a **visible
decision ledger** — a structured markdown record that the user (or a
later session, or a reviewer, or the Judge) can read, audit, and
challenge.

The principle is simple: hidden reasoning is not auditable, and an
agent that cannot be audited cannot be trusted with autonomy. The gate
externalises the reasoning that actually matters — what evidence was
considered, which options were on the table, which worker/model was
chosen and why, how the result will be validated, and what the
rollback plan is if things go wrong.

## When to invoke this skill

Load this skill (`/skill decision-quality-gate`) — or have the
orchestrator load it automatically — for any task that is:

1. **Multi-step or multi-file.** Anything that touches more than one
   file, more than one subsystem, or more than one external service.
2. **Irreversible or expensive.** Anything that mutates production
   state, costs money, writes to shared storage, sends external
   messages, or pushes to a remote.
3. **Model/worker selection.** Anything where Hermes is picking which
   subagent, profile, or model to delegate to. The selection itself is
   a decision and deserves a ledger entry.
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

A useful heuristic: **if you would have produced hidden chain-of-thought
to plan this action, produce a ledger instead.** If you would have just
acted, no ledger needed.

## What the gate produces

Exactly one artefact: a **decision ledger** following the template in
[`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md).

The ledger lives in one of three places depending on context:

| Context | Ledger location |
|---|---|
| Interactive CLI session | Inline in chat reply, also persisted to `~/.hermes/decisions/<session_id>/<seq>-<slug>.md` |
| Cron / webhook / background | `~/.hermes/decisions/<session_id>/<seq>-<slug>.md` and surfaced in the delivery footer |
| Kanban worker | Attached as a `kanban_comment` on the task plus the persisted file |
| Enterprise council leaf | Returned as the `decision_ledger` key in the structured result the Judge inspects |

The persisted copy is plain markdown so it shows up in `grep`, in PR
diffs, and in the curator's review pass. Do not encrypt or compress
ledgers — they are deliberately visible.

## Gate procedure

When the gate fires, Hermes works through the template top-to-bottom.
You do not have to fill every section to the same depth — match the
depth to the stakes — but every section must be present and
non-empty. An empty section means the gate has not actually been
passed.

### 1. Decision

A single sentence. "We will change X from A to B." If you cannot state
the decision in one sentence, the decision is not yet ready and the
ledger is premature — go research more.

### 2. Context

What triggered this? Cite the user message, the cron schedule, the
webhook payload, or the upstream task. One paragraph max. The reader
should be able to pick this up cold without scrolling.

### 3. Evidence Reviewed

Concrete artefacts only. List file paths with line numbers, exact
commands run, doc URLs, web sources, and any prior Hermes
memory/session notes consulted. **No hand-waving.** "I considered the
codebase" is not evidence; `agent/prompt_builder.py:142-180` is.

If the available evidence is thin, say so explicitly:

```markdown
## Evidence Reviewed
- Files: (none reviewed — net-new module)
- Commands: `grep -r "TODO" agent/` (0 matches)
- Docs: https://hermes-agent.nousresearch.com/docs/user-guide/profiles
- Prior memory: none — fresh session
- Gaps: have not yet read the Android counterpart; risk noted below
```

### 4. Options Considered

At least **two** options. If you only have one option, you are not
making a decision — you are following an instruction, and the gate is
the wrong tool. Re-frame as "do the thing" vs "don't do the thing" if
the comparison is genuinely binary.

For each option, fill all four sub-fields:

- **Pros** — what the option buys you
- **Cons** — what it costs
- **Risk** — what could go wrong, and the likely blast radius
- **Validation** — how you'd prove the option worked if you picked it

Do not stack the deck by giving Option B a one-line dismissal. If you
already know which option you're picking, the gate isn't earning its
keep — it's rubber-stamping. Make the second option a fair fight or
add a third.

### 5. Model / Worker Choice

Which Hermes worker, subagent profile, or model will execute this?
Why? What's the fallback if the first choice fails? What is the
cost/latency/quality tradeoff?

This section is mandatory even for "obvious" choices — the
externalised record of *why* the obvious choice was obvious is what
makes future drift detectable. Example:

```markdown
## Model / Worker Choice
Selected worker/model: `delegation` toolset → `anthropic/claude-sonnet-4`
Why: tool-heavy multi-file refactor; sonnet handles long-context
  patch-style edits better than haiku, cheaper than opus.
Fallback: `openai/gpt-5-mini` via OpenRouter if Anthropic key
  exhausted in the credential pool.
Cost/latency/quality tradeoff: ~$0.40 estimated; sub-30s per turn;
  quality acceptable for non-prod code path.
```

### 6. Validation Plan

How will you know the decision was correct *after* you act on it?
Three sub-fields:

- **Commands** — concrete commands that prove success or failure
  (`pytest tests/foo/`, `mypy module/`, `curl http://localhost:8080/health`)
- **Manual checks** — what a human would observe (screenshot the UI,
  read the diff, verify a notification arrives)
- **Success criteria** — the binary "did it work?" definition

"It compiles" is rarely a sufficient success criterion. "It compiles,
the new test passes, and the existing 12 tests in `tests/agent/`
still pass" is.

### 7. Final Decision

The verdict. Four sub-fields:

- **Decision** — which option won (Option A, Option B, neither, defer)
- **Confidence** — `low` / `medium` / `high`, with one sentence of why
- **Open risks** — anything the validation plan does not cover
- **Rollback** — the exact recovery procedure if the decision turns
  out wrong. "Revert the commit" is acceptable; "I'll figure it out"
  is not.

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
own ledgers:

| Anti-pattern | Fix |
|---|---|
| "Considered alternatives" with no alternatives listed | List at least two with pros/cons each |
| Risk: "low" with no justification | State *why* it's low (blast radius, reversibility, test coverage) |
| Validation: "run the tests" | Name *which* tests; state the success criterion |
| Rollback: "revert" with no specifics | `git revert <sha>` plus any side-effect undo (cache invalidation, DB rollback, message recall) |
| Model choice: "default model" | Say which model the default *is* at the time of writing |
| Evidence: "based on the codebase" | File paths with line numbers, or admit you did not look |

The Judge skill checks for these anti-patterns when present. The
curator's background pass also flags ledgers that match the
anti-pattern signatures.

## Where this fits in the larger system

The gate is the **visible reasoning layer** of the orchestration
stack. It does not pick workers, run research, ship code, or learn —
it forces every other layer's reasoning into a ledger row a human can
audit:

| Concern | Skill / doc |
|---|---|
| The job folder the ledger lives in | [`hermes-orchestration-pipeline`](../hermes-orchestration-pipeline/SKILL.md) — every job has its own `decision-ledger.md` |
| Worker / model selection ledger row | [`model-router`](../model-router/SKILL.md) records the routing decision through this gate |
| Evidence to fill the ledger honestly | [`research-validator`](../research-validator/SKILL.md) |
| Tracking new AI tool capabilities so ledgers cite fresh options | [`ai-improvement-radar`](../ai-improvement-radar/SKILL.md) |
| Closing the loop on ledger outcomes | [`self-improvement-loop`](../self-improvement-loop/SKILL.md) — mines ledgers for `routing_miss`, `prompt_regression`, `mission_drift` |
| Council orchestration that produces ledgers per dispatched task | [`aos-full-agent-team`](../aos-full-agent-team/SKILL.md) |
| Publishing a ledger-backed decision | [`github-publisher`](../github-publisher/SKILL.md) — refuses to publish without a pass/conditional ledger |
| Mission anchor (Principle 3: visible evidence) | [`best-coding-tool-mission`](../best-coding-tool-mission/SKILL.md) |

## Posture: private and local-first

- Ledgers are plain markdown on the user's disk
  (`~/.hermes/decisions/...` and inside the job folder). They are
  never uploaded.
- The gate does not call any external API on its own. It produces
  the ledger; downstream skills consume it.
- The Android APK cockpit reads ledgers from the same on-disk
  contract — there is no cockpit-side mirror.

## How to invoke

```text
/reload-skills                              # after editing skills
/decision-quality-gate                      # load this skill into a session
/decision-quality-gate <decision-id>        # gate a specific decision
/research-validator                         # gather evidence before filling a ledger
/model-router <task-type>                   # routing decision → ledger row
/self-improvement-loop                      # mine ledgers at end of job
```

## Cross-references

- **Template:** [`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md)
- **System overview:** [`docs/orchestration/decision-quality-system.md`](../../docs/orchestration/decision-quality-system.md)
- **Research companion:** [`skills/research-validator/SKILL.md`](../research-validator/SKILL.md) — gather evidence to fill the ledger
- **AI improvement radar:** [`skills/ai-improvement-radar/SKILL.md`](../ai-improvement-radar/SKILL.md) — keeps the model/worker options cited in ledgers fresh
- **Self-improvement loop:** [`skills/self-improvement-loop/SKILL.md`](../self-improvement-loop/SKILL.md) — mines ledger outcomes for proposals
- **Enterprise judge:** [`skills/enterprise-council/judge/SKILL.md`](../enterprise-council/judge/SKILL.md) — validates ledgers produced by leaf agents
- **Plan mode:** [`skills/software-development/plan/SKILL.md`](../software-development/plan/SKILL.md) — write-only plan-mode is the right tool when the ledger conclusion is "do not implement yet"
- **Mission:** [`docs/mission/best-coding-tool-mission.md`](../../docs/mission/best-coding-tool-mission.md) — Principle 3 (visible evidence) is the reason this gate exists
