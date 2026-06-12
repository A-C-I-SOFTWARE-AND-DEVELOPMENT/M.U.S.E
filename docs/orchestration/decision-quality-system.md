# M.U.S.E. Decision Quality System

M.U.S.E. is built to operate with growing autonomy across cron jobs,
webhooks, gateway messages, kanban queues, and the enterprise council.
The more autonomously it runs, the more important it becomes that the
**reasoning** behind each non-trivial action is visible, inspectable,
and challengeable — by the user, by a later session, by a reviewer, or
by a peer agent.

The decision quality system is how M.U.S.E. makes that reasoning visible
without exposing raw chain-of-thought. The core artefact is the
**decision ledger** (a structured markdown record); the supporting
machinery is a small set of skills, gates, and validators that make
the ledger honest, complete, and useful.

This document describes the system as a whole. The detailed building
blocks live in:

- [`decision-ledger.md`](decision-ledger.md) — canonical template and field-by-field guidance
- [`../../skills/decision-quality-gate/SKILL.md`](../../skills/decision-quality-gate/SKILL.md) — when to produce a ledger
- [`../../skills/research-validator/SKILL.md`](../../skills/research-validator/SKILL.md) — how to gather evidence and design validation

---

## Why this exists

Three problems the system addresses.

### 1. Chain-of-thought is not auditable

When an LLM reasons internally and only emits the answer, the answer
is the only thing a reviewer can check. If the answer turns out to be
wrong six months from now, there is no record of *why* the model
believed it was right at the time. The reasoning has evaporated.

For interactive single-turn use, this is fine — the user is right
there to push back. For M.U.S.E.'s autonomous modes (cron, webhooks,
kanban workers, enterprise leaves), nobody is watching at decision
time. The audit happens *after the fact*, and "the model thought
it was right" is not a thing one can audit.

The fix is to externalise the reasoning that matters as a structured
artefact. Hidden reasoning is still allowed; the **binding artefact**
of the decision is the ledger.

### 2. Hand-waving is the failure mode

The naive fix — "have the model explain its reasoning in plain text" —
fails because it produces what looks like reasoning but isn't:
plausible-sounding paragraphs with no concrete citations, no real
alternatives weighed, no falsifiable claims. The system has to make
the cost of producing fake reasoning at least as high as the cost of
producing real reasoning.

The fix is a **template with mandatory sub-fields**:

- "Evidence" forces citations (file paths, commands, doc URLs).
- "Options Considered" with a minimum of two forces a real comparison.
- "Validation Plan" with concrete commands forces a falsifiable check.
- "Rollback" forces the agent to face the irreversibility honestly.

Each sub-field has a "what counts as filling this honestly?" rule. The
gate skill enumerates them; the validator skill enforces them.

### 3. Model and worker selection is itself a decision

M.U.S.E. routinely picks between models (`claude-opus-4-7` vs
`claude-sonnet-4-6` vs `claude-haiku-4-5`), between workers (main
loop vs `delegation` vs spawned subprocess vs kanban dispatch), and
between credential pool entries. These choices have cost, latency,
and quality consequences, and they drift over time as defaults
change. The system treats them as first-class decisions with their
own ledger section.

---

## System components

```
                          ┌────────────────────────┐
                          │   User / cron / hook   │
                          │   triggers an action   │
                          └─────────────┬──────────┘
                                        │
                                        ▼
                   ┌────────────────────────────────────┐
                   │   Decision Quality Gate (skill)    │
                   │  - Should this produce a ledger?   │
                   │  - If yes, walk the template       │
                   └─────────────┬──────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
   ┌────────────────────┐  ┌──────────────┐  ┌──────────────────┐
   │ Research/Validator │  │   Hidden     │  │  Model / Worker  │
   │     (skill)        │  │  reasoning   │  │    selection     │
   │  - Evidence        │  │  (optional;  │  │  (recorded)      │
   │  - Validation plan │  │   ephemeral) │  │                  │
   └─────────┬──────────┘  └──────────────┘  └──────────────────┘
             │
             ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                  Decision Ledger (artefact)                 │
   │  - Persisted to ~/.hermes/decisions/<session>/<seq>.md      │
   │  - Surfaced in chat / kanban comment / gateway footer       │
   └─────────────┬───────────────────────────────────────────────┘
                 │
        ┌────────┴────────────┐
        ▼                     ▼
┌────────────────┐   ┌─────────────────────┐
│   Action       │   │  Judge / Monitor    │
│ (executed)     │   │  (validates ledger  │
│                │   │   & systemic        │
│                │   │   regressions)      │
└────────────────┘   └─────────────────────┘
```

