# Worker selection — `<task_id>`

> Rendered by `muse_cli/model_router.py:render_report()`. This file is
> the **template** the router renders into; do not edit a rendered
> instance and expect it to round-trip. Edit this template if you want
> to change the shape of every future report.

**Category:** `<task_category>`  
**Summary:** <task_summary>  
**Primary:** `<primary_worker_id>`  
**Validator:** `hermes-local`  
**Publisher:** `<publisher_worker_id or —>`  
**Registry:** `<yaml | builtin | merged>`

## Selected workers

| worker | role | score | approval | rationale |
| --- | --- | ---:| :---: | --- |
| `<worker_id>` | <primary | validator | publisher | researcher | approver> | 0.00 | yes/— | <one-line why this worker, not the others> |

Roles:

- **primary** — does the work.
- **validator** — runs tests, lints, diff review (always `hermes-local`).
- **publisher** — opens branch / PR / comment (always `github-publisher`,
  gated by `github.allow_writes` + the repo allowlist).
- **researcher** — fetches current external docs (`browser-research`).
- **approver** — `human-approval`, gating destructive / publish /
  remote-tunnel / continuous-listening flows.

## Rejected workers

- `<worker_id>` — <reason: detection failure, capability gap, cost/quality
  filter, approval not granted, manual-only worker, etc.>

Every registered worker either appears in **Selected** or in
**Rejected**. The router never silently drops a worker.

## Fallback plan

1. `<worker_id>` — first fallback if the primary fails validation.
2. `<worker_id>`
3. `hermes-local`  — terminal fallback; never a dead end.

The router walks this ladder on each validation failure, attaching the
prior worker's failure evidence to the next attempt.

## Approval requirements

- `<approval_tag>` — e.g. `publish`, `deployment`, `schema-approval`,
  `remote-tunnel-setup`, `secrets`, `continuous-listening`.

If this section is empty, the plan can execute without human approval.
If it is non-empty, the caller must collect approvals before invoking
the gated workers (Supabase, Vercel, GitHub publish, Claude Code
Windows, etc.).

## Validation plan

- hermes-local: confirm worker outputs match request
- hermes-local: run project test suite
- hermes-local: review git diff before publish
- <category-specific validation steps>

`hermes-local` always owns final validation. Worker-side checks (Codex
"--full-auto", Aider tests, etc.) are *intermediate*; they do not
substitute for Hermes' validation pass.

## Explanation

One short paragraph: primary worker, why it beat the alternatives,
which approvals are needed, and any context flag that changed the
outcome (offline mode, local-first preference, tunnel health).

## Ledger entry

```json
{
  "schema": "hermes.routing.decision.v1",
  "task_id": "<task_id>",
  "task_category": "<task_category>",
  "task_summary": "<one-line summary>",
  "selected": ["hermes-local", "<primary_worker_id>", "..."],
  "primary": "<primary_worker_id>",
  "fallback_plan": ["<worker_id>", "..."],
  "validator": "hermes-local",
  "publisher": "<github-publisher or null>",
  "rejected": {"<worker_id>": "<reason>"},
  "approval_requirements": ["<approval_tag>"],
  "registry_source": "<yaml | builtin | merged>",
  "created_at": 0.0
}
```

This block appends as one line to
`$HERMES_HOME/orchestrator/decision_ledger.jsonl`. The ledger is the
audit trail Hermes (and the user) can replay to understand why a
particular worker was picked at a particular time.

## How to use this report

1. Read the **Explanation** for the gist.
2. Verify the **Approval requirements** — if non-empty, collect those
   approvals before running anything destructive.
3. Run the **Primary** worker. On success, run the **Validation plan**.
4. On validation failure, walk the **Fallback plan** top-to-bottom,
   re-emitting this report at each step with the previous failure
   attached.
5. If the ladder is exhausted, Hermes writes a clear TODO and notifies
   the user via their preferred channel.
