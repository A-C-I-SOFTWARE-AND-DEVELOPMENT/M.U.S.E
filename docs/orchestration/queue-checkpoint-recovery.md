# Queue, checkpoints, and disconnect recovery

> **Status:** Phase 08. Implements the queue / checkpoint / recovery
> primitives used by the orchestrator daemon, the local API, and the
> Android cockpit.

M.U.S.E. orchestrates work that spans long-running workers, remote
tunnels, and unreliable phone networks. This page describes the three
modules that make that work survivable:

| Module                          | Owns                                              |
| ------------------------------- | ------------------------------------------------- |
| `hermes_cli/job_queue.py`       | `queue.json` — scheduling state, per-worker state |
| `hermes_cli/checkpoints.py`     | `checkpoints/<job-id>/*.json` — phase snapshots   |
| `hermes_cli/recovery.py`        | The recovery flow that ties the two together      |

These modules are **filesystem-only**. They never call the network,
never spawn workers, and never touch git directly except to read
read-only snapshot data (`git status`, `git rev-parse`, `git diff
--numstat`). That makes them safe to invoke from any context, including
unit tests and the local API.

## On-disk layout

```
<root>/                              # default: $PWD/.hermes-orchestrator
    queue.json                       # job queue (job_queue.py)
    jobs/<job-id>/                   # per-job job.json + worker dirs
    checkpoints/<job-id>/            # checkpoint snapshots
        <ts>-pre_implementation-*.json
        <ts>-pre_validation-*.json
        <ts>-pre_publish-*.json
    logs/<job-id>/                   # worker logs (existing)
        recovered/<ts>/              # snapshots taken at recovery time
```

`<root>` defaults to `$PWD/.hermes-orchestrator` but `HERMES_ORCHESTRATOR_HOME`
overrides it (the Android cockpit and Termux runtime set this).

## The queue

```python
from hermes_cli.job_queue import JobQueue, QueueState, WorkerStatus

queue = JobQueue()                     # uses $PWD/.hermes-orchestrator
queue.add_job("job-1", prompt="ship the healthz endpoint", mode="build")
queue.add_worker("job-1", "w1", role="builder", target_tool="codex")
queue.set_worker_status("job-1", "w1", WorkerStatus.RUNNING, heartbeat=True)
```

### Queue states

A queue entry has its own scheduling state, separate from the
controller's `JobState`. Job state describes the *work* (planning,
workers_running, scored, …); queue state describes *whether the work
should run now*.

| State           | Meaning                                                    |
| --------------- | ---------------------------------------------------------- |
| `queued`        | Ready for the dispatcher to claim.                         |
| `running`       | At least one worker is actively progressing.               |
| `paused`        | Human-requested pause.                                     |
| `blocked`       | System-requested pause (stale workers, etc).               |
| `disconnected`  | A remote worker tunnel dropped.                            |
| `completed`     | Terminal: all workers succeeded.                           |
| `failed`        | Terminal: dispatcher gave up.                              |
| `cancelled`     | Terminal: human cancelled.                                 |

### Per-worker state

```python
queue.add_worker("job-1", "w1", role="builder")
queue.set_worker_status("job-1", "w1", WorkerStatus.RUNNING, heartbeat=True)
queue.set_pending_worker_io("job-1", "w1", prompt="…", output="partial")
queue.mark_worker_disconnected("job-1", "w1", error="tunnel down")
queue.mark_worker_reconnected("job-1", "w1")
queue.retry_worker("job-1", "w1")
```

`pending_prompt` and `pending_output` are the key fields for survivable
disconnects: whatever was *in flight* when the tunnel dropped is
preserved verbatim, so when the worker reconnects the dispatcher
re-delivers the same prompt instead of re-deriving it (which could
produce a different prompt on a re-plan).

### Public API surface

