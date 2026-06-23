# Validation, Testing, Monitoring

Phase 15 closes the loop between *making changes* and *publishing
them*. Three concerns share one filesystem-native pipeline:

1. **Validation** — `hermes_cli.validation.ValidationRunner` decides
   whether the current workspace is safe to publish. The publish gate
   stays **closed** if any critical check fails. See
   [`local-validation-gates.md`](local-validation-gates.md) for the
   policy and check matrix.
2. **Testing** — the same runner discovers test suites
   (`python.pytest`, `node.tests`, `gradle.test`) and runs them when
   the operator passes `allow_expensive=True`. Tests are *one*
   validator among many — they do not bypass the gate, and a clean
   `pytest` does not imply a green publish.
3. **Monitoring** — `hermes_cli.monitoring.MonitoringHub` watches
   jobs, workers, the remote tunnel, the remote queue, the last
   validation result, and an optional app-health probe. It writes a
   rolling event log plus a snapshot file that the gateway / CLI can
   render.

Both modules are read-mostly, dependency-light, and intentionally
boring: they never call out to the network, never spawn jobs, never
mutate user data. They just observe what the rest of the system has
written to disk and tell the user what is going on.

## Pipeline at a glance

```text
                   ┌────────────────────────────┐
   editor / agent  │ commits, jobs, workers …   │
   ─────────────►  │ write to the workspace     │
                   └──────────────┬─────────────┘
                                  │
                                  ▼
   ┌──────────────────────────────────────────────────┐
   │ ValidationRunner.run()                           │
   │   safe + (optionally) expensive + remote checks  │
   │   writes validation/results.json + summary.md    │
   │   publish_allowed = no critical fail             │
   └──────────────┬─────────────────────┬────────────┘
                  │                     │
        publish ◄─┘ (gate)              │
                                        ▼
                       ┌─────────────────────────────────────┐
                       │ MonitoringHub.snapshot()            │
                       │   jobs · workers · tunnel · queue · │
                       │   validation · app health           │
                       │   writes monitoring/health.json     │
                       │   appends to monitoring/events.jsonl│
                       └──────────────────┬──────────────────┘
                                          │
                                          ▼
                                  gateway / CLI render
```

## Validation gates

The full matrix lives in
[`local-validation-gates.md`](local-validation-gates.md). The
Phase 15 additions extend the matrix with a **remote** category that
fires only when the workspace has a `remote/` directory.

| Trigger                       | Checks added            |
|-------------------------------|-------------------------|
| `remote/tunnel.json`          | `remote.tunnel`         |
| `remote/workers/`             | `remote.workers`        |
| `remote/queue.json`           | `remote.queue`          |

### `remote.tunnel`

Reads `remote/tunnel.json` (an object) and inspects the `state` field.

| `state` (any case)                                | Result |
|---------------------------------------------------|--------|
| `up`, `open`, `healthy`, `connected`, `ready`     | `pass` |
| `down`, `closed`, `error`, `failed`               | `warn` |
| anything else (or missing)                        | `warn` |
| file unparseable                                  | `fail` |

The check is **not critical** — a flaky tunnel must not block a
local commit. Snapshots and the dashboard surface it; the operator
decides whether to act.

Example payload:

```json
{
  "state": "up",
  "url": "https://hermes-tunnel-7c2.example.dev",
  "started_at": 1747948800.0
}
```

### `remote.workers`

Walks `remote/workers/**/heartbeat.json`. Each file is expected to
carry a unix `timestamp` (other accepted keys: `heartbeat`,
`updated_at`). Heartbeats newer than `REMOTE_WORKER_STALE_S`
(5 minutes by default) count as **fresh**; older ones are
**stale**.

| Outcome                       | Result                         |
|-------------------------------|--------------------------------|
| every heartbeat fresh         | `pass`                         |
| any heartbeat stale or absent | `warn` (count surfaced)        |
| no heartbeat files            | `skipped`                      |

Not critical — a stale heartbeat is observability, not a publish
blocker.

### `remote.queue`

Reads `remote/queue.json` as either a bare list of jobs or
`{"jobs": [...]}`. Each job may carry `enqueued_at` /
`created_at`. The runner reports:

* `depth` — number of jobs
* `oldest_age_s` — age of the oldest pending job

If the oldest job exceeds `REMOTE_QUEUE_STALE_S` (30 minutes), the
check returns `warn`. Parse errors return `fail`. Neither blocks
publish.

### Filtering

The new category integrates with the existing filter flags:

```bash
# only remote checks
python -m hermes_cli.validation --workspace . --only remote

# skip remote checks
python -m hermes_cli.validation --workspace . --skip remote
```

## Monitoring hub

`MonitoringHub` is a small read-only aggregator. Its only job is to
take what the rest of muse has written to disk and produce one
human-readable snapshot plus an append-only event log.

### Sources

| Path                                        | Purpose                          |
|---------------------------------------------|----------------------------------|
| `jobs/<id>/job.json`                        | local job state, stall detection |
| `workers/<id>/status.json`                  | local worker heartbeats          |
| `remote/tunnel.json`                        | tunnel state                     |
| `remote/workers/<id>/heartbeat.json`        | remote worker heartbeats         |
| `remote/queue.json`                         | pending remote job queue         |
| `validation/results.json`                   | last validation pass             |
| `health/app.json` *(optional)*              | external app/backend probe       |

Missing sources never crash the hub — they show up as
`present: false` in the snapshot and produce no alerts.

### Snapshot shape

```python
from hermes_cli.monitoring import MonitoringHub

hub = MonitoringHub(workspace=".")
snap = hub.snapshot()
print(snap.jobs["by_status"])
print(snap.alerts)
```

