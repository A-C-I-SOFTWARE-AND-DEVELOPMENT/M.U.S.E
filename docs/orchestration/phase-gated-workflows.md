# Phase-gated workflows

> **Status:** core engine landed (see
> `hermes_cli/workflows.py` and `hermes_cli/workflow_models.py`).
> Wiring into the orchestrator job controller is tracked in
> `docs/orchestration/next-roadmap.md`.

M.U.S.E. runs every non-trivial job through eight explicit, named
phases. The phase log is on disk under the job folder, the transitions
are gated, and the gates are auditable. The goal is to make it
impossible for an autonomous agent to "just keep going" without
leaving a trail of why each step was allowed.

This page is the contract. If something in the engine disagrees with
what's written here, the engine is wrong — file an issue.

## The eight phases

In canonical order:

| # | Phase | What happens | Owns a report? |
|---|---|---|:---:|
| 1 | `intake` | A job has been submitted and its folder exists on disk. | no |
| 2 | `research` | Read the codebase, gather evidence, surface unknowns. | yes |
| 3 | `planning` | Convert evidence into a concrete plan of action. | yes |
| 4 | `approval` | A human (or `trusted_local`) reviews the plan. | yes |
| 5 | `implementation` | Apply the change. | yes |
| 6 | `validation` | Run gates, tests, judges. | yes |
| 7 | `publish` | Push branch, open PR, deliver artifact. | yes |
| 8 | `retrospective` | Capture lessons; update routing / skills / memory. | yes |

Intake is bookkeeping — by the time we have a job folder, intake is
done. Every other phase owns a report file at `phases/<name>.md`.

## Phase statuses

A phase always sits in exactly one of:

- `pending` — known about, not started
- `running` — work is in progress
- `blocked` — work is paused, waiting on something out-of-band
- `needs_approval` — the gate has fired and is waiting for a human
- `approved` — a human (or `trusted_local`) said yes
- `rejected` — a human said no; the job is blocked until the caller resolves it
- `completed` — the phase finished cleanly
- `failed` — the phase ended unrecoverably (timeout, crash, judge said no)

`approved` and `completed` are the two terminal statuses that let the
next phase start. `failed` and `rejected` end the phase but do not
advance the job; the caller decides whether to re-run, escalate, or
abandon.

## Gate rules

These are the rules the engine enforces. They are not aspirational —
they are checked in `transition_phase`, `require_approval`, and
`approve_phase`.

1. **Research can start automatically.** No predecessor evidence is
   required. Submitting a job and calling `transition_phase(job,
   research, research, reason)` is enough.
2. **Planning can start after research evidence exists.** "Evidence"
   means `research` is in a terminal status *and* `phases/research.md`
   is non-empty. Until both hold, planning is refused.
3. **Implementation requires explicit approval unless trusted-local
   config says otherwise.** Without `trusted_local`, advancing into
   `implementation` requires the `approval` phase to be `approved`
   first. With `trusted_local`, the approval phase can be
   auto-approved (still call `approve_phase` so the audit trail
   records who/why).
4. **Validation can run automatically after implementation.** Once
   `implementation` is in a terminal status, validation transitions
   freely to `running`.
5. **Publishing requires explicit approval.** The `publish` phase
   always lands in `needs_approval` on transition; nothing can flip it
   to `running` except `approve_phase`. `trusted_local` does **not**
   downgrade this — publication is visible to others, so it always
   needs a human.
6. **Destructive commands always require approval.** When a worker
   would run something destructive (`rm -rf`, force-push, database
   drop, etc.), it must call `require_approval(job, phase,
   "destructive", reason=...)`. That call escalates the phase to
   `needs_approval` regardless of `trusted_local`.
7. **Secrets operations always require approval.** Reading, rotating,
   or emitting credentials must go through `require_approval(job,
   phase, "secrets", reason=...)`. Same escalation, same rule.

The two `ALWAYS_APPROVED_ACTIONS` (`destructive`, `secrets`) are the
only labels that bypass `trusted_local`. Everything else is
configurable.

## On-disk layout

Inside the job folder:

```
<job_dir>/
    phases/
        research.md
        planning.md
        approval.md
        implementation.md
        validation.md
        publish.md
        retrospective.md
    status.json
```

`status.json` is the serialized `WorkflowState`. It is hand-editable —
the engine treats unknown fields as forward-compat and re-inserts any
missing canonical phase on the next load. Each phase carries an
append-only `history` array; nothing in the engine ever rewrites a
history entry, only appends.

## Plain English requirement

Every phase report — `phases/research.md` through
`phases/retrospective.md` — **must** include a `## Plain English`
section that explains in normal language what happened and why.

`write_phase_report` refuses to write a body that doesn't contain the
heading (case-insensitive). The check is intentional: the engine
optimises for a future reader (a human, a Judge, a later session) who
has no context, and the Plain English section is the only part that
reliably survives across model versions and skill rewrites.

A minimum-viable report:

```markdown
# Research report

## Findings
- The auth code path lives in `gateway/auth.py`.
- There is no existing rate limiter.

## Plain English
We looked through the gateway and found where authentication is handled.
There is no rate limiter today, so adding one is in scope. Nothing on
disk needs to change yet; this is just notes for the planning phase.
```

## API surface

The engine is intentionally small — these are the only public entry
points.

| Function | What it does |
|---|---|
| `initialize_phases(job)` | Create `phases/` and `status.json`. Idempotent. |
| `get_current_phase(job)` | Return the `Phase` the workflow is on. |
| `transition_phase(job, from, to, reason)` | Start a phase in place or advance to the next phase. |
| `complete_phase(job, phase, reason=...)` | Mark a phase `completed`. |
| `fail_phase(job, phase, reason)` | Mark a phase `failed` with reason. |
| `require_approval(job, phase, action, reason=...)` | Force a phase to `needs_approval`. |
| `approve_phase(job, phase, approver, note="")` | Approve a phase. |
| `reject_phase(job, phase, reason)` | Reject a phase. |
| `write_phase_report(job, phase, content)` | Write `phases/<phase>.md` (must include Plain English). |
| `load_state(job)` | Return the on-disk `WorkflowState`. |
| `list_phases(job)` | Phases in canonical order. |

See `tests/test_phase_gated_workflows.py` for the full happy-path walk
through all eight phases.

## What this engine does not do

- It does not run anything. Workers, models, validators, and
  publishers all live elsewhere; the engine only tracks where we are
  and what's allowed next.
- It does not write the phase reports for you. A worker (or the
  orchestrator) writes the report and passes the content into
  `write_phase_report`.
- It does not perform side effects. No network, no subprocess, no
  imports of the agent loop. Everything is filesystem state under the
  job folder.

## Recommended reading

- `docs/orchestration/decision-ledger.md` — the audit trail that
  per-phase history feeds into.
- `docs/orchestration/local-validation-gates.md` — what the
  `validation` phase actually runs.
- `docs/orchestration/github-publisher-runtime.md` — what the
  `publish` phase actually invokes.
- `skills/phase-gated-workflow/SKILL.md` — the playbook a session
  loads when it needs to drive a job through these phases.
