# Local Orchestrator API

`hermes_cli.orchestrator_api` exposes M.U.S.E. orchestration jobs through
a small **local-only** FastAPI app. The Android cockpit, the Flutter
companion, the TUI, and any other on-device client drives the
orchestrator over plain HTTP/WebSocket without embedding M.U.S.E.' Python
internals.

> Companion doc: [websocket-events.md](./websocket-events.md) — the
> event vocabulary streamed on the WebSocket.

## Design constraints

* **Local-first.** The default bind is `127.0.0.1:8765`. Public binds
  are refused unless the operator opts in *and* sets a token.
* **Trusted-local token (optional).** A bearer token can be required on
  every HTTP request and on every WebSocket connect.
* **Loopback middleware.** Even if the OS routes a non-loopback
  connection to the listener, the middleware drops it with 403 unless
  `allow_public_bind=True` was set.
* **Process-local state.** One job store per process. The store is
  in-memory; persistent orchestration state lives with the worker that
  handed the job in.

## Running

```bash
# Loopback, no token (trusted local mode):
python -m hermes_cli.orchestrator_api

# Loopback, with a token (recommended even on a single-user box):
export HERMES_ORCHESTRATOR_API_TOKEN=$(openssl rand -hex 32)
python -m hermes_cli.orchestrator_api

# Programmatic:
from hermes_cli.orchestrator_api import run
run(host="127.0.0.1", port=8765, token="…")
```

A non-loopback bind is refused unless `allow_public_bind=True` **and**
`HERMES_ORCHESTRATOR_API_TOKEN` is set. Token comparison uses
`hmac.compare_digest`, so it is not timing-attackable.

## Authentication

When a token is configured:

* **HTTP:** every request must carry
  `Authorization: Bearer <token>`. `GET /health` is exempt so
  supervisors (systemd, Docker healthcheck) can probe without baking
  the token into their config.
