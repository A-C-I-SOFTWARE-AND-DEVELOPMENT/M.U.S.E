# Job Controller Roadmap (Phase 7)

> Status: **design / pre-implementation**. This document describes the
> next layer of M.U.S.E. orchestration. Nothing here is wired into the
> production CLI yet. The Python skeletons in `hermes_cli/orchestrator.py`
> and `hermes_cli/workers/` are intentionally inert — they import cleanly,
> raise `NotImplementedError` for any unfinished method, and have no
> side effects on import.

## 1. Motivation

M.U.S.E. already has the right *primitives* for orchestration:

- Skills (`skills/`) describe how to delegate to external coding agents
  (Claude Code, Codex, Aider, Goose, etc.).
- The Android local orchestrator (`docs/hermes-local-orchestrator.md`)
  defines a hand-off model where M.U.S.E. prepares a structured prompt
  and the user routes it to whichever paid CLI they already use.
- The Enterprise Council (`skills/enterprise-council/`) shows a working
  pattern for plan-of-record + dispatch + judge + audit.
- Kanban (`hermes_cli/kanban*.py`) gives us a persistent task store and
  swimlane model.

What is missing is a **first-class Job Controller** that ties these
pieces together as a single, scriptable surface. Today, "run this
prompt against Claude Code, then Codex, then Aider, and let me compare"
requires the user to drive three separate skills by hand or write a
bespoke batch script. Phase 7 turns that workflow into a M.U.S.E.
command: `/orchestrate <prompt>` produces a *Job*, dispatches one or
more *WorkerRuns*, records every step in a *Decision Ledger*, and
exposes a small set of follow-up commands.

## 2. Vocabulary

| Term            | Meaning                                                                                                                            |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Job             | One user intent (`/orchestrate <prompt>`). Has a stable `job_id`, a prompt, a plan, and one or more `WorkerRun`s.                  |
| WorkerRun       | One execution of one worker adapter against one Job. Has a `run_id`, `worker` name, status, start/end times, and an output bundle. |
| Worker adapter  | A Python module under `hermes_cli/workers/` that knows how to hand a prompt off to a specific external tool.                       |
| Plan-of-record  | A short, user-visible paragraph describing what the controller is about to do. Borrowed from the Enterprise Council pattern.       |
| Decision ledger | An append-only JSON log of every controller decision (worker selection, retry, escalation, publish).                               |
| AI Radar        | The cached per-tool capability table the model router consults when picking workers. Refreshed via `/ai-radar update`.             |
| Model router    | Function that maps a prompt + constraints to an ordered list of worker candidates. Explainable via `/model-router explain`.        |

## 3. High-level architecture

```
                ┌─────────────────────────┐
                │  /orchestrate <prompt>  │  (slash command, see
                └────────────┬────────────┘   orchestrator-command-roadmap.md)
                             │
                             ▼
                ┌─────────────────────────┐
                │   JobController.start   │
                │                         │
                │  - assign job_id        │
                │  - persist Job          │
                │  - emit plan-of-record  │
                └────────────┬────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  ModelRouter.choose_workers  │
              │  (reads AI Radar cache)      │
              └────────────┬─────────────────┘
                           │ ordered list of worker names
                           ▼
              ┌──────────────────────────────┐
              │  for worker in candidates:   │
              │    adapter = load(worker)    │
              │    run = adapter.run(job)    │
              │    ledger.record(run)        │
              └────────────┬─────────────────┘
                           │
                           ▼
              ┌──────────────────────────────┐
              │  Judge / compare / publish   │
              │  (only on explicit user      │
              │   action via /orchestrator   │
              │   publish <job-id>)          │
              └──────────────────────────────┘
```

The controller is **not** an autonomous agent. By default it stops
after dispatch and waits for the user to inspect, resume, or publish.
"YOLO" mode is left for a later phase and is out of scope here.

## 4. Job lifecycle

```
NEW  ─► PLANNED  ─► DISPATCHED  ─► WAITING  ─► COMPLETED
                         │              │
                         │              └─► FAILED
                         └─► CANCELLED
```

