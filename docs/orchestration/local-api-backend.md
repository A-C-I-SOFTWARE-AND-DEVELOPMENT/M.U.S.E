# Local Orchestrator API Backend

> **Which backend does the Android cockpit use?** The shipped APK talks to
> the **cockpit gateway** (`gateway/cockpit/`, routes `/v1/cockpit/...`,
> `muse cockpit serve`), *not* the `hermes_cli.orchestrator_api` app
> documented below. The cockpit gateway's `jobs_list` merges JobQueue +
> orchestrator jobs and serves the job control + detail surface
> (`/jobs/{id}/ledger|pause|resume|rerun|approve|diff|validate`) the
> mobile Jobs cockpit drives. See
> [`../android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md)
> §4. `orchestrator_api` (below) remains a parallel, FastAPI-based
> control plane for the TUI and other local clients.

`hermes_cli.orchestrator_api` exposes muse orchestration jobs through a
small local-only FastAPI app. The Android APK, the TUI, and any other
on-device client can drive the orchestrator over plain HTTP/WebSocket
without embedding muse' Python internals.

This is **not** a public service. It is a control plane for a single
user, intentionally scoped to the loopback interface.

## Threat model

The orchestrator API has full authority over muse jobs: it can start,
cancel, validate, and publish work on the user's behalf. Any process
that can reach the bind address gets that authority. The defaults are
chosen so the only such process is one running on the same machine as
the user.

| Surface | Default | Hardened mode |
|---|---|---|
| Bind address | `127.0.0.1` | unchanged |
| Token | optional (off) | `HERMES_ORCHESTRATOR_API_TOKEN=...` |
| Public bind | refused | explicit `--insecure` + token |
| Loopback enforcement | middleware rejects non-loopback peers | disabled only when public bind is opted into |

The middleware enforces loopback even if the operating system happened
to route an outside connection to the listener. Token comparison uses
`hmac.compare_digest` so it is not timing-attackable. `/health` is
exempt from token auth so supervisors (systemd, Docker healthcheck) can
probe without baking the token into their config — `/health` carries no
job state.

## Running the API

```bash
# Loopback, no token (trusted local mode):
python -m hermes_cli.main orchestrator-api

# Loopback, with a token (recommended even on a single-user box):
export HERMES_ORCHESTRATOR_API_TOKEN=$(openssl rand -hex 32)
python -m hermes_cli.main orchestrator-api

# Programmatic:
from hermes_cli.orchestrator_api import run
run(host="127.0.0.1", port=8765, token="…")
```

A non-loopback bind is refused unless the caller passes
`allow_public_bind=True` **and** sets a token. Don't do that on a
multi-user machine.

## REST endpoints

All endpoints return JSON. When a token is configured every request
must carry `Authorization: Bearer <token>`. WebSocket clients pass
`?token=<token>` because browser WS clients can't set headers on the
upgrade.

| Method | Path | Description |
|---|---|---|
| GET    | `/health`                          | Liveness probe. Always reachable. |
| GET    | `/jobs`                            | List jobs. |
| POST   | `/jobs`                            | Create a job (`{name, spec}`). |
| GET    | `/jobs/{job_id}`                   | Full job snapshot. |
| GET    | `/jobs/{job_id}/status`            | Compact status (`id`, `status`, `updated_at`, `error`). |
| GET    | `/jobs/{job_id}/artifacts`         | List artifacts attached to a job. |
| POST   | `/jobs/{job_id}/resume`            | Mark a paused/blocked job as `running` and emit `worker.started`. |
| POST   | `/jobs/{job_id}/cancel`            | Cancel a job. Idempotent on already-terminal jobs. |
| POST   | `/jobs/{job_id}/validate`          | Attach a validation report; emits `validation.completed`. |
| POST   | `/jobs/{job_id}/publish-plan`      | Stage a publish plan; emits `publish.ready`. |
| WS     | `/jobs/{job_id}/events`            | Real-time event stream (see below). |

`POST /jobs` body:

```json
{
  "name": "build-docs",
  "spec": {"target": "site"}
}
```

`spec` may be any JSON object — the API stores it verbatim and hands it
back to whichever worker is consuming the job.

## WebSocket events

`/jobs/{job_id}/events` accepts a single subscriber and streams JSON
envelopes:

```json
{"event": "worker.started", "job_id": "…", "ts": 1736020000.1, "data": {…}}
```

On connect the server replays every event in the job's history so a
late client never misses `job.created`.

The full event vocabulary:

| Event | Emitted when |
|---|---|
| `job.created`           | `POST /jobs` succeeds. |
| `evidence.updated`      | A worker attaches new evidence (workers call `JobStore.emit_event`). |
| `worker.started`        | A worker picks up the job, or `POST /jobs/{id}/resume` succeeds. |
| `worker.blocked`        | A worker raises a blocker requiring user input. |
| `worker.completed`      | A worker finishes its slice of the job. |
| `cost.accumulated`      | A model-call cost/usage delta folds into the job's cost meter. |
| `scoring.completed`     | Scoring/verification stage finishes. |
| `validation.completed`  | `POST /jobs/{id}/validate` succeeds. |
| `publish.ready`         | `POST /jobs/{id}/publish-plan` succeeds. |
| `job.failed`            | Cancellation or unrecoverable worker error. |

Workers running in-process can call:

```python
await app.state.store.emit_event(job_id, "evidence.updated", {"file": "…"})
```

to publish to whoever is currently subscribed.

## Storage model

The reference implementation keeps jobs in memory inside a `JobStore`.
There is no database, no migration, no fsync — restarting the API loses
in-flight job state. That is intentional: the API is a *projection* of
whatever the in-process orchestrator considers authoritative. Persistent
state belongs to the orchestrator backend, not to this control surface.

If you need persistence, wrap `JobStore` (or implement the same async
interface) and pass an instance into `create_app(store=…)`.

## Risks of "trusted local mode" (no token)

Running without a token assumes every local process is friendly. That
assumption is reasonable on a personal device but breaks down when:

* A different account on the same machine can connect to loopback.
* Untrusted code (a browser extension, a sandboxed app) can reach
  `127.0.0.1` through the host networking stack.
* The host is a multi-tenant container where loopback is shared.

In any of those cases, set `HERMES_ORCHESTRATOR_API_TOKEN` to a long
random secret and pass it on every request. The token never leaves the
machine — it is not synced anywhere.

## Client integration notes

* **Android APK.** Hits `http://127.0.0.1:8765/jobs/…` over the loopback
  interface inside the same device. Honour the token by storing it in
  Android `EncryptedSharedPreferences` and sending it as a bearer
  header.
* **TUI.** Imports `JobStore` directly and calls `emit_event` to feed
  the dashboard live updates without an extra round trip.
* **External clients.** Treat this exactly like a localhost-only REST
  API — there is no rate limiting, no auditing, no multi-tenant
  isolation, because there is no need for them. Clients are trusted.
