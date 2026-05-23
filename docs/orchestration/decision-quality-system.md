# Decision Quality System

Hermes is a personal orchestrator. It picks workers, drafts prompts,
researches, and validates — and it does these things on the user's
behalf, sometimes autonomously. The **Decision Quality System** is the
set of rules and artifacts that keeps those decisions visible,
defensible, and reversible.

It has four pieces:

| Piece | Lives at | Role |
|---|---|---|
| **Decision ledger template** | [`templates/orchestration/decision-ledger-template.md`](../../templates/orchestration/decision-ledger-template.md) | The canonical schema every ledger fills in. |
| **Ledger spec** | [`docs/orchestration/decision-ledger.md`](./decision-ledger.md) | When a ledger is required, lifecycle, file layout, required sections. |
| **Decision Quality Gate skill** | [`skills/decision-quality-gate/SKILL.md`](../../skills/decision-quality-gate/SKILL.md) | The agent-side gate. Blocks dispatch on missing/weak ledgers. |
| **Research Validator skill** | [`skills/research-validator/SKILL.md`](../../skills/research-validator/SKILL.md) | The agent-side evidence check. Rates each cited source, flags assumptions, scores the ledger. |

This document is the *why*: how the pieces fit together, what
problems they solve, and the behavioural invariants Hermes is
expected to obey.

## Why this system exists

Hermes can talk like an expert. It can also confidently pick the wrong
model for a job, skip a validation step, and overwrite a config in a
way nobody can later explain. The Decision Quality System exists to
make those failure modes hard to commit accidentally:

1. **Visible reasoning, not hidden CoT.** Users do not want a stream
   of internal monologue. They want the *evidence* the decision rested
   on, the *options* that were weighed, the *selection* and *why*, the
   *validation*, and the *rollback*. Ledgers carry exactly those
   fields. Hidden chain-of-thought never reaches the artifact.
2. **No silent worker selection.** Picking a model is a decision and
   gets recorded. The Monitor can then catch patterns like "Opus chosen
   for a read-only lookup" or "Haiku chosen for a HIGH-risk mutation".
3. **No untraceable claims.** Every option must trace back to evidence
   on the ledger's Evidence list. The Research Validator scores each
   piece of evidence and refuses to let unsubstantiated claims pose as
   facts.
4. **No undoable autonomy.** Every accepted ledger names a rollback
   trigger, action, owner, and window. Hermes will not dispatch a
   HIGH-risk task whose ledger says "rollback: we'd figure it out".

## Core behaviours Hermes must obey

The skills enforce these — this section is the contract:

1. **One ledger per non-trivial decision.** Trivial = read-only,
   single-line, fully covered by existing tests. Everything else gets
   a ledger. When in doubt: write the ledger.
2. **Ledger before dispatch.** For tasks classified MEDIUM/HIGH (see
   `skills/enterprise-council/shared/policy.md`), the ledger must be at
   `proposed` status before the Orchestrator dispatches. The Gate
   blocks dispatch otherwise.
3. **Two options minimum.** A "decision" with one option is a
   foregone conclusion, not a decision. "Do nothing" and "defer to
   user" are valid options. List them when relevant.
4. **Selected Model / Worker is mandatory.** Even for a code edit:
   name the model that's making it.
5. **Validation is observable.** "Looks good" is not a success
   criterion. Tests pass, metrics below threshold, output matches
   schema — *those* are criteria.
6. **Rollback is concrete.** Trigger, action, owner, window. No
   ledger reaches `accepted` without it.
7. **Confidence is honest.** Picking `high` confidence costs nothing
   in the moment and everything later. The author records what would
   have to be true for the confidence call to be wrong.
8. **Hidden chain-of-thought never reaches the ledger.** If reasoning
   needs preservation, summarise it into the appropriate section.

## How the pieces interact

```
                ┌──────────────────────────────────────────┐
                │ User goal arrives at the Orchestrator    │
                └────────────────────┬─────────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │ Need a ledger?      │
                          │ (policy.classify +  │
                          │  ledger spec rules) │
                          └─────┬───────────┬───┘
                          no    │           │  yes
                                │           ▼
                                │   ┌──────────────────────┐
                                │   │ Author writes draft  │
                                │   │ ledger from template │
                                │   └──────────┬───────────┘
                                │              ▼
                                │   ┌──────────────────────┐
                                │   │ research-validator   │
                                │   │ scores each evidence │
                                │   │ item, flags gaps     │
                                │   └──────────┬───────────┘
                                │              ▼
                                │   ┌──────────────────────┐
                                │   │ decision-quality-    │
                                │   │ gate checks required │
                                │   │ sections + scores    │
                                │   └──────────┬───────────┘
                                │     pass     │
                                │              ▼
                                │   ┌──────────────────────┐
                                ▼   │ Ledger → proposed    │
                          ┌─────────┴───────┐  ▼            │
                          │ Orchestrator    │  dispatch     │
                          │ dispatches leaf │◄──────────────┘
                          └────────┬────────┘
                                   ▼
                          ┌────────────────┐
                          │ Judge cross-   │
                          │ checks result  │
                          │ vs. validation │
                          └────────┬───────┘
                                   ▼
                          ┌────────────────┐
                          │ Ledger →       │
                          │ accepted +     │
                          │ audit row      │
                          └────────────────┘
```

The Gate and the Validator are *advisory to the Orchestrator and
binding on the leaf*. A leaf cannot dispatch a downstream subagent on a
decision whose ledger has not passed the Gate.

