# Orchestrator Command Roadmap (Phase 7)

> Status: **design / pre-implementation**. The slash commands listed
> here are *future* surface. They are not registered in
> `hermes_cli/main.py` or the gateway dispatcher yet. This document
> exists so reviewers can agree on the names, arguments, and
> behavior before any of them ship.

The muse CLI already exposes a handful of slash commands (e.g.
`/help`, `/model`) and the kanban surface adds more. Phase 7 adds a
small, focused set scoped to the Job Controller and its supporting
machinery.

## 1. Command summary

| Command                              | Purpose                                                                                                |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| `/orchestrate <prompt>`              | Start a new orchestration job from a single prompt.                                                    |
| `/orchestrator status [job-id]`      | Show the state of one job (with `job-id`) or all recent jobs.                                          |
| `/orchestrator open <job-id>`        | Open the job's working directory and print the prepared command for each candidate worker.            |
| `/orchestrator resume <job-id>`      | Resume a `WAITING` or `FAILED` job from where it stopped.                                              |
| `/orchestrator publish <job-id>`     | Publish a chosen worker's artifact bundle (branch / patch / diff).                                     |
| `/ai-radar update`                   | Refresh the cached per-tool capability table the model router reads.                                   |
| `/model-router explain <prompt>`     | Show why the router would pick a given ordered list of workers for `<prompt>`.                         |
| `/decision-ledger show [job-id]`     | Print the append-only decision ledger for one job, or the most recent job if `job-id` is omitted.      |
| `/best-coding-tool-mission status`   | Show the long-running per-tool scoreboard used by the AI Radar and model router.                       |

## 2. `/orchestrate <prompt>`

Starts a new job.

- **Arguments:** the rest of the line is the prompt verbatim.
- **Behavior:**
  1. Persist a new `Job` (state `NEW`).
  2. Echo a one-paragraph plan-of-record, including the ordered
     worker candidates the model router has chosen.
  3. Move to `PLANNED`, then `DISPATCHED`.
  4. Run candidates sequentially until one succeeds or the list is
     exhausted. Each `WorkerRun` is recorded in the ledger.
  5. Land in `WAITING` (success) or `FAILED` (no candidate
     succeeded).
- **Output to user:** the job id, the plan-of-record, and a final
  one-line status. Verbose output stays in the per-run logs.
- **Non-goals:** does not auto-publish, does not auto-merge, does
  not autonomously retry beyond each adapter's own bounded retry.

## 3. `/orchestrator status [job-id]`

Read-only.

- With `job-id`: print the job's current state, the workers it has
  tried, their exit statuses, and the location of the ledger.
- Without `job-id`: print a table of the most recent N jobs (default
  N = 10).
- Never mutates state. Safe to alias to `/status` in environments
  that have already taken `/orchestrate ` as a prefix.

## 4. `/orchestrator open <job-id>`

Surfaces the prepared handoff so the user can inspect or run a worker
manually.

- Prints the absolute path to the job directory.
- For each candidate worker, prints the result of
  `WorkerAdapter.prepare(job)`: argv, cwd, env diff vs. the user's
  current shell, and any preflight notes.
- Optionally opens the directory in the OS file browser (only if
  `--open` is passed explicitly). Default is print-only — no side
  effects.

## 5. `/orchestrator resume <job-id>`

Re-enters a `WAITING` or `FAILED` job.

- If `WAITING`: re-runs the *next* untried candidate, if any.
- If `FAILED`: re-runs the *last* failed candidate (one retry) or,
  if that already happened, surfaces an error explaining why the
  resume is a no-op.
- Resume is the only way to retry from inside the controller; the
  model router does not auto-retry across jobs.

## 6. `/orchestrator publish <job-id>`

Publishes the artifact bundle from a chosen run.

- **Required confirmation:** if more than one run succeeded the
  command refuses to act and asks the user to pick one with
  `/orchestrator publish <job-id> --run <run-id>`.
- **What "publish" means:** apply the bundle's diff or patch to the
  user's working tree, or create the branch the adapter prepared.
  *Never* pushes to a remote on its own — pushing is left to the
  user's normal git workflow.
- This is the one command in the set that can mutate the working
  tree, and it requires an explicit job id. The decision is
  recorded in the ledger with `actor: user`.

## 7. `/ai-radar update`

Refreshes the AI Radar cache.

- Walks every adapter under `hermes_cli/workers/` and calls
  `available()`.
- Persists the results to
  `${HERMES_HOME}/orchestrator/ai_radar.json`.
- Idempotent. Safe to run on a cold cache or right after a tool
  upgrade.
- Does *not* call any provider API. The radar only records what is
  installed and what each adapter advertises in its
  `capabilities` set.

## 8. `/model-router explain <prompt>`

Dry-run the router. Useful for debugging the routing logic without
spending tokens.

- Tokenizes `<prompt>`, asks the router for its candidate list, and
  prints each candidate with the score and the matching capability
  tags.
- Marks unavailable workers (per the AI Radar cache) explicitly.
- Pure function — no job is created, no run is started, no ledger
  entry is written.

## 9. `/decision-ledger show [job-id]`

Pretty-prints the append-only ledger for one job.

- Each entry includes: timestamp, actor (`user` / `controller` /
  adapter name), event (`plan`, `dispatch`, `succeed`, `fail`,
  `cancel`, `publish`, `note`), and a short message.
- Output is plain text and trivially `grep`-able. The raw JSONL
  lives at
  `${HERMES_HOME}/orchestrator/jobs/<job-id>/ledger.jsonl`.

## 10. `/best-coding-tool-mission status`

The "scoreboard" view. Aggregates the per-tool success / failure /
publish counts across all jobs to give the user (and the router) a
running sense of which tools earn their keep.

- Read-only.
- Counts come from the decision ledger; there is no separate
  database.
- Shows last update timestamp and a one-line note per tool.
- The model router consults this scoreboard as a *tiebreaker*, not
  a primary signal — capabilities and availability still come
  first.

## 11. Registration plan

These commands are not yet wired in. When they ship the registration
will follow the existing slash-command pattern in
`hermes_cli/main.py` (the same place `/help`, `/model`, and similar
are registered). Each command will dispatch into the controller
module described in
[`docs/orchestration/job-controller-roadmap.md`](./job-controller-roadmap.md)
via a small function exposed by `hermes_cli/orchestrator.py`.

The first PR after this roadmap should wire only `/orchestrate`,
`/orchestrator status`, and `/decision-ledger show` — the minimum
slice that lets a user run a job and inspect the result. The rest
land in follow-up PRs once we have early users on the basic path.

## 12. Out of scope

- Cron-driven orchestrate jobs.
- Web/UI surfacing in the kanban dashboard.
- Cross-job memory or learning (beyond the AI Radar cache).
- Telemetry / analytics. muse does not collect any.