| Method                         | Purpose                                       |
| ------------------------------ | --------------------------------------------- |
| `add_job`                      | Add a queue entry.                            |
| `list_jobs(state=…, states=…)` | Enumerate, optionally filtered.               |
| `get_job(id)`                  | Load one entry.                               |
| `pause_job(id)`                | Pause a non-terminal entry.                   |
| `resume_job(id)`               | Lift a paused / blocked / disconnected entry. |
| `cancel_job(id)`               | Terminal-cancel and mark live workers.        |
| `remove_job(id)`               | Hard delete the queue entry.                  |
| `set_state(id, state)`         | Force a state (used by recovery).             |
| `add_worker / set_worker_status` | Per-worker mutators.                        |
| `retry_worker(id, wid)`        | Reset a failed/disconnected/blocked worker.   |
| `mark_worker_disconnected`     | Cascade to entry if no other runners.         |
| `mark_worker_reconnected`      | Lift the entry out of `disconnected`.         |
| `set_pending_worker_io`        | Stash in-flight prompt/output.                |
| `set_phase_checkpoint`         | Pin the latest checkpoint id + phase.         |
| `mark_recovered`               | Stamp `recovered_at` for the publisher.       |

## Checkpoints

Checkpoints are tiny JSON snapshots taken at three safe points:

| Phase                  | Taken when                                       |
| ---------------------- | ------------------------------------------------ |
| `pre_implementation`   | Workers are about to start writing code.         |
| `pre_validation`       | Implementation is done; validators about to run. |
| `pre_publish`          | Validators passed; about to push/PR.             |

Each checkpoint captures:

- **Job phase + state** — what the controller thought was happening.
- **Worker statuses** — every worker's status and attempt count.
- **Approval state** — `none`, `pending`, `approved`, `rejected`.
- **Git snapshot** — branch, HEAD SHA, `status --porcelain`, and
  `diff --numstat` summary. Captured via subprocess; never raises on
  non-repo paths.

```python
from hermes_cli.checkpoints import CheckpointStore, CheckpointPhase

store = CheckpointStore()
cp = store.checkpoint_pre_validation(
    "job-1",
    repo_root="/srv/example",
    job_state="workers_complete",
    workers=[
        {"worker_id": "w1", "role": "builder", "status": "succeeded"},
    ],
)
```

The `CheckpointStore` exposes:

| Method                    | Purpose                                  |
| ------------------------- | ---------------------------------------- |
| `create_checkpoint`       | Generic snapshot.                        |
| `checkpoint_pre_*`        | Phase-specific helpers (clearer at use). |
| `list_checkpoints(id)`    | All checkpoints for a job, oldest-first. |
| `load_checkpoint`         | Read one back.                           |
| `latest(id)`              | The newest snapshot of any phase.        |
| `latest_for_phase(id, p)` | The newest snapshot for one phase.       |
| `latest_safe_phase(id)`   | The highest phase observed.              |
| `clear_job(id)`           | Drop every checkpoint for a job.         |
| `list_jobs()`             | Job IDs with at least one checkpoint.    |

### Why these three phases?

They are the **rollback points** for the worker pipeline:

- After `pre_implementation` and before `pre_validation`, the cost of
  re-running is one worker attempt. We checkpoint here so a Termux
  restart doesn't force a full re-plan.
- After `pre_validation` and before `pre_publish`, the cost of
  re-running is *much* higher (every validator runs again). We
  checkpoint so we can resume right at the publish gate.
- `pre_publish` is the final approval point. The publisher refuses to
  push a recovered job — see below.

## Recovery

```python
from hermes_cli.recovery import RecoveryManager

mgr = RecoveryManager.from_root()       # uses $PWD/.hermes-orchestrator
report = mgr.recover_all()              # walks every incomplete job
for jr in report.jobs:
    print(jr.job_id, jr.queue_state_after, jr.requires_approval)
```

### The five non-negotiables

1. **Never auto-publish after recovery.** Every `recover_job` call
   stamps `entry.recovered_at = <ts>`. The github publisher checks
   this and refuses to push without explicit human approval.
