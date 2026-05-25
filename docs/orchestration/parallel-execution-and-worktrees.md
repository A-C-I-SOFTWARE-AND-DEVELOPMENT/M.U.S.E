# Phase 13 — Parallel execution & worktree isolation

Phase 13 hardens the parallel-execution stack with two
production-readiness features:

1. **`remote-run` execution mode** with explicit **approval gating**
   so privileged or off-machine actions never dispatch by default.
2. **Resume semantics** so a partially completed job can be re-run
   without re-doing finished work.

It builds on the Phase 12 primitives — the
[`worktrees`](../../hermes_cli/worktrees.py) module ships the
git-worktree lifecycle and the
[`parallel_runner`](../../hermes_cli/parallel_runner.py) module is the
Phase 13 successor to `orchestrator_parallel.py`.

See also: [`parallel-workers-and-worktrees.md`](parallel-workers-and-worktrees.md)
for the Phase 12 baseline.

---

## Modules

| Module                              | Responsibility                                                       |
|-------------------------------------|----------------------------------------------------------------------|
| `hermes_cli/parallel_runner.py`     | Plan, runner, approval gating, resume, status persistence.           |
| `hermes_cli/worktrees.py`           | `git worktree` lifecycle + sidecar metadata + dirty-repo detection. |

## On-disk layout

Everything the runner writes lives under
`<repo>/.hermes-orchestrator/`. A repo-local `.git/info/exclude` entry
is added automatically the first time a worktree is created, so the
orchestrator's own state never makes the host repo appear dirty.

```text
<repo>/.hermes-orchestrator/
├── jobs/
│   └── <job-id>/
│       ├── status.json              # snapshot of every worker state
│       ├── cancel.requested         # drop this file to cancel the job
│       └── <worker-id>/
│           ├── prompt.txt           # rendered prompt (if any)
│           ├── handoff.json         # for handoff-required workers
│           ├── stdout.log           # for local-run / remote-run
│           └── stderr.log
└── worktrees/
    └── <job-id>/
        ├── <worker-id>/             # the actual git worktree
        └── <worker-id>.worktree.json # sidecar metadata
```

## Execution plan

An `ExecutionPlan` describes one job:

```python
from pathlib import Path

from hermes_cli.parallel_runner import (
    ApprovalState,
    ExecutionMode,
    ExecutionPlan,
    ParallelRunner,
    WorkerPlan,
)

plan = ExecutionPlan(
    job_id="phase-13-demo",
    workers=[
        WorkerPlan(
            worker_id="researcher",
            profile="researcher",
            mode=ExecutionMode.PROMPT_ONLY,
            prompt="Find prior art on X.",
        ),
        WorkerPlan(
            worker_id="aider-fixer",
            profile="aider",
            mode=ExecutionMode.LOCAL_RUN,
            command=["aider", "--message", "fix flaky test"],
            timeout_seconds=600,
            use_worktree=True,
        ),
        WorkerPlan(
            worker_id="deploy-bot",
            profile="deployer",
            mode=ExecutionMode.REMOTE_RUN,
            command=["bash", "-c", "./scripts/deploy.sh staging"],
            timeout_seconds=300,
        ),
    ],
    concurrency=2,
    use_worktrees=True,
    approval_state=ApprovalState.PENDING,
    description="Phase-13 demo job",
)

runner = ParallelRunner(Path("."), plan)
statuses = runner.run()
```

### Fields

| Field             | Type              | Notes                                                    |
|-------------------|-------------------|----------------------------------------------------------|
| `job_id`          | `str`             | Sanitized into branch / path segments.                   |
| `workers`         | `Sequence[WorkerPlan]` | Must be non-empty and have unique IDs.              |
| `concurrency`     | `int`             | `1..MAX_CONCURRENCY` (8).                                |
| `use_worktrees`   | `bool`            | When `True`, workers with `use_worktree=True` get one.   |
| `base_ref`        | `str?`            | The branch / commit each worktree forks off (default `HEAD`). |
| `allow_dirty`     | `bool`            | When `False` (default), refuses to start on a dirty repo. |
| `approval_state`  | `ApprovalState`   | `pending` / `approved` / `rejected`. Gates `remote-run`. |
| `description`     | `str`             | Persisted into `status.json` for human auditing.         |

## Execution modes

| Mode                       | What the runner does                                                              |
|----------------------------|-----------------------------------------------------------------------------------|
| `prompt-only`              | Renders the prompt to `prompt.txt` and marks the worker `completed`.              |
| `handoff-required`         | Writes `handoff.json`; the worker becomes `awaiting-handoff` for a human to act.  |
| `local-run`                | Spawns `command` on this machine. Captures stdout/stderr to `*.log`.              |
| `remote-run`               | Same as `local-run` BUT refuses unless `approval_state` is `approved`.            |

A `remote-run` worker on a `pending` or `rejected` plan is recorded as
`blocked-by-approval` — no subprocess is spawned, no log files are
created, and the runner moves on.

## Worker states

```text
                 ┌────────────────────────────────────────────────────┐
                 │                                                    │
                 ▼                                                    │
   pending ──► running ─┬──► completed                                │
                        ├──► failed ──────────────────► (resume re-runs)
                        ├──► timed-out ──────────────► (resume re-runs)
                        └──► cancelled ─── terminal
   pending ──► awaiting-handoff ── terminal
   pending ──► blocked-by-approval ─ terminal until approval flips
   pending ──► (resume) ──► skipped-resumed ── terminal
```