* **WebSocket:** connect with `?token=<token>`. Missing or wrong
  tokens close the socket with code `4401` before accept.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/health` | Liveness + auth/bind self-report |
| `GET`  | `/jobs` | List every job in the store |
| `POST` | `/jobs` | Create a new job |
| `GET`  | `/jobs/{job_id}` | Full job snapshot |
| `GET`  | `/jobs/{job_id}/status` | Compact status (id / status / error) |
| `GET`  | `/jobs/{job_id}/artifacts` | Artifacts produced so far |
| `GET`  | `/jobs/{job_id}/logs` | Event log (history) |
| `POST` | `/jobs/{job_id}/approve` | Grant a pending approval |
| `POST` | `/jobs/{job_id}/reject` | Reject a pending approval |
| `POST` | `/jobs/{job_id}/resume` | Move a paused job back to running |
| `POST` | `/jobs/{job_id}/cancel` | Cancel a job (idempotent) |
| `POST` | `/jobs/{job_id}/validate` | Record a validation result |
| `POST` | `/jobs/{job_id}/publish-plan` | Stage a publish plan |
| `GET`  | `/workers` | Last known state of every worker |
| `GET`  | `/jobs/{job_id}/workers` | Workers attached to one job |
| `POST` | `/jobs/{job_id}/workers/{worker}` | Worker heartbeat / state update |
| `POST` | `/voice/intake` | Create a job from a voice transcript |
| `WS`   | `/jobs/{job_id}/events` | Live event stream (see other doc) |

### GET /health

```json
{
  "status": "ok",
  "service": "hermes-orchestrator-api",
  "version": "1.0.0",
  "auth_required": false,
  "public_bind": false
}
```

### GET /jobs

```json
{ "jobs": [ { ...job snapshot... } ] }
```

### POST /jobs

Request:

```json
{ "name": "build-docs", "spec": { "any": "object" } }
```

* `name` (required, non-empty string) — short title.
* `spec` (optional object) — opaque payload passed to the worker.

Returns `201` with the full job snapshot.

### GET /jobs/{job_id}

Full job snapshot:

```json
{
  "id": "…uuid…",
  "name": "build-docs",
  "spec": {…},
  "status": "running",
  "phase": "executing",
  "created_at": 1700000000.0,
  "updated_at": 1700000020.0,
  "evidence": {…},
  "artifacts": [],
  "workers": { "alice": {"state": "running", "progress": 0.4, "updated_at": …} },
  "approvals": [],
  "validation": null,
  "publish_plan": null,
  "error": null,
  "source": null
}
```

* `status` is the high-level lifecycle (`pending`, `running`,
  `validating`, `awaiting_approval`, `publish_ready`, `completed`,
  `failed`, `cancelled`).
* `phase` is the more granular phase (`intake`, `planning`,
  `executing`, `validating`, `awaiting_approval`, `publish_ready`,
  `completed`, `failed`, `cancelled`). Cockpits drive their progress
  indicator off this.
* `source` is set to `"voice"` for jobs created via `/voice/intake`.

### GET /jobs/{job_id}/status

```json
{ "id": "…", "status": "running", "updated_at": 1700000020.0, "error": null }
```

### GET /jobs/{job_id}/artifacts

```json
{ "id": "…", "artifacts": [ {...} ] }
```

### GET /jobs/{job_id}/logs

Query params:

* `since` (float, optional) — return only envelopes with `ts > since`.
* `limit` (int, optional) — return at most the last N envelopes.

```json
{
  "id": "…",
  "logs": [
    { "event": "job.created", "job_id": "…", "ts": …, "data": {…} },
    { "event": "phase.changed", "job_id": "…", "ts": …, "data": {...} }
  ]
}
```

Each envelope matches the shape documented in
[websocket-events.md](./websocket-events.md). A cockpit that wants to
poll instead of using the WebSocket can watch the latest `ts` and pass
it back as `since` on the next request.

### POST /jobs/{job_id}/approve

Body (all fields optional):

```json
{ "approval_id": "a1", "comment": "lgtm" }
```

If `approval_id` is omitted the oldest pending approval is granted.
Returns the updated job. Returns `409` if no pending approval exists.
The job moves to `status="running"` / `phase="executing"` and
`approval.granted` is emitted.

### POST /jobs/{job_id}/reject

Same body shape as `/approve`. Marks the approval rejected and the job
`status="failed"`. Emits `approval.rejected` then `job.failed`. The
optional `comment` field is also stored as `job.error`.

### POST /jobs/{job_id}/resume

No body. Sets `status="running"`, `phase="executing"`. Emits
`phase.changed` then `worker.started`. Returns `409` on terminal jobs
(`completed` / `failed` / `cancelled`).

### POST /jobs/{job_id}/cancel

Idempotent: cancelling an already-terminal job returns the same job
without error. Otherwise sets `status="cancelled"`, emits
`phase.changed` then `job.failed`.

### POST /jobs/{job_id}/validate

Body is the validation result object (free-form). Stored on
`job.validation`. Emits `phase.changed` (to `validating`) then
`validation.completed`. Returns `409` on terminal jobs.

### POST /jobs/{job_id}/publish-plan

Body is the publish plan object (free-form). Stored on
`job.publish_plan`. Emits `phase.changed` (to `publish_ready`) then
`publish.ready`. Returns `409` on terminal jobs.

### GET /workers

Aggregates worker state across every job:

```json
{
  "workers": [
    {
      "job_id": "…",
      "job_name": "build-docs",
      "worker": "alice",
      "state": "running",
      "progress": 0.4,
      "updated_at": 1700000020.0
    }
  ]
}
```

### GET /jobs/{job_id}/workers

```json
{ "id": "…", "workers": { "alice": {…}, "bob": {…} } }
```

### POST /jobs/{job_id}/workers/{worker}

Record a heartbeat or state change. Body:

```json
{
  "state": "running",
  "progress": 0.4,
  "note": "compiling",
  "reason": "…optional, used for blocked state…",
  "result": "…optional, used for done/completed state…"
}
```

Side effects by `state`:

* `running` → emits `worker.heartbeat`.
* `blocked` → emits `worker.blocked`.
* `done` / `completed` → emits `worker.completed`.

Any other value is recorded as-is without an event.

### POST /voice/intake

Create a job from a transcribed voice utterance.

Body:

```json
{
  "transcript": "Build the release notes for v1.4 and ship it",
  "name": "optional explicit title",
  "context": { "locale": "en-US", "device": "android" },
  "spec": { "priority": "high" }
}
```

Behaviour:

* `transcript` is required and must be a non-empty string.
* When `name` is omitted, the first ~8 words of the transcript become
  the title.
* The transcript is stored at `spec.transcript`. `context` (if given)
  goes to `spec.context`. Any keys in `spec` win over the auto-built
  ones.
* The new job's `source` is set to `"voice"`.

Returns `201` with the full job snapshot.

### WebSocket /jobs/{job_id}/events

See [websocket-events.md](./websocket-events.md) for the envelope
shape and the full event vocabulary.

## Error responses

| Status | When |
|---|---|
| `400` | Malformed payload (missing required field, wrong type). |
| `401` | Token required and missing/wrong. |
| `403` | Non-loopback client when `allow_public_bind=False`. |
| `404` | Unknown `job_id`. |
| `409` | Action invalid for current state (e.g. resume on cancelled). |
| `422` | FastAPI body validation (top-level non-object). |

All error bodies look like `{ "detail": "…" }` (or `{ "error": "…" }`
for the middleware-level 401/403 responses).
