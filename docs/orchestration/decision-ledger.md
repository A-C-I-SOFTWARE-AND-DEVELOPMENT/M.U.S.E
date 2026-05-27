# Decision Ledger

The decision ledger is Hermes's externally-visible record of a single
non-trivial decision. It replaces hidden chain-of-thought with a
structured artefact that a human reviewer, a later session, or the
enterprise Judge can audit.

This file is the **canonical schema**. Skills, plugins, and agents
that produce ledgers must follow this shape exactly — section
headings, ordering, and field names. Tooling (the Judge, the curator,
the `/decisions` slash command, the Python module
[`hermes_cli/decision_ledger.py`](../../hermes_cli/decision_ledger.py))
parses against these headings.

When and how to produce a ledger is documented in
[`skills/decision-quality-gate/SKILL.md`](../../skills/decision-quality-gate/SKILL.md).
How to gather and check the evidence that fills it is documented in
[`skills/research-validator/SKILL.md`](../../skills/research-validator/SKILL.md).
The overall system is described in
[`decision-quality-system.md`](decision-quality-system.md).

A ready-to-fill blank lives at
[`templates/orchestration/decision-ledger-template.md`](../../templates/orchestration/decision-ledger-template.md);
the Python module exposes the same template via
`hermes_cli.decision_ledger.render_template()`.

---

## The fifteen sections

Every ledger has exactly these fifteen H2 headings, in this order:

1. `## Decision`
2. `## Plain English Summary`
3. `## Context`
4. `## Evidence Reviewed`
5. `## Options Considered`
6. `## Selected Model / Worker`
7. `## Why This Choice`
8. `## Rejected Alternatives`
9. `## Cost / Latency / Quality Tradeoff`
10. `## Validation Plan`
11. `## Approval Required`
12. `## Final Decision`
13. `## Confidence`
14. `## Open Risks`
15. `## Rollback Plan`

The document title is always `# Decision Ledger` (an extra subtitle
after a dash is fine: `# Switch Delegation Model — Decision Ledger`).

**An empty section means the ledger is not done.** "N/A" is acceptable
only with a one-sentence justification of why the section does not
apply to this decision.

---

## Template

Copy from the fenced block below — or run
`hermes_cli.decision_ledger.render_template()` — fill every section,
and commit (or post, or persist) the result.

````markdown
# Decision Ledger

## Decision
<!-- One sentence, active voice. -->

## Plain English Summary
<!-- One short paragraph a non-technical reader could understand. -->

## Context
<!-- What triggered this? Cite the upstream artefact. -->

## Evidence Reviewed
- Files:
- Commands:
- Docs:
- Web sources, if available:
- Prior Hermes memory / session notes, if available:
- Gaps:

## Options Considered

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

## Selected Model / Worker
<!-- Which Hermes worker, subagent profile, or model. -->

## Why This Choice
<!-- Why selected beats the alternatives for THIS task. -->

## Rejected Alternatives
<!-- Each non-picked option + one-line "why it lost" + fallback. -->

## Cost / Latency / Quality Tradeoff
<!-- Estimated cost, expected latency, quality bar. -->

## Validation Plan
- Commands:
- Manual checks:
- Success criteria:

## Approval Required
<!-- "no — <reason>", "yes — <approver>", or "defer — <waiting on>". -->

## Final Decision
<!-- Which option won, by name. -->

## Confidence
<!-- low / medium / high — plus one sentence of why. -->

## Open Risks
<!-- Anything Validation Plan does not cover. -->

## Rollback Plan
<!-- Exact recovery procedure if the decision turns out wrong. -->
````

---

## Field-by-field guidance

### `## Decision`

One sentence. Active voice. State the change, not the deliberation.

OK: "Switch the orchestrator default delegation model from
`claude-haiku-4-5` to `claude-sonnet-4-6` for multi-file refactors."

Not OK: "Consider whether we should change the delegation model."

If you cannot write a one-sentence decision, the ledger is premature —
go back to research.

### `## Plain English Summary`

One short paragraph a non-technical reader could understand. Say what
is changing and why anyone should care. No jargon, no internal
acronyms, no model names without a parenthetical gloss. The point is
that someone outside the immediate context can read the rest of the
ledger and know whether they should keep reading.

This section is the one most likely to expose unstated assumptions: if
you find yourself unable to explain the change in plain English, the
decision itself probably needs more thought.

### `## Context`

One paragraph. What triggered the decision? Cite the upstream
artefact: a user message, a cron schedule, a webhook, a parent task,
a previously-deferred ledger.

The reader should be able to pick up the ledger cold without scrolling
through prior conversation.

### `## Evidence Reviewed`

Concrete artefacts only. Six sub-bullets:

