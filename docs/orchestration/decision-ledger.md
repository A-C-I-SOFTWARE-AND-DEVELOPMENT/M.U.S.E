# Decision Ledger — Spec

The **decision ledger** is the user-facing record of a non-trivial
decision Hermes makes on the user's behalf. It replaces hidden chain-of-
thought with an artifact a human can read, diff, and challenge.

The canonical template lives at
[`templates/orchestration/decision-ledger-template.md`](../../templates/orchestration/decision-ledger-template.md).
The runtime contract — when to write one, where it lives, and how
quality gates consume it — is described here. The
[`decision-quality-gate`](../../skills/decision-quality-gate/SKILL.md)
and [`research-validator`](../../skills/research-validator/SKILL.md)
skills are the agent-side enforcement of this contract.

## What a ledger is for

* **Visible reasoning, not hidden CoT.** Hermes does not paste raw
  chain-of-thought into the ledger. It records the *inputs* (evidence),
  the *options*, the *selection*, the *validation*, and the *rollback*.
  A reader can reconstruct *why* without reading internal monologue.
* **Replayable.** Anyone with the ledger plus repo access should be
  able to re-run the validation commands and reach the same verdict.
* **Auditable.** Each accepted ledger writes one `decision` event to
  the council audit trail (see `skills/enterprise-council/shared/audit.md`)
  so the Monitor can spot patterns (same option always loses, same risk
  keeps recurring, same worker keeps getting rejected).

## When a ledger is required

Write a ledger when **any** of the following hold:

1. The work involves **selecting between two or more credible options**
   (architecture, library, model, leaf, schema, rollout strategy).
2. The work **selects a model / worker** for a multi-step or
   user-visible run. Picking the model *is* a decision; record it.
3. The classified risk under
   `enterprise.policy.classify(task)` is **MEDIUM** or **HIGH**, OR the
   autonomy mode is `strict`.
4. The change is **hard to reverse** (schema migration, public API
   surface, destructive git operation, sent message, money movement).
5. The decision **supersedes a prior ledger** — even if the new choice
   is "obviously right" in the moment.

You do *not* need a ledger for:

* Read-only lookups, formatting fixes, comment changes, one-line bug
  fixes that pass the existing test suite and touch no external state.
* Mechanical edits dictated by an already-accepted ledger.

When in doubt: write the ledger. The cost of an unneeded ledger is one
file; the cost of a missing ledger is an un-auditable mutation.

## Lifecycle and statuses

```
draft ─► proposed ─► accepted ─► (optionally) superseded / rolled-back
```

* **draft** — the author is still gathering evidence and listing
  options. Not yet a candidate for execution.
* **proposed** — every required section is filled in, including the
  validation plan, but the validation has not yet been run.
* **accepted** — the validation plan has been executed (or explicitly
  waived with a recorded reason) and the Final Decision block is
  filled in. From this point the decision is committed to.
* **superseded** — a later ledger replaces this one. The new ledger
  fills in `Supersedes:` and the old one is marked `superseded`.
* **rolled-back** — the rollback trigger fired. The ledger is updated
  with the trigger that fired, the actual rollback action that ran, and
  the timestamp. A follow-up ledger usually replaces it.

A ledger never silently disappears. Mistakes get a new ledger that
supersedes the old one, not an in-place rewrite.

## File layout

```
.hermes/decisions/
├── 2026-05-23_143012-pick-judge-model.md          # accepted
├── 2026-05-23_151155-finance-leaf-retry-budget.md # proposed
└── 2026-05-24_090402-pick-judge-model.md          # supersedes the first
```

* One ledger per file. The filename is
  `YYYY-MM-DD_HHMMSS-<slug>.md` so chronological `ls` matches creation
  order.
* Storage is *workspace-relative* so Hermes' backend-aware file tools
  keep the ledger with the workspace on local, docker, ssh, modal, and
  daytona backends (same convention as `.hermes/plans/`).
* The `.hermes/decisions/` directory is *not* git-ignored. Ledgers are
  the record. Commit them with the work they cover.

## Required sections

The template enumerates the schema; this section just states what is
*required* for a ledger to be considered valid by
`decision-quality-gate`.

| Section | Required for | Notes |
|---|---|---|
| Decision | all statuses | One sentence; no jargon. |
| Context | all statuses | Must name the triggering event. |
| Evidence Reviewed | proposed + | ≥1 concrete item; assumptions go in Open risks, not here. |
| Options Considered | proposed + | ≥2 options; "do nothing" and "defer to user" count. |
| Selected Model / Worker | proposed + | Always — including for code edits. Name the model. |
| Validation Plan | proposed + | Must contain at least one Command or one Manual check with a measurable success criterion. |
| Final Decision | accepted + | Includes Confidence and Rollback. Empty until accepted. |