### The gate (`decision-quality-gate`)

A skill that fires before non-trivial actions. Its only outputs are
(a) a yes/no on "should this action produce a ledger?" and (b) when
yes, a completed ledger. It does not itself execute the action — it
gates it.

The gate's triggers are defined explicitly so that a future operator
can tune them: multi-step actions, irreversible/expensive actions,
model/worker selection, cross-session continuation, and explicit
"why?" requests from the user.

### The research-validator (`research-validator`)

A skill that fills the two empirical sections of the ledger:
`Evidence Reviewed` and `Validation Plan`. It defines four evidence
channels (local code, docs, web, prior memory) and three validation
artefacts (automated commands, manual checks, success criteria) and
specifies what "enough" looks like for each.

It also defines the cross-check procedure used when one ledger
challenges another — the same discipline the enterprise Judge applies
to leaf results, but adapted to free-text ledgers.

### The ledger (`docs/orchestration/decision-ledger.md`)

The canonical markdown template. Section headings are a parsing
contract; sub-bullets are free-form. Persisted to
`~/.hermes/decisions/<session_id>/<seq>-<slug>.md` and surfaced in
context-appropriate ways (inline in CLI, footer in gateway,
`kanban_comment` for workers, structured field for enterprise
leaves).

### The validators (existing skills, in supporting roles)

The decision quality system **does not introduce new validator
machinery**; it integrates with what M.U.S.E. already has:

- **Enterprise Judge** (`skills/enterprise-council/judge/SKILL.md`)
  validates structured leaf results and now also expects a
  `decision_ledger` key when leaves are produced for non-trivial
  actions. The Judge applies its existing schema/policy/jury checks
  to that field.
- **Enterprise Monitor** (`skills/enterprise-council/monitor/SKILL.md`)
  scans audit rows post-hoc for systemic regressions, including
  ledger-quality regressions (missing sections, anti-pattern matches,
  validation-plan no-ops).
- **Curator** (`muse curator` / `/curator`) scans persisted ledgers
  during its background pass and flags ones that look like
  rubber-stamps, so the next interactive session can review them.

### The decision store

Ledgers live as plain markdown on disk under
`~/.hermes/decisions/`. This is deliberately the same surface area as
sessions and skills: greppable, diffable, easy to share by attaching
a file path, easy to inspect during incident response.

The persisted-file path is the canonical identity of a ledger.
Surfaced copies (chat replies, kanban comments, gateway footers) are
references to the same artefact.

---

## How the components compose

### Interactive CLI session

1. User issues a non-trivial request.
2. M.U.S.E.'s main loop detects gate triggers (multi-step, etc.) and
   loads `decision-quality-gate` if not already loaded.
3. The gate procedure walks the template top-to-bottom; if any
   section is genuinely thin, the gate either calls
   `research-validator` to gather more evidence, or annotates the
   gap as an open risk.
4. The completed ledger is shown inline in the reply and persisted
   to `~/.hermes/decisions/<session>/<seq>-<slug>.md`.
5. M.U.S.E. proceeds to execute the chosen option.
6. After execution, the Validation Plan commands run. Their outcome
   is appended to the ledger as a `## Validation Result` section
   (added post-hoc; not part of the original template parsing
   contract because not all ledgers reach this stage).

### Cron / webhook / background

