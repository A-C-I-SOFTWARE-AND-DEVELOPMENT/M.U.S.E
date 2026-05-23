# Decision Ledger

The decision ledger is Hermes's externally-visible record of a single
non-trivial decision. It replaces hidden chain-of-thought with a
structured artefact that a human reviewer, a later session, or the
enterprise Judge can audit.

This file is the **canonical template**. Skills, plugins, and agents
that produce ledgers must follow this shape exactly — section
headings, ordering, and field names. Tooling (the Judge, the curator,
ledger search) parses against these headings.

When and how to produce a ledger is documented in
[`skills/decision-quality-gate/SKILL.md`](../../skills/decision-quality-gate/SKILL.md).
How to gather and check the evidence that fills it is documented in
[`skills/research-validator/SKILL.md`](../../skills/research-validator/SKILL.md).
The overall system is described in
[`decision-quality-system.md`](decision-quality-system.md).

---

## Template

Copy from the fenced block below, fill every section, and commit (or
post, or persist) the result. **An empty section means the ledger is
not done.** "N/A" is acceptable only with a one-sentence justification
of why the section does not apply to this decision.

````markdown
# Decision Ledger

## Decision
What is being decided?

## Context
What task, repo, user goal, or constraint triggered this?

## Evidence Reviewed
- Files:
- Commands:
- Docs:
- Web sources, if available:
- Prior Hermes memory/session notes, if available:

## Options Considered

### Option A
Pros:
Cons:
Risk:
Validation:

### Option B
Pros:
Cons:
Risk:
Validation:

## Model / Worker Choice
Selected worker/model:
Why:
Fallback:
Cost/latency/quality tradeoff:

## Validation Plan
Commands:
Manual checks:
Success criteria:

## Final Decision
Decision:
Confidence:
Open risks:
Rollback:
````

---

## Field-by-field guidance

### `## Decision`

One sentence. Active voice. State the change, not the deliberation.

✅ "Switch the orchestrator default delegation model from
`claude-haiku-4-5` to `claude-sonnet-4-6` for multi-file refactors."

❌ "Consider whether we should change the delegation model."

If you cannot write a one-sentence decision, the ledger is premature —
go back to research.

### `## Context`

One paragraph. What triggered the decision? Cite the upstream
artefact: a user message, a cron schedule, a webhook, a parent task,
a previously-deferred ledger.

The reader should be able to pick up the ledger cold without scrolling
through prior conversation.

### `## Evidence Reviewed`

Concrete artefacts only. Five sub-fields:

| Sub-field | What goes here | Acceptable "none" |
|---|---|---|
| Files | Paths with line ranges: `agent/prompt_builder.py:142-180` | "(none — net-new module)" |
| Commands | Verbatim commands plus a one-line result summary | "(none — read-only research)" |
| Docs | Path or URL plus the section/heading you used | "(none consulted)" |
| Web sources | URL + retrieval date + a relevant quote | "(none — answer was local)" |
| Prior Hermes memory/session notes | Session id + ledger path, or "(none found)" | "(none found)" |

Hand-waving is the failure mode here. "I considered the codebase" is
not evidence. `grep -rn "DecisionLedger" agent/` returning a file
path is.

If your evidence is genuinely thin, **say so** and add a `Gaps:`
sub-bullet describing what you did not check. That goes straight into
`Open risks` later.

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

A third option named "**defer**" (with concrete trigger conditions
for when to reopen the question) is always available and often
correct.

### `## Model / Worker Choice`

Four sub-fields:

| Sub-field | Example |
|---|---|
| Selected worker/model | `delegation` toolset → `anthropic/claude-sonnet-4-6` |
| Why | tool-heavy multi-file work; long-context patch edits; not worth opus cost |
| Fallback | `openai/gpt-5-mini` via OpenRouter if Anthropic exhausted |
| Cost/latency/quality tradeoff | ~$0.40; sub-30s/turn; acceptable for non-prod path |

Mandatory even when the choice is "obvious" — the externalised
record of *why* the obvious choice was obvious is what makes future
drift detectable. (When the default model changes six months from
now, the new operator can see why the old default was picked and
decide whether the new default still satisfies the same criteria.)

For tasks that don't delegate (single-process work), this section
records the *model* that produced the ledger itself: "Hermes main
loop, model `claude-opus-4-7`, reasoning level `medium`."

### `## Validation Plan`

The post-action check. Three sub-fields:

- **Commands** — runnable from a fresh shell, with any setup
  inlined. `pytest tests/agent/test_prompt_builder.py -q`, not
  "run the tests".
- **Manual checks** — specific observations a human can make.
  "Open the dashboard, confirm the new entry appears at the top",
  not "looks right".
- **Success criteria** — the binary acceptance test. "All listed
  commands pass, all listed manual checks confirm, runtime within
  10% of baseline."

Tighter is better. A validation plan that cannot fail is not a plan.

### `## Final Decision`

Four sub-fields:

| Sub-field | Notes |
|---|---|
| Decision | Which option won, by name. "Option A", "Option B", "Defer", or "Neither — re-research". |
| Confidence | `low` / `medium` / `high`, plus one sentence of why. |
| Open risks | Anything the Validation Plan does not cover. Each risk gets a one-line mitigation or an honest "accepting this risk because…". |
| Rollback | Exact recovery procedure if the decision turns out wrong. `git revert <sha>`, plus any side-effect undo (cache invalidation, DB rollback, message recall, kanban un-claim). |

A `Rollback: I'll figure it out` is not acceptable. If you cannot
state the rollback, you are not yet ready to decide — or the decision
is genuinely irreversible and the ledger should say so loudly with a
HIGH-risk flag and an explicit "no rollback; mitigations only" line.

---

## Worked example

The following is a complete ledger for a realistic Hermes decision.
Use it as a depth reference — not every ledger needs to be this
detailed, but every ledger needs at least this much *structure*.

````markdown
# Decision Ledger

## Decision
Add a `--ledger` flag to `hermes chat` that auto-loads the
`decision-quality-gate` skill into the session.

## Context
User asked: "make it easier to turn on the decision ledger thing —
typing `/skill decision-quality-gate` every time is annoying."
Session id: `20260523_182600_d4f5a6`. CLI invocation, interactive.

## Evidence Reviewed
- Files:
  - `hermes_cli/main.py:312-355` — argparse setup for `hermes chat`
  - `hermes_cli/main.py:401-418` — `--skills` flag, accepts CSV
  - `cli.py:8412-8430` — `_preload_skills` builds the session skill set
  - `skills/decision-quality-gate/SKILL.md` — exists, name is
    `decision-quality-gate`
- Commands:
  - `grep -rn "preload_skills" hermes_cli/ cli.py` → 4 hits, all
    plumbing the existing `--skills` arg
  - `hermes chat --help` → confirms `--skills` is documented but
    `--ledger` is not
- Docs: `docs/hermes-local-orchestrator.md` — no mention of skill
  flags; not relevant.
- Web sources: (none — local question)
- Prior Hermes memory: session `20260520_141200_a1b2c3` decided to
  keep `--skills` as the only skill-preload knob; new convenience
  flags route through it. Ledger: `~/.hermes/decisions/20260520_141200_a1b2c3/0003-skills-flag.md`.
- Gaps: did not check Telegram gateway side; flagged as open risk.

## Options Considered

### Option A — Add a dedicated `--ledger` flag
Pros: discoverable in `--help`; short; matches user's mental model.
Cons: new surface area; one more thing to test on Windows; the
  precedent says skill-preload routes through `--skills`.
Risk: future skills want their own flag → flag sprawl. Low blast
  radius (CLI-only change).
Validation: `hermes chat --ledger -q "test"` loads the gate skill;
  `hermes chat --help` lists the flag.

### Option B — Document `--skills decision-quality-gate` more prominently
Pros: zero code change; consistent with the prior ledger's
  convention; nothing new to test.
Cons: doesn't actually fix the user's "annoying to type" complaint —
  the long skill name is what they were complaining about.
Risk: user remains annoyed; comes back next week with the same ask.
Validation: edit the docs, ask user to confirm the new docs solve
  their problem.

### Option C — Defer
Pros: lets us see if more skills want preload-shortcuts before we
  commit to a pattern.
Cons: ignores a real user complaint.
Risk: low; the user can keep typing the full skill name.
Validation: revisit if a second skill asks for a shortcut.

## Model / Worker Choice
Selected worker/model: Hermes main loop, model `claude-opus-4-7`,
  reasoning level `medium`. No delegation — single-file CLI change.
Why: too small to delegate; main-loop quality is fine for argparse
  edits.
Fallback: if main-loop tool calls fail, delegate to
  `delegation` toolset with `claude-sonnet-4-6`.
Cost/latency/quality tradeoff: negligible; ~3 turns end-to-end.

## Validation Plan
Commands:
  - `python -m pytest tests/hermes_cli/test_main.py -q`
  - `python -m pytest tests/cli/test_preload_skills.py -q`
  - `hermes chat --ledger --help` (smoke test; new flag must appear)
Manual checks:
  - Run `hermes chat --ledger -q "say hi"` and confirm the session
    loads `decision-quality-gate` before the first turn.
  - Read the diff: confirm no behavioural change when `--ledger`
    is *not* passed.
Success criteria: all tests pass; smoke command succeeds; diff is
  ≤ 30 lines; no Windows-specific path issues (will be re-checked
  by CI on the Windows runner).

## Final Decision
Decision: Option A — add the `--ledger` flag.
Confidence: medium. One-line CLI change with clear tests; the
  flag-sprawl risk is real but distant.
Open risks:
  - Telegram gateway may want a parallel shortcut (`/ledger`); not
    in scope today.
  - Future skills may want similar shortcuts; revisit the
    `--skills <name>` vs dedicated flag question if we get a second
    request.