| Sub-bullet | What goes here | Acceptable "none" |
|---|---|---|
| Files | Paths with line ranges: `agent/prompt_builder.py:142-180` | "(none — net-new module)" |
| Commands | Verbatim commands plus a one-line result summary | "(none — read-only research)" |
| Docs | Path or URL plus the section/heading you used | "(none consulted)" |
| Web sources | URL + retrieval date + a relevant quote | "(none — answer was local)" |
| Prior Hermes memory / session notes | Session id + ledger path, or "(none found)" | "(none found)" |
| Gaps | What you did not check (feeds Open Risks) | "(none — coverage complete)" |

Hand-waving is the failure mode here. "I considered the codebase" is
not evidence. `grep -rn "DecisionLedger" agent/` returning a file
path is.

### `## Options Considered`

Minimum two options. Each option fills all four sub-fields:

- **Pros** — what the option buys you, beyond restating the decision.
- **Cons** — what it costs. Time, money, complexity, blast radius,
  reversibility.
- **Risk** — what could go wrong, and the likely consequence. Be
  specific: "if X fails, Y breaks for users on Z" beats "could break".
- **Validation** — how you'd prove this option worked *if you chose
  it*. This is the option-specific draft of the global Validation
  Plan; the global plan may pick parts from each option.

If you only have one option, you are not making a decision — you are
following an instruction. Re-frame as the binary "do the thing" vs
"do not do the thing" so the costs of action are visible against the
costs of inaction.

A third option named "**Defer**" (with concrete trigger conditions for
when to reopen the question) is always available and often correct.

### `## Selected Model / Worker`

Which Hermes worker, subagent profile, or model will execute this?
Name it precisely:

```
delegation toolset -> anthropic/claude-sonnet-4-6
```

For tasks that don't delegate (single-process work), record the
*model* that produced the ledger itself: "Hermes main loop, model
`claude-opus-4-7`, reasoning level `medium`".

### `## Why This Choice`

Why the selected model/worker beats the alternatives for THIS task.
Tie the answer back to the evidence above. This section exists so
that *future* drift becomes detectable — when the default model
changes six months from now, the new operator can read this and
decide whether the new default still satisfies the same criteria.

Mandatory even when the choice is "obvious".

### `## Rejected Alternatives`

For each option NOT picked, one short paragraph on why it lost.
Always include the **fallback** you'd switch to if the primary choice
fails (rate-limited, exhausted credentials, error budget, etc.). The
fallback is what keeps the decision recoverable.

Example:

```markdown
- Opus: too expensive for this cron path; reserved for council leaves.
- Haiku: insufficient context window for the 12-file refactor.
- Fallback if sonnet exhausted: openai/gpt-5-mini via OpenRouter.
```

### `## Cost / Latency / Quality Tradeoff`

Estimated cost (USD or token budget), expected latency per turn, and
the quality bar this choice clears. State the tradeoff explicitly —
this is the section future operators will use to detect price drift
or quality regression.

```markdown
~$0.40/turn; sub-30s/turn latency; acceptable for non-prod code path.
Quality bar: passes the 12-file refactor benchmark within 5% of Opus.
```

### `## Validation Plan`

The post-action check. Three sub-bullets:

- **Commands** — runnable from a fresh shell, with any setup inlined.
  `pytest tests/agent/test_prompt_builder.py -q`, not "run the tests".
- **Manual checks** — specific observations a human can make.
  "Open the dashboard, confirm the new entry appears at the top",
  not "looks right".
- **Success criteria** — the binary acceptance test. "All listed
  commands pass, all listed manual checks confirm, runtime within
  10% of baseline."

Tighter is better. A validation plan that cannot fail is not a plan.

### `## Approval Required`

Does this decision need explicit human approval before execution?
Start the field with one of these verdict tokens — the Python
validator enforces this so tooling can filter for "needs approval"
without re-parsing free text:

| Token | When to use |
|---|---|
| `no` | Reversible, low blast radius, or already authorised by a durable user instruction. State *why* it's safe to proceed unattended. |
| `yes` | Pushes to a remote, sends external messages, costs money beyond the configured budget, or touches shared infrastructure. Name the approver. |
| `defer` | Cannot proceed without information you don't have. State what you're waiting on. |

Examples:

```markdown
no — flag is additive and defaults to off; CLI-only change.
yes — must reach Jeremiah before pushing the cron schedule edit.
defer — waiting on user to confirm the budget tier in their next reply.
```

### `## Final Decision`

Which option won, by name. "Option A", "Option B", "Defer", or
"Neither — re-research". One line. This separates from `## Decision`
because the top-line `## Decision` is the *proposed* change at the
top of the document; `## Final Decision` is the *verdict* after
walking through the rest of the template — they can diverge if
Options Considered surfaced something better than the initial
proposal.

### `## Confidence`

Start with one of `low`, `medium`, `high` (the Python validator
checks this), then one sentence of why. The "why" should reference
the evidence and validation, not vibes.

