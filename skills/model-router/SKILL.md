---
name: model-router
description: "Decide which orchestration worker (hermes-local, claude-code, codex-cli) should receive a given job. Phase-02-aware: workers are scaffolded as folders only, not yet dispatched."
version: 0.2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [orchestration, routing, workers, dispatch]
    related_skills:
      - hermes-orchestration-pipeline
      - github-publisher
      - developer-ux-command-center
---

# Model router

This skill picks the right worker for a job in the Hermes orchestration
pipeline. It mirrors the worker list in `scripts/hermes-orchestrate.sh`.

## Phase-02 reality check

In Phase 02, **no worker is actually dispatched**. The script creates
`workers/hermes-local/`, `workers/claude-code/`, and
`workers/codex-cli/` for every job, each with `prompt.md`, `output.md`,
`patch.diff`, and `status.json` (state `not_started`). Routing
decisions made now are recorded in `decision-ledger.md` and consumed by
the controller that runs in a later phase.

Do not pretend a worker ran. If you find yourself reasoning about a
worker's output in Phase 02, you are ahead of the implementation.

## Worker roster

| Worker         | Strength                                        | Typical modes              | Notes |
|----------------|-------------------------------------------------|----------------------------|-------|
| `hermes-local` | Local reasoning, tool use through the gateway   | `audit`, `plan`, `review`  | Always available; the default fallback. No external account required. |
| `claude-code`  | Long-context code edits, careful patches        | `build`, `debug`, `review` | Requires the user to have Claude Code installed and logged in. |
| `codex-cli`    | Fast iteration, language-light scaffolding      | `build`, `debug`           | Requires the user to have Codex / ChatGPT CLI installed and logged in. |

The roster is hard-coded in the `WORKERS` array in
`scripts/hermes-orchestrate.sh`. To add or remove a worker, edit:

1. The `WORKERS` array in the script.
2. The roster section in
   `docs/orchestration/hermes-orchestration-pipeline.md`.
3. This table.

Out-of-sync rosters silently produce jobs that the controller cannot
dispatch — keep all three locations aligned.

## Routing rules

1. **Always include `hermes-local`.** It is the only worker guaranteed
   to be present. If the user has neither external CLI installed, the
   job runs hermes-local only and the council reduces to one voice.
2. **Add `claude-code` whenever the mission produces a code patch**
   (`mode` is `build`, `debug`, or `review` for a code change). Claude
   Code is the strongest patch writer in the roster.
3. **Add `codex-cli` for breadth on `build` and `debug`** when the
   user wants a second opinion against `claude-code`. Council review
   then has two patch writers to compare. Skip it for pure `audit`,
   `plan`, or `review` modes where a second patch buys nothing.
4. **Never route to a worker the user has not opted into.** Phase 02
   scaffolds all three folders unconditionally because the cost is a
   few empty files; the controller in the next phase reads the user's
   config and demotes missing workers to `state: "skipped"` instead
   of dispatching them.
5. **Record the routing decision in `decision-ledger.md`** before
   running. One row per dispatched worker, plus one row per skipped
   worker with the reason.

## Mode-to-worker quick reference

| Mode     | Default fan-out                              |
|----------|----------------------------------------------|
| `plan`   | `hermes-local`                               |
| `audit`  | `hermes-local`                               |
| `build`  | `hermes-local` + `claude-code` (+ `codex-cli` for second patch) |
| `debug`  | `hermes-local` + `claude-code`               |
| `review` | `hermes-local` + `claude-code`               |
| `publish`| `hermes-local` only                          |

`publish` is intentionally narrow — it only promotes already-merged
artifacts to a branch + PR draft via the `github-publisher` skill, so
there is nothing for a second worker to add.

## Failure modes worth flagging

- **Phantom worker output.** If `workers/<worker>/output.md` has
  content but `status.json` says `not_started`, someone wrote to the
  folder out-of-band. Trust the status file, not the prose.
- **Empty roster.** If every worker is skipped, abort the job and tell
  the user — there is nothing to dispatch. Do not silently emit empty
  merge artifacts.
- **Mode/router mismatch.** `mode=publish` with `claude-code` routed
  means someone overrode the defaults; surface it in the ledger so the
  next reviewer notices.