Rollback: `git revert <commit>`. No state, no migrations; the flag
  is purely additive and defaults to off.
````

---

## File naming and storage

Persisted ledgers live under:

```
~/.hermes/decisions/<session_id>/<seq>-<slug>.md
```

Where:

- `<session_id>` is the session that produced the ledger (e.g.
  `20260523_182600_d4f5a6`).
- `<seq>` is a four-digit zero-padded sequence number within the
  session (`0001`, `0002`, …).
- `<slug>` is a short kebab-case description (`add-ledger-flag`,
  `pick-delegation-model`).

For profile-scoped runs, replace `~/.hermes` with the active profile
root (`~/.hermes/profiles/<name>/`).

Kanban-worker ledgers additionally surface as a `kanban_comment` on
the task they belong to, so the next worker claiming a related task
sees the prior reasoning without having to dig.

---

## Parsing contract

External tooling — the enterprise Judge, the curator, the
`/decisions` slash command (not yet built; see
[`decision-quality-system.md`](decision-quality-system.md)) — parses
ledgers by heading. Do not rename, reorder, or skip these headings:

- `# Decision Ledger`
- `## Decision`
- `## Context`
- `## Evidence Reviewed`
- `## Options Considered`
- `### Option A` / `### Option B` (additional options as `### Option C`, etc.)
- `## Model / Worker Choice`
- `## Validation Plan`
- `## Final Decision`

Sub-bullets inside each section are free-form. Tooling reads them as
opaque markdown; only the section boundaries are structurally
parsed.

---

## Cross-references

- [`decision-quality-system.md`](decision-quality-system.md) — system architecture
- [`../../skills/decision-quality-gate/SKILL.md`](../../skills/decision-quality-gate/SKILL.md) — when and why to produce a ledger
- [`../../skills/research-validator/SKILL.md`](../../skills/research-validator/SKILL.md) — how to fill `Evidence Reviewed` and `Validation Plan` honestly
- [`../../skills/enterprise-council/judge/SKILL.md`](../../skills/enterprise-council/judge/SKILL.md) — the validator that consumes structured leaf ledgers
- [`../../skills/enterprise-council/orchestrator/SKILL.md`](../../skills/enterprise-council/orchestrator/SKILL.md) — the orchestrator that emits ledgers per dispatched task

### How the ledger plugs into the rest of the orchestration stack

| Concern | Doc / skill |
|---|---|
| Job folder the ledger lives in | [`hermes-orchestration-pipeline.md`](hermes-orchestration-pipeline.md) — every job has its own `decision-ledger.md` |
| Worker / model picked in the ledger row | [`../../skills/model-router/SKILL.md`](../../skills/model-router/SKILL.md), [`../ai-intelligence/model-registry.yaml`](../ai-intelligence/model-registry.yaml), [`../ai-intelligence/model-routing-policy.md`](../ai-intelligence/model-routing-policy.md) |
| Fresh AI capabilities cited as options | [`../../skills/ai-improvement-radar/SKILL.md`](../../skills/ai-improvement-radar/SKILL.md), [`../ai-intelligence/ai-improvement-radar.md`](../ai-intelligence/ai-improvement-radar.md) |
| Competitive feature harvester input | [`../competitive/openhuman-paperclip-research.md`](../competitive/openhuman-paperclip-research.md) |
| End-of-job mining of ledger outcomes | [`self-improvement-loop.md`](self-improvement-loop.md), [`../../skills/self-improvement-loop/SKILL.md`](../../skills/self-improvement-loop/SKILL.md) |
| Publishing a ledger-backed decision | [`github-publisher-runtime.md`](github-publisher-runtime.md), [`../../skills/github-publisher/SKILL.md`](../../skills/github-publisher/SKILL.md) |
| Council that emits ledgers per dispatched specialist | [`../../skills/aos-full-agent-team/SKILL.md`](../../skills/aos-full-agent-team/SKILL.md) |
| Mission anchor (Principle 3) | [`../mission/best-coding-tool-mission.md`](../mission/best-coding-tool-mission.md), [`../../skills/best-coding-tool-mission/SKILL.md`](../../skills/best-coding-tool-mission/SKILL.md) |

### Posture: private and local-first

Ledgers are plain markdown on the user's disk. They are never
uploaded, never relayed through a Hermes-owned cloud service, and
never shared with third parties. The Android APK cockpit reads
ledgers from the same on-disk contract — there is no cockpit-only
mirror. The Hermes backend is the engine; the APK is the cockpit.

### Invocation (CLI, gateway DM, or cockpit)

```text
/reload-skills                              # after editing skills
/decision-quality-gate                      # load the gate into a session
/decision-quality-gate <decision-id>        # gate a specific decision
/research-validator                         # fill Evidence + Validation honestly
/model-router <task-type>                   # routing decision → ledger row
/ai-improvement-radar                       # keeps the cited options fresh
/self-improvement-loop                      # mines ledgers for routing/prompt fixes
/github-publisher <job-id>                  # consumes pass/conditional ledgers
```
