# Parallel workers and git worktrees

Phase 12 of the M.U.S.E. local orchestrator adds two narrow capabilities:

1. A **parallel runner** that takes an execution plan of workers and
   runs them sequentially or with bounded concurrency, capturing logs
   and writing an auditable `status.json`.
2. **Worktree isolation** so that concurrent workers don't stomp on
   each other's working tree.

Both live entirely on the user's machine. Nothing here pushes, force-
pushes, deletes branches without explicit confirmation, or otherwise
mutates remote state.

## Modules

| Module                                  | Responsibility                                  |
|-----------------------------------------|-------------------------------------------------|
| `hermes_cli/orchestrator_parallel.py`   | Plan validation, runner, cancellation, status. |
| `hermes_cli/worktrees.py`               | `git worktree` lifecycle + sidecar metadata.   |

## On-disk layout

Everything the runner writes lives under
`<repo>/.hermes-orchestrator/`. A repo-local `git/info/exclude` entry is
added automatically the first time a worktree is created, so the
orchestrator's own state never makes the host repo appear dirty.

```
<repo>/.hermes-orchestrator/
├── jobs/
│   └── <job-id>/
│       ├── status.json              # snapshot of every worker state
│       ├── cancel.requested         # drop this file to cancel the job
│       └── <worker-id>/
│           ├── prompt.txt           # rendered prompt (if any)
│           ├── handoff.json         # for handoff-required workers
│           ├── stdout.log           # for local-run workers
│           └── stderr.log
└── worktrees/
    └── <job-id>/
        ├── <worker-id>.worktree.json   # sidecar metadata
        └── <worker-id>/                 # the working tree itself
            └── ...checkout of branch hermes/<job-id>/<worker-id>...
```

`<job-id>` and `<worker-id>` are sanitized down to `[A-Za-z0-9_.-]`
before they hit either the filesystem or a branch name.

## Execution modes

```python
class ExecutionMode(str, Enum):
    PROMPT_ONLY      = "prompt-only"
    HANDOFF_REQUIRED = "handoff-required"
    LOCAL_RUN        = "local-run"
```

| Mode               | What the runner does                                                      |
|--------------------|---------------------------------------------------------------------------|
| `prompt-only`      | Writes `prompt.txt` and marks the worker `completed`. No external action. |
| `handoff-required` | Writes `prompt.txt` + `handoff.json` and marks the worker `awaiting-handoff`. The user (or another agent) is expected to act on the handoff. |
| `local-run`        | `subprocess.Popen`s the worker's `command` with the given `cwd`/`env`, streaming stdout/stderr to log files. Honors `timeout_seconds` and the `cancel.requested` flag. |

The runner never opens external apps, never executes web links, and
never calls a provider API on the user's behalf. `handoff-required`
exists specifically so the dashboard can hand work off to the user
without the runner doing it itself.

## Worker plan

```python
WorkerPlan(
    worker_id="w1",
    profile="researcher",
    mode=ExecutionMode.LOCAL_RUN,
    command=["python", "-c", "..."],   # required for LOCAL_RUN
    prompt="What to do",                # optional, persisted to prompt.txt
    cwd=None,                            # defaults to worktree path or repo
    env={"FOO": "bar"},                  # merged on top of os.environ
    timeout_seconds=600,
    handoff={"target": "chatgpt"},       # required for HANDOFF_REQUIRED
    use_worktree=False,                  # opt-in per worker
)
```

`WorkerPlan.validate()` rejects:
- empty `worker_id` or `profile`
- `local-run` without a `command`
- `local-run` whose joined command contains an obvious destructive
  token: `git push`, `git push --force`, `git push -f`,
  `git reset --hard`, `rm -rf /`
- `handoff-required` without a `handoff` payload
- `timeout_seconds <= 0`

## Execution plan

```python
ExecutionPlan(
    job_id="job-1",
    workers=[...],
    concurrency=2,           # default 2; max 8
    use_worktrees=False,     # opt-in at the plan level
    base_ref=None,           # which ref worktrees branch off (default HEAD)
    allow_dirty=False,       # refuse to create worktrees off a dirty repo
)
```

Default concurrency is intentionally low (`DEFAULT_CONCURRENCY = 2`),
and the validator caps it at `MAX_CONCURRENCY = 8`. Duplicate
`worker_id`s within a plan are rejected.

## Running

```python
from pathlib import Path
from hermes_cli.orchestrator_parallel import (
    ExecutionMode, ExecutionPlan, ParallelRunner, WorkerPlan,
)

plan = ExecutionPlan(
    job_id="research-2026-05-23",
    workers=[
        WorkerPlan(
            worker_id="market-scan",
            profile="researcher",
            mode=ExecutionMode.PROMPT_ONLY,
            prompt="Find competitors for X.",
        ),
        WorkerPlan(
            worker_id="local-bench",
            profile="bench",
            mode=ExecutionMode.LOCAL_RUN,
            command=["pytest", "-q"],
            timeout_seconds=300,
            use_worktree=True,
        ),
    ],
    concurrency=2,
    use_worktrees=True,
)

runner = ParallelRunner(Path.cwd(), plan)
statuses = runner.run()
```

