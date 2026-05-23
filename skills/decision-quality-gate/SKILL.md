---
name: decision-quality-gate
description: "Block dispatch on a decision until its ledger is complete, validated, and rollback-ready."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [decision, ledger, gate, validation, orchestration, audit, autonomy, safety]
    related_skills:
      - research-validator
      - enterprise-orchestrator
      - enterprise-judge
      - enterprise-monitor
      - plan
      - writing-plans
      - spike
---

# Decision Quality Gate

Use this skill **before dispatching** any non-trivial decision —
selecting a model/worker, picking an architecture, committing to a
rollout, mutating shared state. The gate refuses to let work proceed
on a missing, incomplete, or weak ledger.

The full *system* this gate belongs to is described in
[`docs/orchestration/decision-quality-system.md`](../../docs/orchestration/decision-quality-system.md).
The *ledger spec* is in
[`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md).
The *template* every ledger copies from is in
[`templates/orchestration/decision-ledger-template.md`](../../templates/orchestration/decision-ledger-template.md).

## Load this skill when

* You are about to **dispatch a leaf, subagent, or external tool** on
  behalf of the user.
* You are about to **select a model / worker** for a multi-step or
  user-visible run.
* The work is classified **MEDIUM or HIGH** by
  `enterprise.policy.classify(task)`, or autonomy mode is `strict`.
* The change is **hard to reverse** (schema migration, public API
  surface, destructive git, sent message, money movement).
* The user says "make sure this is right", "double-check", "are you
  sure", or otherwise asks for visible justification.

Do **not** load this for read-only lookups, formatting fixes, or
one-line bug fixes already covered by tests.

## What the gate does, in order

1. **Locate the ledger.** Look in `.hermes/decisions/` for a file
   matching this task. If none exists, refuse to dispatch and prompt
   the author to create one from the template.
2. **Run `research-validator`** on the ledger. The validator scores
   evidence quality 0–100 and flags individual items.
3. **Check required sections** for the ledger's target status
   (`proposed` for dispatch, `accepted` for completion).
4. **Apply hard rejections** — secrets, hidden chain-of-thought,
   in-place rewrites, single-option "decisions", missing rollback.
5. **Compare validator score to the threshold** for the task's risk
   level.
6. **Emit one of**: `gate_pass`, `gate_warn`, `gate_fail` with a
   structured reason list.
7. **Write one audit row** (`event="decision_gate"`) so the Monitor
   can spot patterns. Never write the ledger body to the row — only
   the ledger id, status, score, and reason list.

## Required sections by target status

The ledger is being moved from `draft` → `proposed` (before dispatch)
or `proposed` → `accepted` (after validation). The required sections
differ:

### To reach `proposed` (dispatch-eligible)

| Section | Acceptance check |
|---|---|
| Decision | Non-empty, one sentence, no jargon. |
| Context | Names the triggering event (issue, user msg, prior ledger). |
| Evidence Reviewed | ≥1 concrete item per option that cites it. |
| Options Considered | ≥2 options. Both have Pros / Cons / Risks / Validation / Cost-Latency-Quality / Evidence-supporting. |
| Selected Model / Worker | All five sub-fields filled: Selected, Why, Rejected alternatives, Fallback, Cost/latency/quality tradeoff. |
| Validation Plan | ≥1 reproducible command *or* manual check with an observable success criterion. Failure response named. |
| Final Decision | May be empty at `proposed`. |

### To reach `accepted` (post-validation)

Everything above, plus the Final Decision block:

| Sub-field | Acceptance check |
|---|---|
| Decision | Restates the choice, names the option label. |
| Confidence | One of `low | medium | high`. Includes the one sentence saying what would have to be true for the confidence call to be wrong. |
| Open risks | Each has a trigger that would force a revisit. |
| Rollback | Trigger, Action, Owner, Window all present. None of them is "we'd figure it out". |

## Hard rejections (any → `gate_fail`)

The gate refuses to advance the ledger if **any** of:

1. **Missing ledger** for a MEDIUM/HIGH task or for a worker
   selection.
2. **Single option.** "Do nothing" and "defer to user" are valid
   options and should be enumerated when relevant. A ledger with only
   one option is not a decision.
3. **Selected Model / Worker blank** or missing sub-fields.
4. **Validation Plan is unobservable** ("looks good", "seems fine",
   no command/check, no success criterion).
5. **Rollback is vague** ("we'd figure it out", "revert if needed"
   with no commit/command).
6. **Secret pasted into ledger.** Token-shaped string, API key, bearer
   token, password, private key. The author rewrites; the council
   redactor still scrubs on audit write.
7. **Hidden chain-of-thought pasted in.** Reasoning monologue in any
   section. The author summarises into the appropriate field
   (Evidence, Options, Why).
8. **In-place rewrite of an `accepted` ledger.** Force a new ledger
   with `Supersedes:` pointing at the old one.
9. **Validator score below threshold** for the risk level (see next
   section).

## Score thresholds

The `research-validator` skill scores the ledger 0–100. The gate
applies:

| Risk classification | Minimum score for `proposed` | Minimum score for `accepted` |
|---|---|---|
| LOW (only if a ledger was written anyway) | 50 | 60 |
| MEDIUM | 70 | 75 |
| HIGH | 85 | 90 |

A score below threshold is `gate_fail` with the validator's flags as
the reason. A score within 5 points of threshold is `gate_warn` — the
gate passes but logs a follow-up suggestion (add one more evidence
item, name an independent source, tighten the success criterion).

## Output contract

The gate emits a single structured response:

```json
{
  "verdict": "gate_pass | gate_warn | gate_fail",
  "ledger_id": "2026-05-23_143012-pick-judge-model",
  "target_status": "proposed | accepted",
  "validator_score": 84,
  "threshold": 85,
  "reasons": [
    "rollback.window: missing — name the time horizon over which the rollback path stays cheap"
  ],
  "warnings": [
    "evidence.web: only one web source cited; add an independent corroboration"
  ],
  "audit_event": "decision_gate"
}
```

On `gate_pass` the orchestrator may proceed with dispatch. On
`gate_warn` it proceeds and surfaces the warning to the author. On
`gate_fail` it refuses to dispatch and surfaces the reason list to
the author so the ledger can be fixed.

## What the gate must NOT do

* **Do not edit the ledger.** The gate reads, scores, and reports.
  The author (the orchestrator or a human) edits.
* **Do not lower the risk classification** to clear a threshold. Risk
  is set by `enterprise.policy.classify`; if the classification looks
  wrong, file a Monitor proposal — do not override at gate time.
* **Do not paste any secret value into the audit row**, even when
  reporting that one was found in the ledger. Log "secret_detected:
  <field>" only.
* **Do not skip the Validator.** The gate's hard checks are
  necessary but not sufficient; the score is what catches the soft
  failures (one option weakly evidenced, web source undated,
  confidence asserted without justification).
* **Do not run any commands listed in the Validation Plan.** That is
  the Judge / leaf's job. The gate evaluates whether the plan *could*
  be run by an independent reader.
* **Do not bypass on user pressure.** "Just dispatch it, I'll fix
  the ledger later" is exactly the failure mode this gate exists to
  prevent. Surface the reasons and ask the user to fix the ledger or
  to formally accept the missing-ledger risk via a one-line
  acknowledgment that itself becomes the (one-option) ledger.

## How to use this skill, step by step

1. **Find or create the ledger.**
   - If absent: copy `templates/orchestration/decision-ledger-template.md`
     to `.hermes/decisions/YYYY-MM-DD_HHMMSS-<slug>.md` and fill it
     in. Use Hermes' workspace-relative file tools so the ledger ends
     up on the right backend.
2. **Run `research-validator` on the ledger path.** Note the score
   and the per-item flags.
3. **Run the gate** with target status `proposed` (pre-dispatch).
4. If `gate_pass`: dispatch.
5. If `gate_warn`: dispatch and address the warning in the next
   iteration.
6. If `gate_fail`: fix the listed reasons, re-run validator, re-run
   gate. Do not dispatch.
7. After dispatch and validation, re-open the ledger, fill in Final
   Decision, run the gate again with target status `accepted`.
8. On `gate_pass` for `accepted`: status → `accepted`. The council
   runtime writes one `decision` audit row tying the ledger id to the
   session id.

## Integration with the Enterprise Council

* **Orchestrator** calls this gate before
  `enterprise.council.dispatch(...)` for any task that meets the
  ledger-required rule. If the gate fails, the orchestrator does not
  dispatch and surfaces the reasons.
* **Judge** reads the ledger's Validation Plan to decide what counts
  as success when it `cross_check`s the leaf's result.
* **Monitor** reads the `decision_gate` and `decision` audit rows
  alongside everything else and proposes improvements (e.g.
  "validator score on `finance.*` ledgers dropped 15 points this
  week"). Improvements arrive via the existing drafts lane.

## What the user sees

Nothing fancy. One line on a clean pass:

```
DECISION GATE: pass (score 84/85, target=proposed, ledger=2026-05-23_143012-pick-judge-model)
```

Or, on a fail:

```
DECISION GATE: fail (score 62/70, target=proposed, ledger=...)
  - options: only one option enumerated; add an alternative or "do nothing"
  - validation: success criterion is unobservable ("looks good")
  - rollback: missing trigger
```

No internal monologue. The reasons are actionable and point at the
section that needs editing.