| State        | Entry condition                                                          | Allowed user actions                                                          |
| ------------ | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| `NEW`        | `/orchestrate` invoked, job persisted, plan not yet emitted.             | wait                                                                          |
| `PLANNED`    | Plan-of-record echoed; workers chosen; nothing dispatched yet.           | `/orchestrator open`, `/orchestrator status`                                  |
| `DISPATCHED` | At least one `WorkerRun` started.                                        | `/orchestrator status`, `/orchestrator open`                                  |
| `WAITING`    | All `WorkerRun`s finished; awaiting user inspection.                     | `/orchestrator open`, `/orchestrator resume`, `/orchestrator publish`         |
| `COMPLETED`  | User explicitly published (or marked done) one of the worker outputs.    | `/orchestrator status` (read-only)                                            |
| `FAILED`     | All workers reported a hard failure and the controller gave up retrying. | `/orchestrator resume`, `/orchestrator open`                                  |
| `CANCELLED`  | User aborted before completion.                                          | `/orchestrator status` (read-only)                                            |

Transitions are recorded in the decision ledger with a timestamp,
the actor (`user` or `controller`), and a free-text reason.

## 5. Storage layout

Under `${HERMES_HOME:-~/.hermes}/orchestrator/`:

```
orchestrator/
  jobs.json                # index: job_id -> summary
  jobs/
    <job_id>/
      job.json             # prompt, plan, state, timestamps
      ledger.jsonl         # append-only decision ledger
      runs/
        <run_id>/
          run.json         # worker, status, exit info
          stdout.log
          stderr.log
          artifacts/       # optional diff, patch, file dump
```

This mirrors the kanban / batch-runner layout already used by the
codebase (one directory per logical unit, JSONL for append-only logs).
No new top-level config keys are introduced in this phase.

## 6. Failure model

The controller never deletes or rewrites a worker's output. If a
worker fails:

1. The controller records the failure in the ledger with the worker's
   exit code, captured stdout/stderr tail, and any structured error
   payload the adapter surfaced.
2. If the model router has another candidate and the user has not
   asked to stop, the controller advances to the next candidate.
3. If the router runs out of candidates, the job lands in `FAILED`
   and surfaces a one-line summary plus the ledger path.

Retries are **bounded** (default 1 retry per worker, configurable per
adapter). There is no exponential-backoff loop and no "kick until it
passes" behavior — those belong to the worker's own CLI, not to the
controller.

## 7. Security and safety

- **No external calls on import.** Every adapter is lazy: its
  `available()` probe is the only function that may touch the
  filesystem or PATH, and even that is optional.
- **No credential brokering.** The controller follows the same rule
  as the Android orchestrator: it never reads cookies, never extracts
  tokens, never automates a hidden login. If a worker needs an API
  key the user supplies it through the worker's own mechanism.
- **No destructive operations by default.** Publishing (`/orchestrator
  publish <job-id>`) is the only command that may mutate a working
  tree or push to a remote, and it requires an explicit run id.
- **Audit trail.** Every controller decision is appended to the
  ledger. The `/decision-ledger show` command reads — never writes —
  the ledger.

## 8. Open questions

These are deliberately left open for the next design pass:

1. **Concurrency.** Should we ever dispatch two workers in parallel
   for the same job? The current design is strictly sequential.
2. **Cross-job memory.** Should the AI Radar learn from each job's
   outcome automatically, or only via an explicit
   `/best-coding-tool-mission status` review?
3. **Plugin packaging.** Worker adapters live under `hermes_cli/workers/`
   for now. Long-term they may become discoverable plugins under
   `plugins/`, the way `github_assistant` already does.
4. **Web surface.** The kanban dashboard could grow a Jobs tab.
   Out of scope for this roadmap.

## 9. Phase 7 deliverables (this PR)

- This document (`job-controller-roadmap.md`).
- `worker-adapter-interface.md` — formal contract every adapter must
  satisfy.
- `orchestrator-command-roadmap.md` — slash command surface.
- Inert Python skeletons:
  - `hermes_cli/orchestrator.py`
  - `hermes_cli/workers/__init__.py`
  - `hermes_cli/workers/base.py`
  - `hermes_cli/workers/hermes_local.py`
  - `hermes_cli/workers/codex.py`
  - `hermes_cli/workers/claude_code.py`
  - `hermes_cli/workers/aider.py`
  - `hermes_cli/workers/goose.py`
  - `hermes_cli/workers/chatgpt_handoff.py`

Each skeleton imports cleanly, has type hints and docstrings, raises
`NotImplementedError` for unfinished methods, and is **not** wired into
`hermes_cli/main.py` yet. The wiring lands in a later PR after the
adapter contracts have been reviewed.