## What "visible reasoning, not hidden CoT" means in practice

Hermes uses the model's reasoning to *find* evidence, *enumerate*
options, and *pick* a selection. None of that internal reasoning is
copied verbatim into the ledger. Instead:

* The **Evidence Reviewed** section lists the artifacts the reasoning
  consulted (files, commands, docs, web sources, prior memory).
* The **Options Considered** section lists the candidates the
  reasoning generated, each with pros / cons / risks / validation /
  cost-quality, and each option cites evidence.
* The **Selected Model / Worker** and **Final Decision** sections
  record the conclusion, not the trace that led to it.
* The **Validation Plan** captures what an *independent* reader could
  run to confirm the conclusion. That's the real check on the
  reasoning — not the reasoning itself.

If a future Hermes feature surfaces extended thinking blocks, those
blocks stay in the runtime and the audit trail (hashed), not in the
ledger.

## Scoring (Research Validator)

The Research Validator scores a ledger out of 100 on four axes —
**Coverage** (evidence breadth), **Reproducibility** (can a reader
re-run it), **Independence** (multiple sources, not just one), and
**Honesty** (assumptions called out as assumptions). The default Gate
threshold for `proposed` status is **70**; HIGH-risk tasks bump the
threshold to **85**. The exact rubric lives in the
`research-validator` SKILL.

The score is recorded on the ledger and in the audit row so the
Monitor can flag systemic drift (e.g. "validator score on
`finance.*` ledgers dropped 15 points this week").

## Failure modes the system is designed to catch

| Failure mode | Caught by | How |
|---|---|---|
| Ledger missing for a MEDIUM/HIGH task | Gate | Refuses dispatch. Audit row `validation=ledger_missing`. |
| Only one option listed | Gate | Refuses `proposed` status. |
| Option with no cited evidence | Validator | Flags as `unsubstantiated`. Score penalty. |
| Web source with no access date | Validator | Flags as `untrusted_unknown_age`. Score penalty. |
| `Selected Model / Worker` blank | Gate | Refuses `proposed`. |
| Validation plan is "looks good" | Gate | Refuses — needs observable criterion. |
| Rollback is "we'd figure it out" | Gate | Refuses `accepted`. |
| Confidence `high` with no rationale | Validator | Score penalty + warning. |
| Secret pasted into ledger | Gate | Refuses, asks author to rewrite. Council redactor still scrubs on audit write. |
| In-place rewrite of an accepted ledger | Gate | Refuses; forces a new ledger with `Supersedes:`. |
| Hidden chain-of-thought pasted in | Validator | Flags and asks the author to summarise into the appropriate section. |

## Relationship to the Enterprise Council

* **Orchestrator** writes / updates ledgers for any task it dispatches
  that meets the ledger-required rule, and consults
  `decision-quality-gate` before dispatching.
* **Leaf agents** consult their parent ledger to know which validation
  criteria they're responsible for satisfying. They do not edit the
  ledger themselves — they emit `VALIDATE:` tags the Judge can
  cross-check.
* **Judge** treats the ledger's Validation Plan as ground truth for
  what counts as success. Result schema + validation criteria together
  are what `cross_check` evaluates.
* **Monitor** reads accepted ledgers alongside the audit trail. Drift
  in validator scores, recurring rollbacks, or rejected-option
  patterns become improvement proposals via the existing drafts lane.

## Relationship to the rest of Hermes

* **Plans** (`software-development/plan`,
  `software-development/writing-plans`) are the *what to do*; ledgers
  are the *why this approach with this worker*. A complex feature
  usually has one ledger and one or more plans. The ledger links to
  the plans; each plan can link back to the ledger.
* **Spikes** (`software-development/spike`) feed evidence into a
  ledger. A spike verdict is *evidence*; the ledger is the
  *commitment*.
* **The Android local orchestrator** drafts handoff prompts for
  external AI tools rather than calling provider APIs directly. The
  Decision Quality System still applies — ledgers describe the
  decision to hand off, which tool was selected and why, and the
  validation the user will perform after pasting. The ledger lives in
  the workspace, not on the device.

## What this system explicitly does *not* do

* It does **not** replace plan-mode or spike-mode. They answer
  different questions.
* It does **not** automate the user's review for HIGH-risk decisions.
  The Orchestrator still escalates per the policy taxonomy; the
  ledger is what the user reads when they're asked to approve.
* It does **not** expose the model's raw reasoning to the user.
  Visible reasoning is the *structured* artifact.
* It does **not** retain or transmit secrets — the ledger never
  contains them, and the audit row is scrubbed even if a leaf
  misbehaves (see `skills/enterprise-council/shared/audit.md`).

## Quick-start for an agent

1. Decide whether the work needs a ledger (see "When a ledger is
   required" in the spec).
2. Copy `templates/orchestration/decision-ledger-template.md` to
   `.hermes/decisions/YYYY-MM-DD_HHMMSS-<slug>.md`.
3. Fill in Decision, Context, Evidence Reviewed, Options Considered
   (≥2), Selected Model / Worker, Validation Plan.
4. Run the Research Validator on the file. Address any flags.
5. Run the Decision Quality Gate. Get to `proposed`.
6. Dispatch the work.
7. Run the Validation Plan. Fill in Final Decision (Decision,
   Confidence, Open risks, Rollback). Status → `accepted`.
8. The audit row is written automatically by the council runtime; the
   Monitor picks it up from there.