Same flow, but the ledger is surfaced in the delivery footer
(Telegram/Discord/Slack/email message) and the executor's stdout
rather than inline. The gateway has a `/footer` toggle that the
user can use to suppress the inline footer if they prefer to read
the persisted file directly.

For pure data-collection cron jobs (`no_agent=True`), the gate does
not fire — there is no agent reasoning to externalise.

### Kanban worker

A worker claiming a task with the `decision-quality-gate` skill in
its profile produces a ledger as soon as the task moves into
"in progress". The ledger is attached as a `kanban_comment` *and*
persisted to disk. If the worker hits a sub-decision mid-task
(picking between two implementation paths), it produces an
additional ledger with an incremented `<seq>`.

### Enterprise council leaf

A leaf agent dispatched by the orchestrator returns the standard
structured leaf result *plus* a `decision_ledger` key (markdown
string, conforms to the parsing contract). The Judge's schema check
treats `decision_ledger` as a required key for any leaf action
classified MEDIUM or HIGH risk. Trivial LOW-risk reads remain
ledger-free.

### Enterprise council orchestrator

The orchestrator produces one ledger per **plan-of-record**: the
decomposition itself is a decision. Subsequent leaf ledgers are
treated as child artefacts of that plan ledger. The orchestrator's
`PROGRESS:` / `DONE:` one-liners reference the relevant ledger ids.

---

## What hidden chain-of-thought is still allowed to do

The system does not ban internal reasoning. Models that support
reasoning channels (Claude reasoning modes, `/reasoning xhigh`,
etc.) are still allowed to think privately while *producing* the
ledger. The ledger is the binding artefact; the path the model took
to draft it is not.

The contract is:

> **Hidden reasoning is a means. The ledger is the means' product. The
> ledger is what gets audited; the reasoning is allowed to be
> ephemeral.**

This is the same contract the enterprise Judge enforces on leaf
agents: leaves may reason however they like internally; the
structured output is what gets validated.

Two practical consequences:

1. Asking a model to "show its reasoning" inline alongside the
   ledger usually makes the ledger *worse* — the model splits effort
   between two artefacts. Prefer to let reasoning be private and
   put all the externalised work into the ledger.
2. Reasoning-level config (`/reasoning medium` etc.) is orthogonal
   to ledger production. A `low` reasoning level still produces a
   complete ledger; an `xhigh` reasoning level does too, but with
   more thorough sub-bullets.

---

## What the system does *not* do

It is worth being explicit about the non-goals so that future
contributors don't add weight the system doesn't need.

- **It is not a code review.** Ledgers explain decisions; PR review
  validates code. `/skill code-review` is a separate concern.
- **It is not a planning system.** `/skill plan` and
  `/skill writing-plans` produce *what to do*; the ledger records
  *why this is the right thing*. A plan can cite a ledger as its
  justification; a ledger is not itself a plan.
- **It is not a memory system.** The `memory` toolset persists
  facts; the ledger persists the reasoning behind a single decision
  at a single moment. Memory may *use* ledgers as source material,
  but it is not the same store.
- **It does not eliminate hidden chain-of-thought.** It only ensures
  that the externally-binding artefact of a decision is visible. The
  reasoning that produced the artefact is allowed to remain private.
- **It does not gate everything.** Trivial actions (single-line
  answers, read-only commands explicitly requested, in-loop
  bookkeeping) bypass the gate. The cost of producing a ledger has
  to be less than the cost of being wrong.

---

## Lifecycle of a single ledger

```
draft → execute → validate → archive
  │         │         │         │
  │         │         │         └─ persisted as-is; curator may
  │         │         │            flag for review if it matches
  │         │         │            anti-pattern signatures
  │         │         │
  │         │         └─ Validation Plan commands run; outcome
  │         │            appended as `## Validation Result`
  │         │
  │         └─ chosen option is executed; ledger remains the
  │            authoritative record of why this option was chosen
  │
  └─ template walked, sections filled, persisted to
     ~/.hermes/decisions/<session>/<seq>-<slug>.md