2. **Stale workers become blocked, not failed.** A worker that hasn't
   heartbeated within `DEFAULT_STALE_WORKER_SECONDS` (10m) is flipped
   to `WorkerStatus.BLOCKED`. The dispatcher will not silently
   re-run it.
3. **Failed and disconnected jobs are not silently re-queued.**
   Recovery leaves their queue state where it was. A `failed` job
   needs an explicit `retry_worker`; a `disconnected` job needs an
   explicit `mark_worker_reconnected` once the tunnel is back.
4. **Logs are preserved.** Every `recover_job` copies
   `logs/<job-id>/` into a timestamped `recovered/<ts>/` subfolder
   before any state is changed.
5. **The resume phase is the same as the last safe phase.** Recovery
   never silently advances. If the last checkpoint was
   `pre_validation`, the next attempt re-runs validation.

### `RecoveryReport`

`recover_all()` returns a `RecoveryReport` with one `JobRecoveryReport`
per processed job:

```json
{
  "started_at": 1700000000.0,
  "finished_at": 1700000001.0,
  "jobs": [
    {
      "job_id": "job-1",
      "queue_state_before": "running",
      "queue_state_after": "blocked",
      "last_safe_phase": "pre_validation",
      "resume_phase": "pre_validation",
      "requires_approval": true,
      "actions": [
        {"worker_id": "w1", "action": "stale_blocked",
         "reason": "last_heartbeat=… (>600s ago)"}
      ],
      "notes": ["…"]
    }
  ]
}
```

## Network disconnect — the full sequence

This is the canonical "Windows tunnel drops while Claude Code worker
is mid-flight" sequence:

```
1. Dispatcher polls worker w1                          → no response
2. queue.mark_worker_disconnected("job-1", "w1")
       w1.status     = DISCONNECTED
       entry.state   = DISCONNECTED   (no other runner)
3. Worker process on remote machine writes final output
   somewhere (e.g. resume token) — irrelevant to M.U.S.E..
4. Tunnel comes back.
5. Dispatcher detects w1 is reachable again.
6. queue.mark_worker_reconnected("job-1", "w1")
       w1.status     = PENDING        (or RUNNING if mid-replay)
       w1.last_heartbeat = now
       entry.state   = QUEUED
7. Dispatcher re-delivers w1.pending_prompt verbatim;
   resumes processing from where w1.pending_output left off.
```

The key invariant: between steps 2 and 6 there is *zero* loss of
prompt or output state. Both fields live in `queue.json`, which
survives M.U.S.E. / Termux / phone restarts.

## Mobile app recovery

The Android cockpit and any other client can query the queue and
trigger a resume through two helpers in `hermes_cli.recovery`:

```python
from hermes_cli.recovery import query_queue_state, resume_job_by_id

view   = query_queue_state(root=HERMES_ORCHESTRATOR_HOME)
report = resume_job_by_id("job-1", root=HERMES_ORCHESTRATOR_HOME)
```

These are also wired into the local API:

| Method | Path                       | Returns                |
| ------ | -------------------------- | ---------------------- |
| GET    | `/queue`                   | `query_queue_state()`  |
| POST   | `/queue/<job-id>/resume`   | `resume_job_by_id()`   |

Both calls are cheap (one `queue.json` read each). The cockpit can
poll the GET freely; the POST is gated on a human tap.

## Operational pointers

- **Queue is corrupt:** `JobQueueError("queue.json is corrupt …")` is
  raised on every read. Move the file aside, restart the orchestrator,
  and replay from per-job `jobs/<id>/job.json`.
- **Checkpoint files unreadable:** `list_checkpoints` skips them with
  a warning; `load_checkpoint` raises `CheckpointError`. Recovery uses
  `list_checkpoints`, so a single bad file does not derail the whole
  flow.
- **Schema version newer than build:** `JobQueueError("schema version
  X is newer than this build")`. Upgrade hermes-agent before
  continuing — the queue refuses to load instead of silently
  truncating fields.
- **Test isolation:** every module accepts `root=` for direct injection;
  the tests run against a `tmp_path` and never touch
  `~/.hermes-orchestrator/`.