`decision-quality-gate` refuses to let the orchestrator dispatch on a
ledger that fails these requirements.

## Evidence quality rules

The `research-validator` skill is the per-evidence-item check; the
ledger-level rules are:

* **Every option must cite evidence** by reference back to the
  "Evidence Reviewed" list. An option with no citations is an opinion,
  and opinions go in Open risks.
* **Web sources are dated.** Without an access date the source is
  treated as "untrusted_unknown_age" and the validator will flag it.
* **Commands are reproducible.** A command like `pytest` without a path
  or selector is rejected; a command like `pytest tests/foo/test_bar.py
  -k baz` is accepted.
* **Secrets are never inlined.** Reference services by name; never
  paste tokens, even truncated. The council redactor will mask them on
  audit write, but the ledger itself should never have contained them.
* **Hidden chain-of-thought is never pasted.** If the author wants to
  preserve reasoning, summarise it into the relevant section. The
  ledger is for the *structured* record.

## Selected Model / Worker — what to record

This block is mandatory for every proposed ledger and is the single
most useful row for cost/quality analysis. It must include:

* **Selected** — the concrete model id (e.g. `claude-opus-4-7`,
  `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`) or leaf name (e.g.
  `enterprise-finance`).
* **Why** — the one sentence that distinguishes this worker from the
  alternatives.
* **Rejected alternatives** — each one with a reason (cost, latency,
  capability, policy, availability). Listing the rejections is what
  makes the cost/quality tradeoff visible.
* **Fallback** — what to switch to if the selected worker is
  unavailable or its result fails the judge.
* **Cost / latency / quality tradeoff** — explicit. Rough numbers are
  fine; the point is to make the tradeoff legible.

The Monitor uses these rows to spot patterns like "Opus selected for
LOW-risk read-only lookups" or "Haiku selected for HIGH-risk
mutations" — both are smells worth surfacing.

## Validation Plan — what makes one acceptable

A validation plan is acceptable when a different agent (or the user)
could execute it and arrive at the same verdict. Concretely:

* **Commands** must be copy-pasteable, including paths and selectors.
* **Manual checks** must name the file/screen and what to look for.
* **Success criteria** must be observable (test passes, metric below
  threshold, output matches schema). "Looks good" is not a criterion.
* **Failure response** must be one of: retry once, escalate to user,
  roll back, open follow-up ledger. Silent failure is not an option.

## Final Decision — what makes one acceptable

The Final Decision block is filled in *after* the validation plan ran.
It must include:

* **Decision** — the choice restated, pointing to the option label.
* **Confidence** — `low | medium | high`, with the one sentence that
  says what would have to be true for the confidence call to be wrong.
* **Open risks** — what we are knowingly accepting, and the trigger
  that would force a revisit.
* **Rollback** — trigger, action, owner, window. A rollback "we'd
  figure it out" is rejected by `decision-quality-gate`.

## Cross-references

A ledger is more useful when it points at the artifacts it produced
and was produced from:

* `.hermes/plans/<plan>.md` — the plan this ledger committed to.
* `spikes/NNN-<slug>/` — spikes whose verdict fed this decision.
* `session_id` + audit event ids — for runs that produced this ledger.
* PR / commit refs — the code that implements the decision.
* Superseded-by — the newer ledger that replaced this one.

These go in the HTML-commented footer at the bottom of the template so
they don't clutter the readable body.

## Relationship to other systems

* **Plans (`skills/software-development/plan`,
  `skills/software-development/writing-plans`)** — a plan answers
  *what to do, step by step*. A ledger answers *why this approach, this
  worker, with this validation and rollback*. A complex feature
  typically gets one ledger and one or more plans; the ledger links to
  the plans.
* **Spikes (`skills/software-development/spike`)** — a spike answers
  *is this even possible*. Spike verdicts are evidence for a ledger,
  not a substitute.
* **Enterprise Council** — the Orchestrator writes ledgers for any
  HIGH-risk task before dispatch; the Judge consults the ledger when
  it cross-checks the leaf's result; the Monitor reads accepted
  ledgers + audit rows together to propose improvements.
* **Hermes plans lane** — accepted ledgers can be promoted to plans
  via the existing curator surface; the ledger stays as the rationale
  artifact.