`completed`, `awaiting-handoff`, `cancelled`, `skipped-resumed`, and
`blocked-by-approval` are all considered terminal for resume purposes.
`failed`, `timed-out`, and any `running`/`pending` leftover gets
re-dispatched when the runner is constructed with `resume=True`.

## Approval gating

`approval_state` is the single switch that decides whether
`remote-run` workers may dispatch. The plan defaults to
`ApprovalState.PENDING`. To approve:

```python
approved = plan.with_approval(ApprovalState.APPROVED)
ParallelRunner(repo, approved).run()
```

`with_approval` returns a new plan; the original is unchanged so the
"who approved this" decision is captured explicitly at the call site.

A plan that contains zero `remote-run` workers is unaffected — the
gate only applies to that mode.

## Cancellation

Two equally-valid mechanisms:

```python
# In-process — fastest path for the same Python program.
runner.request_cancel()

# Cross-process — drop a flag file. The runner polls for it.
from hermes_cli.parallel_runner import request_cancel
request_cancel(repo, "phase-13-demo")
```

Either path:

1. Sets the in-process cancel event.
2. Writes `cancel.requested` under the job dir.
3. The runner notices on its next poll (`poll_interval`, default 0.5s),
   sends `SIGTERM` then `SIGKILL` to any running subprocess, and marks
   the worker `cancelled`.

Cancellation is **non-destructive**: worktrees, log files, prompts,
and `status.json` all stay on disk so a human can audit what happened.

## Resume

Re-running the same plan with `resume=True` reads the existing
`status.json` and:

- Skips workers whose prior state was `completed`, `awaiting-handoff`,
  `cancelled`, or `skipped-resumed` — they move to `skipped-resumed`.
- Re-dispatches workers in `failed`, `timed-out`, `pending`, or
  `running` (interrupted) state, bumping their `attempt` counter so
  the audit trail records retries.
- Re-uses existing worktrees rather than re-creating them.

```python
ParallelRunner(repo, plan, resume=True).run()
```

If there's no prior `status.json`, `resume=True` is a no-op fresh run.

## Safety invariants

The runner is hardened against the most common footguns:

1. **No `git push`**, no `git push --force`, no `git push -f`.
2. **No `git reset --hard`**, no `git clean -fd`.
3. **No `rm -rf /`** or `rm -rf ~` tokens in command strings.
4. **No fork-bomb** tokens.

The full list lives in
[`parallel_runner.FORBIDDEN_COMMAND_TOKENS`](../../hermes_cli/parallel_runner.py).
Any `local-run` or `remote-run` worker whose command contains one of
these substrings fails `WorkerPlan.validate()` with a
`RunnerError` — long before any subprocess is launched.

Additional invariants enforced by the worktree layer:

- `create_worktree` refuses to run on a dirty repo unless
  `allow_dirty=True` is passed explicitly.
- `create_worktree` refuses to recycle an existing branch name.
- `cleanup_worktree` is a no-op unless called with `confirm=True`.
- `_run_git` refuses `push`, `reset`, `clean`, `rebase` outright.

And at the runner level:

- `remote-run` only runs when `approval_state is APPROVED`.
- `concurrency` is capped at 8.
- `timeout_seconds` is capped at 24 hours.

## Audit trail

`status.json` is rewritten on every state transition. The schema:

```json
{
  "job_id": "phase-13-demo",
  "created_at": "2026-05-23T12:34:56Z",
  "updated_at": "2026-05-23T12:35:01Z",
  "concurrency": 2,
  "use_worktrees": true,
  "approval_state": "approved",
  "description": "Phase-13 demo job",
  "workers": [
    {
      "worker_id": "aider-fixer",
      "profile": "aider",
      "mode": "local-run",
      "state": "completed",
      "started_at": "2026-05-23T12:34:57Z",
      "ended_at":   "2026-05-23T12:35:00Z",
      "return_code": 0,
      "error": null,
      "stdout_path": ".hermes-orchestrator/jobs/phase-13-demo/aider-fixer/stdout.log",
      "stderr_path": ".hermes-orchestrator/jobs/phase-13-demo/aider-fixer/stderr.log",
      "worktree_path": ".hermes-orchestrator/worktrees/phase-13-demo/aider-fixer",
      "branch": "hermes/phase-13-demo/aider-fixer",
      "handoff_path": null,
      "prompt_path":  ".hermes-orchestrator/jobs/phase-13-demo/aider-fixer/prompt.txt",
      "attempt": 1
    }
  ]
}
```

`attempt` increments by one each time the worker is re-dispatched via
`resume=True`, so the ledger always reflects how many tries the work
took.

## Testing

- `tests/test_parallel_runner.py` — plan validation, modes, approval
  gating, concurrency, cancellation, resume, worktree integration,
  persistence.
- `tests/test_worktrees.py` — worktree lifecycle, dirty-repo detection,
  cleanup safety.

```bash
python -m py_compile hermes_cli/parallel_runner.py hermes_cli/worktrees.py
python -m pytest tests/test_parallel_runner.py tests/test_worktrees.py -q
```