```

Ledgers are **never deleted** by automated processes. The curator's
most destructive action on a ledger is to flag it for review. Manual
deletion is fine — they're just markdown files — but the system
treats the persisted ledger as the audit trail.

---

## Open work

The system as described above is the **minimum viable shape**.
Reasonable extensions, each of which can be added without changing
the parsing contract:

- **`muse decisions` CLI** — `list`, `show`, `grep`, `tail`.
  Mirrors `muse sessions`.
- **`/decisions` slash command** — interactive picker for ledgers
  in the current session and cross-session search.
- **Web dashboard view** — read-only browser view, served by the
  existing `web/` dashboard, listing ledgers with filters
  (confidence, risk, validation status).
- **Ledger templates per domain** — finance / hr / customer-service
  domains under the enterprise council might want sub-fields the
  generic template lacks (e.g. counterparty, amount, regulatory
  basis). These extensions append; they do not replace the base
  sections.
- **Cross-ledger graph** — when ledger B cites ledger A in its
  `Context` or `Evidence Reviewed`, the system could surface the
  link explicitly for navigation.

None of these are required for the system to be useful — the bare
ledger + the two skills + the existing validators (Judge, Monitor,
curator) are sufficient.

---

## Anti-patterns the system is designed to prevent

| Anti-pattern | How the system blocks it |
|---|---|
| Agent acts on a high-stakes irreversible action with no visible reasoning | Gate's "irreversible or expensive" trigger forces a ledger |
| "Considered alternatives" with no alternatives listed | Template's minimum-two-options requirement; Judge anti-pattern check |
| Validation: "looks good" with no falsifiable check | Validation Plan's mandatory `Commands` and `Success criteria` sub-fields |
| Model/worker drift over time with no record of original rationale | Mandatory `Selected Model / Worker` and `Why This Choice` sections even for "obvious" picks |
| Re-doing the same research from scratch every session | Evidence Reviewed's prior-memory channel; persisted ledgers as a searchable store |
| Rollback hand-wave ("I'll figure it out") | Dedicated `Rollback Plan` section with a concrete procedure |
| Cost drift undiscovered until the bill arrives | Dedicated `Cost / Latency / Quality Tradeoff` section that future operators can diff against |
| Unauthorised pushes / sends / payments | Dedicated `Approval Required` section with `yes` / `no` / `defer` verdict tokens |
| Hand-waving evidence ("based on the codebase") | Evidence Reviewed sub-field types: file paths with line ranges, verbatim commands, doc URLs with sections |
| Hidden chain-of-thought as the only artefact | Gate procedure produces the ledger as the binding artefact; reasoning is allowed to be ephemeral, but the ledger is not |

---

## Cross-references

- [`decision-ledger.md`](decision-ledger.md) — the template
- [`../../skills/decision-quality-gate/SKILL.md`](../../skills/decision-quality-gate/SKILL.md) — when and how to produce a ledger
- [`../../skills/research-validator/SKILL.md`](../../skills/research-validator/SKILL.md) — evidence and validation discipline
- [`../../skills/enterprise-council/orchestrator/SKILL.md`](../../skills/enterprise-council/orchestrator/SKILL.md) — orchestrator integration
- [`../../skills/enterprise-council/judge/SKILL.md`](../../skills/enterprise-council/judge/SKILL.md) — Judge validates ledgers in structured leaf results
- [`../../skills/enterprise-council/monitor/SKILL.md`](../../skills/enterprise-council/monitor/SKILL.md) — Monitor flags systemic ledger-quality regressions
- [`../../skills/autonomous-ai-agents/hermes-agent/SKILL.md`](../../skills/autonomous-ai-agents/hermes-agent/SKILL.md) — M.U.S.E. overall surface area (cron, kanban, gateway, delegation)
- [`../muse-local-orchestrator.md`](../muse-local-orchestrator.md) — Android local orchestrator (consumer of ledgers when manual handoff feeds back into a session)
