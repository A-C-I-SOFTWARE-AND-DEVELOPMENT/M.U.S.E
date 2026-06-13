# Orchestrator WebSocket Event Stream

Live event stream for one orchestration job:

```
ws://127.0.0.1:8765/jobs/{job_id}/events
```

Token-protected when the server is run with
`HERMES_ORCHESTRATOR_API_TOKEN` set — connect with
`?token=<token>`.

See [local-orchestrator-api.md](./local-orchestrator-api.md) for the
HTTP surface that this stream complements.

## Connect lifecycle

1. Client opens the WebSocket. If the token is wrong (or the request
   is non-loopback while public bind is off) the server closes the
   socket with code `4401` before accepting.
2. If the job id is unknown the server closes with code `4404`.
3. Otherwise the server `accept()`s and immediately **replays** every
   envelope buffered for the job. A late subscriber therefore sees the
   `job.created` envelope it would otherwise have missed.
4. Live envelopes follow as they happen.

The server reads (and discards) any frames the client sends — that
makes disconnects surface promptly.

## Envelope shape

Every message is a JSON object with the same four keys:

```json
{
  "event": "phase.changed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "ts": 1700000020.0,
  "data": { "from": "intake", "to": "executing", "reason": "resume" }
}
```

* `event` — one of the constants below.
* `job_id` — the path-matching job id.
* `ts` — server `time.time()` at publish.
* `data` — event-specific payload (always an object, possibly empty).

The shape is stable; add new keys before renaming the existing ones.

## Event vocabulary

The canonical list lives in
[`hermes_cli/orchestrator_events.py`](../../hermes_cli/orchestrator_events.py)
as the `ALL_EVENTS` tuple. Import the constants from that module
rather than hard-coding strings in Python clients.

### Lifecycle

| Event | When | Notable `data` keys |
|---|---|---|
| `job.created` | A new job was inserted into the store. | `name`, `spec` |
| `job.failed`  | Terminal failure (also emitted on cancel and on reject). | `reason` |
| `phase.changed` | The job moved from one phase to another. | `from`, `to`, `reason` |
| `error` | Non-terminal error worth surfacing to the cockpit. | `message`, `fatal`, `detail` |

`phase.changed.data.from` may be `null` when the previous phase was
implicit (e.g. straight after `job.created`).

### Approvals

| Event | When | Notable `data` keys |
|---|---|---|
| `approval.requested` | A worker is asking for human approval. | `kind`, `summary`, `payload`, optional `id` |
| `approval.granted`   | `POST /jobs/{id}/approve` succeeded. | `approval_id`, `comment` |
| `approval.rejected`  | `POST /jobs/{id}/reject` succeeded. | `approval_id`, `comment` |

A `kind` field discriminates approval types (`"publish"`,
`"destructive"`, `"manual"`, …) so the cockpit can pick the right UI.

### Workers

| Event | When | Notable `data` keys |
|---|---|---|
| `worker.started`   | A worker started or resumed on this job. | `reason`, optional `worker` |
| `worker.heartbeat` | Periodic liveness ping + progress. | `worker`, `progress`, `note` |
| `worker.blocked`   | Worker stalled and needs intervention. | `worker`, `reason` |
| `worker.completed` | Worker finished its slice of work. | `worker`, `result` |

### Cost

| Event | When | Notable `data` keys |
|---|---|---|
| `cost.accumulated` | One model-call delta folded into the job's cost meter (`JobStore.accumulate_cost`). Event-sourced so restart-replay rebuilds the meter. | `usage` (token buckets), `cost_usd`, `model`, `provider` |

Heartbeats are emitted by the API when a client POSTs
`/jobs/{id}/workers/{worker}` with `state="running"`. Cockpits should
treat a missing heartbeat for N seconds as "worker silent" rather than
"worker dead" — the worker may simply be busy.

### Evidence / scoring

| Event | When | Notable `data` keys |
|---|---|---|
| `evidence.updated`   | Worker added evidence to the job's bundle. | free-form |
| `scoring.completed`  | A scoring pass finished. | `score`, `summary` |

### Validation / publish

| Event | When | Notable `data` keys |
|---|---|---|
| `validation.completed` | A validation gate ran. | `result` |
| `publish.ready`        | The publish plan is staged. | `plan` |

## Phases

`phase.changed.data.to` is drawn from the `ALL_PHASES` tuple in
`orchestrator_events`:

* `intake` — initial state when the job lands.
* `planning` — the job is being decomposed into a task graph.
* `executing` — workers are doing the work.
* `validating` — a validation pass is running.
* `awaiting_approval` — paused waiting for a human gate.
* `publish_ready` — a publish plan is staged.
* `completed` — terminal success.
* `failed` — terminal failure.
* `cancelled` — terminal cancel.

## Backpressure & dropped events

Each subscriber gets a bounded queue (256 envelopes by default). If a
slow subscriber lets it fill, new envelopes for *that* subscriber are
dropped with a warning rather than blocking the fan-out for everyone.
The dropped envelopes are still reflected in `GET /jobs/{id}/logs`, so
the cockpit can recover state by polling logs and the job snapshot
after a disconnect.

The history buffer the WS replays on connect is also bounded (256
envelopes per job in the broker), but the per-job `events` list on
the job snapshot is unbounded — clients that need full history should
fetch `GET /jobs/{id}/logs`.

## Close codes

| Code | Meaning |
|---|---|
| `1000` | Normal close (client initiated). |
| `4401` | Authentication required or wrong token. |
| `4404` | Unknown `job_id`. |

## Client example

```python
import asyncio
import json
import websockets

async def watch(job_id: str, token: str = ""):
    url = f"ws://127.0.0.1:8765/jobs/{job_id}/events"
    if token:
        url += f"?token={token}"
    async with websockets.connect(url) as ws:
        async for raw in ws:
            env = json.loads(raw)
            print(env["event"], env["data"])

asyncio.run(watch("…job-id…"))
```

```dart
// Flutter cockpit (sketch)
final ws = WebSocketChannel.connect(
  Uri.parse('ws://127.0.0.1:8765/jobs/$jobId/events?token=$token'),
);
ws.stream.listen((raw) {
  final env = jsonDecode(raw);
  bus.dispatch(env['event'], env['data']);
});
```