```markdown
medium — benchmark covers 90% of expected refactor shapes; the long
tail is not exercised.
```

### `## Open Risks`

Anything the Validation Plan does not cover. Each risk gets either a
one-line mitigation or an honest "accepting this risk because…".

```markdown
- Windows runner not yet exercised; mitigation: CI matrix run before
  release.
- Long-context edits beyond 100k tokens not benchmarked; accepting
  because we have no production trace of those today.
```

### `## Rollback Plan`

Exact recovery procedure if the decision turns out wrong:

```markdown
`git revert <sha>`. No state, no migrations; the flag is purely
additive and defaults to off. Telegram gateway picks up the revert on
its next config reload (≤60s).
```

A `Rollback: I'll figure it out` is not acceptable. If you cannot
state the rollback, you are not yet ready to decide — or the decision
is genuinely irreversible and the ledger should say so loudly with a
HIGH-risk flag in `## Open Risks` and an explicit "no rollback;
mitigations only" line here.

---

## File naming and storage

Persisted ledgers live under:

```
$HERMES_HOME/decisions/<session_id>/<seq>-<slug>.md
```

Where:

- `<session_id>` is the session that produced the ledger (e.g.
  `20260523_182600_d4f5a6`).
- `<seq>` is a four-digit zero-padded sequence number within the
  session (`0001`, `0002`, …).
- `<slug>` is a short kebab-case description (`add-ledger-flag`,
  `pick-delegation-model`).

For profile-scoped runs, replace `$HERMES_HOME` with the active
profile root (`~/.hermes/profiles/<name>/`).

The Python helpers in
[`hermes_cli/decision_ledger.py`](../../hermes_cli/decision_ledger.py)
handle the layout for you:

```python
from hermes_cli import decision_ledger as dl

ledger = dl.parse_markdown(my_filled_text)
path = dl.write_ledger(ledger, session_id="20260523_182600_d4f5a6")
# -> $HERMES_HOME/decisions/20260523_182600_d4f5a6/0001-switch-delegation-model.md
```

Kanban-worker ledgers additionally surface as a `kanban_comment` on
the task they belong to, so the next worker claiming a related task
sees the prior reasoning without having to dig.

---

## Parsing contract

External tooling — the enterprise Judge, the curator, the
`/decisions` slash command (not yet built; see
[`decision-quality-system.md`](decision-quality-system.md)) — parses
ledgers by heading. Do not rename, reorder, or skip these headings.

The canonical, machine-parseable heading set is defined by
`hermes_cli.decision_ledger.SECTION_HEADINGS`. Any consumer that
parses ledgers by string-matching headings MUST import that constant
rather than re-typing the names.

Sub-bullets inside each section are free-form. Tooling reads them as
opaque markdown; only the H1 title (`# Decision Ledger`) and the
fifteen H2 section boundaries are structurally parsed. Inside
`## Options Considered`, the `### Option A` / `### Option B` H3
headings are conventional but not currently parsed by tooling — keep
them so humans can scan, but do not rely on them as a structural
boundary.

---

## Field-level validators

[`hermes_cli/decision_ledger.py`](../../hermes_cli/decision_ledger.py)
enforces three machine-checkable rules on top of "every section is
non-empty":

| Field | Rule |
|---|---|
| Confidence | First word (after lowercasing) must be `low`, `medium`, or `high`. |
| Approval Required | First word must be `yes`, `no`, or `defer`. |
| Any section | A body of bare `N/A`, `NA`, or `none` (no justification) counts as empty. |

These rules are the bare minimum the Judge and curator need to
operate on ledgers as data rather than as prose. Hermes can layer
richer checks (LLM-based "does this answer the question?") on top,
but the three above are non-negotiable for tooling.

---

## Cross-references

- [`decision-quality-system.md`](decision-quality-system.md) — system architecture
- [`../../skills/decision-quality-gate/SKILL.md`](../../skills/decision-quality-gate/SKILL.md) — when and why to produce a ledger
- [`../../skills/research-validator/SKILL.md`](../../skills/research-validator/SKILL.md) — how to fill `Evidence Reviewed` and `Validation Plan` honestly
- [`../../skills/enterprise-council/judge/SKILL.md`](../../skills/enterprise-council/judge/SKILL.md) — the validator that consumes structured leaf ledgers
- [`../../skills/enterprise-council/orchestrator/SKILL.md`](../../skills/enterprise-council/orchestrator/SKILL.md) — the orchestrator that emits ledgers per dispatched task
- [`../../templates/orchestration/decision-ledger-template.md`](../../templates/orchestration/decision-ledger-template.md) — ready-to-fill blank
- [`../../hermes_cli/decision_ledger.py`](../../hermes_cli/decision_ledger.py) — Python module: dataclass, render, parse, validate, write, read