`snap.to_dict()` mirrors the JSON written to
`monitoring/health.json`:

```json
{
  "workspace": "/abs/path",
  "generated_at": 1747948800.5,
  "jobs": {
    "total": 4,
    "by_status": {"running": 1, "done": 2, "failed": 1},
    "failed": [{"id": "j-3", "status": "failed", "path": "j-3"}],
    "stalled": [],
    "recent": [...]
  },
  "local_workers":  { "fresh": 2, "stale": [], "workers": [...] },
  "remote_tunnel":  { "state": "up", "url": "...", "present": true },
  "remote_workers": { "fresh": 1, "stale": [], "workers": [...] },
  "remote_queue":   { "depth": 0, "oldest_age_s": null, "present": true },
  "validation":     { "publish_allowed": true, "blocking_failures": [], ... },
  "app_health":     { "state": "healthy", "present": true, ... },
  "alerts": [
    { "severity": "error",
      "source":   "jobs",
      "message":  "job j-3 failed",
      "detail":   {...} }
  ]
}
```

### Event log

`MonitoringHub.record(event)` appends one JSON line per event to
`monitoring/events.jsonl`. Producers (orchestrator, workers,
gateway) call this when something interesting happens. The hub
itself records one rollup event per `snapshot()` so the log doubles
as a snapshot history.

Standard event kinds (see `EVENT_*` constants):

| Kind                 | Producer                            |
|----------------------|-------------------------------------|
| `job.state`          | orchestrator on job transitions     |
| `worker.heartbeat`   | local + remote workers              |
| `remote.tunnel`      | tunnel daemon on state changes      |
| `remote.worker`      | remote worker bootstrap / shutdown  |
| `remote.queue`       | queue mutator (enqueue / dequeue)   |
| `validation.result`  | end of each `ValidationRunner.run`  |
| `app.health`         | optional external probe             |
| `alert`              | the hub itself (rollup per snapshot)|

`severity` is one of `info`, `warn`, `error`. The hub's rollup
event carries the maximum severity across all alerts in the
snapshot so a single `grep` against the log lights up the worst
state the system has been in.

### Alert rules

The hub does not decide *what to do* when something is wrong — it
just builds an `alerts` list the renderer can show. Today's rules:

| Rule                                           | Severity |
|------------------------------------------------|----------|
| job status `failed` / `error`                  | `error`  |
| job `running` / `in_progress` with no update for `JOB_STALL_S` | `warn` |
| local worker stale (`status.json` heartbeat too old) | `warn` |
| remote worker stale                            | `warn`   |
| remote tunnel state ∈ {down, closed, error, failed} | `error` |
| remote tunnel state ∉ {up, open, healthy, …}   | `warn`   |
| remote queue parse error                       | `error`  |
| remote queue oldest job > 30 minutes           | `warn`   |
| `validation/results.json` has `publish_allowed: false` | `error` |
| `health/app.json` state ∈ {down, error, unhealthy, failed} | `error` |
| `health/app.json` state ∈ {degraded, warning}  | `warn`   |

Anything not in the table simply does not generate an alert.

## Output contracts

### `validation/`

| File              | Contents                                                     |
|-------------------|--------------------------------------------------------------|
| `results.json`    | machine-readable list of check records + `publish_allowed`   |
| `summary.md`      | Markdown table the agent can drop into a PR or chat reply    |
| `commands.log`    | literal shell commands the runner executed                   |

### `monitoring/`

| File              | Contents                                                     |
|-------------------|--------------------------------------------------------------|
| `events.jsonl`    | append-only audit log, one event per line                    |
| `health.json`     | last snapshot written by `MonitoringHub.snapshot()`          |

Both directories are added to `.gitignore` by convention so the
artefacts of the gate / hub don't bleed into commits.

## Integration touch points

* **CLI** — `hermes_cli/orchestrator.py` invokes the validator
  before exporting a job folder or opening a PR, and surfaces
  `summary.md` to the user. The slash command surface keeps
  monitoring out of band: `/orchestrator status` reads from
  `monitoring/health.json`, not from a live process.
* **Workers** — local and remote workers call
  `MonitoringHub.record()` on lifecycle transitions. The hub does
  not require them — they may also simply update their own
  `status.json` / `heartbeat.json` files and let the scanners pick
  the change up on the next snapshot.
* **Gateway** — the gateway surfaces `alerts` from the latest
  snapshot. It does not invent its own alerting layer; if a new
  signal needs to be surfaced, add it to the hub and the gateway
  picks it up automatically.

## Testing

Two pytest modules cover the Phase 15 surface end-to-end:

* `tests/test_validation_gates.py` — the Phase 14 validator
  invariants (still required to pass).
* `tests/test_validation.py` — the Phase 15 additions
  (`remote.tunnel` / `remote.workers` / `remote.queue`,
  filtering, artefact shape).
* `tests/test_monitoring.py` — every `MonitoringHub` source
  scanner, event-log round-tripping, alert rules, snapshot shape.

To run only the Phase 15 tests:

```bash
python -m pytest tests/test_validation.py tests/test_monitoring.py -q
```

To compile-check the modules in isolation (matches the
`ValidationRunner` smoke step):

```bash
python -m py_compile hermes_cli/validation.py hermes_cli/monitoring.py
```

## What this loop does NOT do

* It does not push, force-push, or rewrite git history.
* It does not open tunnels, enqueue jobs, or start workers.
* It does not run an alerting daemon — the gateway polls.
* It does not bypass `allow_expensive=False` on expensive
  validators "just to be safe".
* It does not auto-fix anything it discovers. Repair belongs in
  a different skill, invoked by the user.

If any of those are needed, add them as a separate module —
this pipeline stays read-mostly on purpose.