After `run()` returns, `<repo>/.hermes-orchestrator/jobs/<job-id>/status.json`
contains a serialized snapshot of every worker:

```json
{
  "job_id": "research-2026-05-23",
  "created_at": "2026-05-23T19:00:00Z",
  "updated_at": "2026-05-23T19:00:14Z",
  "concurrency": 2,
  "use_worktrees": true,
  "workers": [
    {
      "worker_id": "market-scan",
      "profile": "researcher",
      "mode": "prompt-only",
      "state": "completed",
      "started_at": "2026-05-23T19:00:00Z",
      "ended_at":   "2026-05-23T19:00:00Z",
      "prompt_path": ".../jobs/.../market-scan/prompt.txt",
      ...
    },
    ...
  ]
}
```

## Cancellation

There are two equivalent ways to ask the runner to stop:

1. **In-process** — call `runner.request_cancel()` from another thread.
2. **Out-of-process** — drop the `cancel.requested` flag file with
   `orchestrator_parallel.request_cancel(repo, job_id)`. The runner
   polls for this file at `poll_interval` and propagates the request to
   every in-flight worker.

Workers that have not yet started transition to `cancelled` without
running. Workers in `local-run` get `SIGTERM` (then `SIGKILL` after a
2s grace period if they didn't exit) and end up in the `cancelled`
state. Workers already in `completed` / `failed` / `timed-out` are
left as-is.

## Worktree lifecycle

```python
from hermes_cli import worktrees as wt

info = wt.create_worktree(
    repo,
    job_id="research-2026-05-23",
    worker_id="local-bench",
    base_ref="main",          # default: HEAD
    allow_dirty=False,         # default: refuse to proceed if dirty
    extra_metadata={"profile": "bench"},
)
# info.path   = <repo>/.hermes-orchestrator/worktrees/research-2026-05-23/local-bench
# info.branch = hermes/research-2026-05-23/local-bench
```

`create_worktree` will refuse to:

- run against a non-git directory
- run against a dirty repo unless `allow_dirty=True`
- reuse a worktree path that already exists on disk
- reuse a branch that already exists in the repo
- branch off a `base_ref` git cannot resolve

It will NOT:

- delete branches
- force-create branches (no `-B`/`--force`)
- push anything anywhere
- modify any tracked file (it only writes to
  `.git/info/exclude` and to `.hermes-orchestrator/`)

### Inspecting

`wt.list_worktrees(repo)` returns every Hermes-managed worktree by
reading the sidecar `<worker>.worktree.json` files.
`wt.iter_worktrees_for_job(repo, job_id)` narrows that to a single job.

### Cleanup (destructive — opt-in only)

```python
# default: no-op, returns False
wt.cleanup_worktree(repo, job_id="...", worker_id="...")

# opt-in: removes the worktree path and the sidecar metadata
wt.cleanup_worktree(repo, job_id="...", worker_id="...", confirm=True)

# opt-in: also drops the branch (safe form: `git branch -d`, not -D)
wt.cleanup_worktree(
    repo, job_id="...", worker_id="...",
    confirm=True, delete_branch=True,
)
```

Or, to clean up every worktree under a job in one go:

```python
from hermes_cli.orchestrator_parallel import cleanup_job_worktrees

cleanup_job_worktrees(
    repo, job_id="...",
    confirm_destructive=True,
    delete_branches=False,
)
```

Branch deletion uses `git branch -d` — the non-force form. A branch
with unmerged commits stays put and the operation fails loudly, by
design.

## Safety summary

| Risk                                  | Mitigation                                                  |
|---------------------------------------|-------------------------------------------------------------|
| Pushing to a remote                   | The module's `_run_git` helper explicitly refuses `push`.   |
| Rewriting history                     | `_run_git` refuses `reset`, `rebase`, `clean`.              |
| Force-creating branches               | `git worktree add -b` (not `-B`) — collisions fail.         |
| Leaking state into user's repo        | `.hermes-orchestrator/` is added to `.git/info/exclude`.    |
| Running destructive shell commands    | `WorkerPlan.validate` refuses obvious footguns.             |
| Unbounded parallelism                 | `DEFAULT_CONCURRENCY = 2`, hard cap `MAX_CONCURRENCY = 8`.  |
| Silent deletion of worktrees/branches | `confirm=True` required; default is no-op.                  |
| Runaway workers                       | `timeout_seconds` per worker + `SIGTERM`→`SIGKILL`.         |
| Stuck cancellation                    | `cancel.requested` flag file polled out-of-process.         |

## Validation

```bash
python -m py_compile hermes_cli/orchestrator_parallel.py hermes_cli/worktrees.py
python -m pytest tests/test_parallel_orchestration.py tests/test_worktrees.py -q
```
