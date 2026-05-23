---
name: recover-job
description: "Diagnose and recover Hermes orchestrator jobs after a phone restart, Termux restart, Windows tunnel drop, or partial worker failure. Walks the queue + checkpoints, marks stale workers, never auto-publishes."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows, android]
metadata:
  hermes:
    tags: [orchestration, recovery, queue, checkpoints, disconnect, resilience]
    related_skills:
      - hermes-orchestration-pipeline
      - decision-quality-gate
      - local-quality-gate
---

# Recover Job

Use this skill when an orchestrator job is in any of these states:

- **Running but silent** — no heartbeat in 10+ minutes.
- **Disconnected** — a remote worker tunnel dropped mid-flight.
- **Paused / blocked** — needs a human decision to resume.
- **Failed** — needs an explicit retry choice.
- **After a hard restart** — phone, Termux, the laptop, the tunnel.

Recovery is implemented in `hermes_cli/recovery.py` (with
`hermes_cli/job_queue.py` and `hermes_cli/checkpoints.py` underneath).
The skill below is the operator playbook — what to actually do.

## Non-negotiables

Before doing anything, internalize these:

1. **Never auto-publish a recovered job.** The publisher refuses to
   push when `entry.recovered_at != 0`. Your job is to surface the
   facts so a human can approve, not to advance the pipeline.
2. **Preserve logs first, mutate state second.** `RecoveryManager`
   copies `logs/<job-id>/` into `logs/<job-id>/recovered/<ts>/` before
   any queue write. Do not delete logs.
3. **Stale ≠ failed.** A worker that has not heartbeated for >10
   minutes is `blocked`, not `failed`. It may resume cleanly once the
   tunnel is back; do not mark it as failed pre-emptively.
4. **Resume from the last safe phase.** If the latest checkpoint is
   `pre_validation`, the resume target is `pre_validation` — recovery
   re-runs that phase. Do not "skip ahead" by hand.

## Decision tree

```
queue entry state
├── queued              → nothing to recover (just hasn't started)
├── running             → run recover_job(); usually returns "blocked"
│                         with stale_blocked actions
├── paused              → confirm with human; resume_job() if approved
├── blocked             → inspect actions[] to see why; fix root cause
│                         before resume_job()
├── disconnected        → wait for tunnel; mark_worker_reconnected()
│                         once worker is reachable
├── failed              → diagnose; retry_worker() per worker
├── completed           → no action
└── cancelled           → no action
```

## Step-by-step

### 1. Snapshot the situation

```bash
# Show every incomplete entry as JSON
python -c '
from hermes_cli.recovery import query_queue_state
import json, os
root = os.environ.get("HERMES_ORCHESTRATOR_HOME")
print(json.dumps(query_queue_state(root=root), indent=2))
'
```

Capture the output before doing anything else. If the recovery goes
sideways, this is the only ground-truth you'll have.

### 2. Walk the queue

```python
from hermes_cli.recovery import RecoveryManager

mgr = RecoveryManager.from_root()
report = mgr.recover_all()
for jr in report.jobs:
    print(f"{jr.job_id:30}  before={jr.queue_state_before:12}  "
          f"after={jr.queue_state_after:12}  "
          f"resume_phase={jr.resume_phase}")
    for action in jr.actions:
        print(f"    {action.action:24}  {action.worker_id}  {action.reason}")
    for note in jr.notes:
        print(f"    note: {note}")
```

Read every line. Recovery may have:

- **Blocked stale workers** (`action=stale_blocked`) — confirm with
  the user whether to retry them or investigate the upstream
  (network? worker process crashed? prompt too big?).
- **Retained disconnected workers** (`action=disconnected_retained`)
  — the worker's `pending_prompt` and `pending_output` are still in
  `queue.json`. Re-delivery happens automatically on reconnect.
- **Left the entry as `blocked`** — there are workers still in
  `blocked` / `disconnected` status. Don't `resume_job` until you've
  decided what to do with each.

### 3. Decide and act, one job at a time

For each job in the report:

```python
from hermes_cli.job_queue import JobQueue, WorkerStatus

queue = JobQueue()
entry = queue.get_job("job-1")
for w in entry.workers:
    print(w.worker_id, w.status, w.attempts, w.last_error)
```

Then:

- **Worker stuck in `blocked` because of staleness:** if you and the
  user agree the worker has genuinely crashed, call
  `queue.retry_worker("job-1", "w1")`. This increments
  `attempts` and resets the worker to `pending`.
- **Worker in `disconnected`:** wait for the tunnel. When it comes
  back, the dispatcher calls `mark_worker_reconnected` automatically
  — you usually don't need to do it by hand.
- **Worker `failed` with a real error:** read `last_error`. If it's
  a bug in the prompt, fix the prompt with `write_worker_prompt` on
  the JobController and *then* `retry_worker`. If it's a real bug in
  the code under test, escalate to the human.

### 4. Resume

Once every worker is in a sane state:

```python
queue.resume_job("job-1", note="user reviewed recovery report")
```

The queue entry flips back to `queued` and the dispatcher picks it
up on the next tick. **The `recovered_at` stamp stays set** — the
publisher will still demand approval at the publish gate.

### 5. Approve the publish

When the job reaches `pre_publish` again, *manually* approve. The
publisher reads `entry.recovered_at` and refuses to push without a
fresh human OK, even if the prior approval was already on file.

## Mobile cockpit flow

The Android cockpit exposes the same primitives:

| Tap                 | Hermes call                             |
| ------------------- | --------------------------------------- |
| "Resume"            | `POST /queue/<id>/resume`               |
| "Pause"             | `POST /queue/<id>/pause`                |
| "Cancel"            | `POST /queue/<id>/cancel`               |
| "Retry worker"      | `POST /queue/<id>/workers/<wid>/retry`  |

If the user is operating from the cockpit, do **not** also mutate
the queue from a shell on the laptop — concurrent writers can race.
Pick one driver and stick with it for the duration of the recovery.

## Anti-patterns

- ❌ Calling `queue.set_state("...", "completed")` to "close out" a
  ghost job. Use `cancel_job`; the publisher checks for completed
  artifacts and a leftover `completed` entry without artifacts will
  confuse anyone reading the queue later.
- ❌ Deleting `queue.json` to "start fresh". The per-job folders
  under `jobs/<id>/` still exist and the orchestrator will rebuild a
  queue from them on next start, but without the heartbeat /
  disconnect history.
- ❌ Editing checkpoint JSON files by hand. Recovery treats missing
  files as "no checkpoint" but treats malformed files as warning
  events — your edit will land in the logs.
- ❌ Calling `clear_job` on the checkpoint store before the recovery
  report has been captured. You lose the "last safe phase" signal.

## See also

- `docs/orchestration/queue-checkpoint-recovery.md` — module reference.
- `docs/orchestration/troubleshooting.md` — broader failure-pattern
  catalogue.
- `tests/test_recovery.py` — worked examples of every flow above.
