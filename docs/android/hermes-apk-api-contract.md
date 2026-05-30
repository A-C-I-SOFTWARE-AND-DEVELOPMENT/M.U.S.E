# Hermes APK ↔ Gateway — Cockpit API contract

Phase 18 wire format between the Android cockpit APK and a Hermes
gateway. This is a **specification**: the routes are not all live on the
gateway yet (`/v1/health` is — see `gateway/`). The contract is written
first so the Android side and the gateway side can be implemented in
parallel without drifting.

> **Authoritative location of secrets:** the **backend** holds provider
> API keys, GitHub PATs, and any other third-party credentials. The
> cockpit holds the **gateway bearer token only**, in
> `EncryptedSharedPreferences`. No cockpit endpoint accepts a provider
> API key in the request body.

---

## 1. Conventions

- Base URL is configured per device in *Settings → Connection*. All
  paths below are appended to it.
- All routes are HTTPS in production. Cleartext HTTP is supported by
  debug builds for LAN / emulator testing — see the cockpit doc.
- Auth: `Authorization: Bearer <gateway-token>` on every cockpit route
  except `/v1/health`. Missing or expired token → `401`.
- Content-type: `application/json` for request and response bodies,
  except SSE streams (`text/event-stream`).
- Timestamps: ISO-8601 UTC (`2026-05-23T18:45:00Z`).
- Pagination: cursor-based via `?cursor=<opaque>` + `?limit=<int>`;
  responses include `next_cursor` (nullable) and `prev_cursor`
  (nullable). Default `limit=25`, max `100`.
- Error envelope:

  ```json
  {
    "error": {
      "code": "validation_failed",
      "message": "Human-readable summary",
      "details": { "field_name": "what's wrong with it" }
    }
  }
  ```

  HTTP status mirrors the class: `400` validation, `401` auth, `403`
  policy, `404` missing, `409` state mismatch, `5xx` backend bug. The
  cockpit treats `code` as the source of truth for branching, not the
  human-readable message.

- Idempotency: `POST` routes that create or mutate accept an optional
  `Idempotency-Key` header. The gateway stores the resulting status
  for at least 24h keyed on `(token, key)`.

---

## 2. Health

### `GET /v1/health`

Already exists. Treated by the cockpit as "is the gateway up at all?".

The **live** cockpit gateway (`gateway/cockpit/handlers.py`) returns:

```json
{
  "ok": true,
  "service": "hermes-cockpit",
  "api_version": "1.0.0",
  "gateway_version": "0.14.0",
  "time": "2026-05-23T18:45:00Z"
}
```

An older/alternate gateway may instead return `{ "ok", "version",
"message", ... }`. The cockpit's `HealthStatus` model accepts **both**
variants (unknown keys ignored; `resolvedVersion` prefers
`gateway_version`, falling back to `version`) so negotiation works
across gateway revisions.

`ok=false` → cockpit renders *Backend reachable but reporting unhealthy*.

---

## 3. Runtime

### `GET /v1/cockpit/runtime/status`

Reports what's happening on the machine the gateway runs on.

```json
{
  "gateway": {
    "version": "0.14.0",
    "started_at": "2026-05-23T16:00:00Z",
    "pid": 1234,
    "mode": "termux" 
  },
  "host": {
    "platform": "android-termux",
    "arch": "aarch64",
    "hostname": "phone-1"
  },
  "queue": {
    "running": 2,
    "queued": 1,
    "waiting_approval": 0
  }
}
```

`gateway.mode ∈ {"local", "remote", "termux"}`. `host.platform ∈ {"linux",
"darwin", "windows", "android-termux"}`.

### `GET /v1/cockpit/runtime/workers`

Lists the workers the gateway has detected on its host. The cockpit's
**Settings → Worker detection** card renders this list directly.

```json
{
  "workers": [
    {
      "id": "codex_cli",
      "display_name": "OpenAI Codex CLI",
      "kind": "external_cli",
      "available": true,
      "version": "0.6.2",
      "path": "/data/data/com.termux/files/usr/bin/codex",
      "notes": null
    },
    {
      "id": "claude_code",
      "display_name": "Claude Code",
      "kind": "external_cli",
      "available": false,
      "version": null,
      "path": null,
      "notes": "Not installed on this host."
    },
    {
      "id": "hermes_batch",
      "display_name": "Hermes batch runner",
      "kind": "internal",
      "available": true,
      "version": "0.14.0",
      "path": null,
      "notes": null
    }
  ]
}
```

`kind ∈ {"external_cli", "internal", "remote_provider"}`.

### `GET /v1/cockpit/templates`

Optional. Returns named prompt templates the gateway exposes. Cockpit
falls back to a bundled default list if this returns 404.

```json
{
  "templates": [
    {
      "id": "build_feature",
      "title": "Build a feature",
      "body": "## Goal\n...\n## Constraints\n...",
      "default_worker": "codex_cli"
    }
  ]
}
```

---

## 4. Jobs — **canonical, implemented** (read + dispatch + cancel)

A **job** is one prompt × one worker × one execution. The cockpit
treats it as the unit of progress.

`GET /v1/cockpit/jobs`, `GET /v1/cockpit/jobs/{id}`,
`POST /v1/cockpit/jobs` (dispatch), and `POST /v1/cockpit/jobs/{id}/cancel`
are **live**, backed by the real `JobQueue` via the adapter in
`gateway/cockpit/contract.py`. The SSE stream, files, diff, validation,
and publish sub-resources remain specified-but-pending. Git/publish
metadata (`branch`, `validation_summary`, `publish_state`, …) is surfaced
from the job's `metadata` when the pipeline has populated it, and is
`null` otherwise — never fabricated.

> **Canonical status is a superset.** The wire `status` vocabulary is the
> union of the JARVIS-Prime queue's **execution** states
> (`QUEUED`, `RUNNING`, `PAUSED`, `BLOCKED`, `DISCONNECTED`, `COMPLETED`,
> `FAILED`, `CANCELLED`) and the cockpit's **workflow** states
> (`DRAFT`, `WAITING_FOR_APPROVAL`, `APPROVED`, `PUBLISHING`, `PUBLISHED`).
> The execution states come straight from the queue; the workflow states
> from a pipeline-set `metadata.workflow_status`. The Android `JobStatus`
> enum gains `PAUSED`/`BLOCKED`/`DISCONNECTED`/`COMPLETED` when aligned.
> Wire values are the **enum constant names** (UPPER_SNAKE), per §1.

### Job object

```json
{
  "id": "job_01HXYZ...",
  "title": "Add OAuth callback handler",
  "worker_id": "codex_cli",
  "status": "running",
  "created_at": "2026-05-23T18:30:00Z",
  "updated_at": "2026-05-23T18:42:11Z",
  "workspace_path": "/data/data/com.termux/files/home/projects/hermes",
  "branch": "feature/oauth-callback",
  "base_branch": "main",
  "remote": "origin",
  "validation_summary": { "pass": 4, "fail": 0, "pending": 1 },
  "publish_state": "not_started"
}
```

`status` lifecycle (one-way arrows; the cockpit never invents states):

```
draft → queued → running →┬─ waiting_for_approval → approved → publishing → published
                          ├─ failed
                          └─ cancelled
```

`publish_state ∈ {"not_started", "in_progress", "succeeded", "failed"}`.

### `GET /v1/cockpit/jobs`

Query: `status` (csv, optional), `worker_id` (optional), `cursor`,
`limit`. Returns:

```json
{
  "jobs": [ ...Job objects... ],
  "next_cursor": "opaque-or-null",
  "prev_cursor": null
}
```

### `GET /v1/cockpit/jobs/stream`

Server-Sent Events. Each event is a delta:

```
event: job.upsert
data: { ...Job object... }

event: job.removed
data: { "id": "job_01HXYZ..." }

event: heartbeat
data: { "ts": "2026-05-23T18:45:00Z" }
```

Heartbeat every 15s. If the cockpit goes >45s without a heartbeat, the
connection is considered dead and reopened with exponential backoff.

### `GET /v1/cockpit/jobs/{id}`

Returns the full Job object.

### `POST /v1/cockpit/jobs`

Dispatch a new job.

```json
{
  "title": "Add OAuth callback handler",
  "worker_id": "codex_cli",
  "prompt": "## Goal\n...",
  "workspace_path": "/.../projects/hermes",
  "branch_hint": "feature/oauth-callback",
  "watch": false
}
```

`watch=true` is a cockpit-side intent (auto-subscribe). The gateway
ignores it; it exists so the request body matches what the user saw.

Response: `201 Created` with the Job object.

### `POST /v1/cockpit/jobs/{id}/cancel`

```json
{ "reason": "Hit wrong workspace" }
```

`reason` is logged into the job's event stream. Response: `200` + Job.
`409` if the job is already in a terminal state.

---

## 5. Files

### `GET /v1/cockpit/jobs/{id}/tree`

Query: `path` (relative to `workspace_path`, default `.`). Returns:

```json
{
  "path": "src/auth",
  "entries": [
    { "name": "callback.py", "kind": "file", "size": 1234, "mtime": "2026-05-23T18:35:00Z" },
    { "name": "tests",        "kind": "dir",  "size": null, "mtime": null }
  ]
}
```

### `GET /v1/cockpit/jobs/{id}/file`

Query: `path`. Returns:

```json
{
  "path": "src/auth/callback.py",
  "size": 1234,
  "truncated": false,
  "content": "...UTF-8 text...",
  "encoding": "utf-8"
}
```

If the file is larger than the per-job max (default 1 MB) or is
binary, the response is `200` with `truncated=true` and `content=null`.
The cockpit shows the "open in Termux" fallback in that case.

---

## 6. Diff and approval

### `GET /v1/cockpit/jobs/{id}/diff`

Returns the worker's pending diff as a single unified-diff blob, plus
metadata so the cockpit can render the file list strip.

```json
{
  "files": [
    { "path": "src/auth/callback.py", "additions": 42, "deletions": 3 }
  ],
  "diff": "diff --git a/src/auth/callback.py b/src/auth/callback.py\n...",
  "truncated": false
}
```

If the diff exceeds 250 kB, `truncated=true` and `diff` carries the
first 250 kB. The cockpit shows the truncation banner.

### `GET /v1/cockpit/jobs/{id}/files-changed`

Convenience — same `files` array as the diff response, without the body.

### `POST /v1/cockpit/jobs/{id}/approve`

```json
{
  "decision": "merge",
  "notes": null,
  "decided_at": "2026-05-23T18:50:00Z",
  "decided_by": "cockpit"
}
```

`decision ∈ {"merge", "reject"}`. `reject` requires `notes` non-empty.
The gateway writes an audit-log line and transitions the job
(`waiting_for_approval` → `approved` or `needs_revision`). Response:
`200` + Job. `409` if the job already moved.

---

## 7. Validation

### `GET /v1/cockpit/jobs/{id}/validation`

```json
{
  "gates": [
    {
      "id": "tests",
      "name": "Unit tests",
      "status": "passed",
      "summary": "412 tests, 412 passed, 0 failed",
      "log_excerpt": null,
      "override_allowed": false
    },
    {
      "id": "ty_check",
      "name": "ty type-check",
      "status": "failed",
      "summary": "3 errors in src/auth/",
      "log_excerpt": "src/auth/callback.py:42: ...",
      "override_allowed": true
    }
  ],
  "policy": {
    "all_must_pass": true,
    "override_requires_note": true
  }
}
```

`status ∈ {"passed", "failed", "pending", "skipped", "error"}`.

### `POST /v1/cockpit/jobs/{id}/revalidate`

No body. Triggers the gateway to re-run gates. Response: `202`.

### `POST /v1/cockpit/jobs/{id}/override`

```json
{
  "gate_ids": ["ty_check"],
  "note": "Pre-existing failures unrelated to this change."
}
```

Response: `200` + new validation snapshot. `403` if policy disallows.

---

## 8. Publishing

### `GET /v1/cockpit/jobs/{id}/publish/preview`

```json
{
  "remote": "origin",
  "branch": "feature/oauth-callback",
  "base": "main",
  "commits": [
    { "sha": "abc1234", "subject": "feat(auth): add OAuth callback handler" }
  ],
  "default_title": "feat(auth): add OAuth callback handler",
  "default_body": "## Summary\n...\n",
  "existing_pr_url": null
}
```

### `POST /v1/cockpit/jobs/{id}/publish`

```json
{
  "title": "feat(auth): add OAuth callback handler",
  "body": "## Summary\n...\n",
  "draft": true,
  "base": "main"
}
```

Response (success):

```json
{
  "pr_url": "https://github.com/example/repo/pull/42",
  "pr_number": 42,
  "branch": "feature/oauth-callback",
  "remote": "origin",
  "state": "open",
  "is_draft": true
}
```

Errors:

- `403 github_not_configured` → backend has no PAT.
- `409 pr_already_exists` → response carries `pr_url`; cockpit flips
  the action to **Update existing PR**.

---

## 9. Events and logs

### `GET /v1/cockpit/events`

Query: `since` (ISO timestamp, optional), `level` (csv of
`info|warn|error`, optional), `source` (csv of
`gateway|worker|hook|cron`, optional), `job_id` (optional), `cursor`,
`limit`.

```json
{
  "events": [
    {
      "ts": "2026-05-23T18:45:00Z",
      "level": "info",
      "source": "worker",
      "job_id": "job_01HXYZ...",
      "message": "Wrote src/auth/callback.py",
      "attributes": { "bytes": 1234 }
    }
  ],
  "next_cursor": null
}
```

### `GET /v1/cockpit/events/stream`

SSE. Events use the same shape:

```
event: log
data: { "ts": "...", "level": "info", "source": "worker", "job_id": "...", "message": "..." }

event: heartbeat
data: { "ts": "..." }
```

---

## 10. Destructive command approvals

Some backend actions (force-push, rebase across protected base,
deleting a branch, running a long-running shell hook) wait for a human
green-light. The cockpit reads pending approvals from:

### `GET /v1/cockpit/approvals`

```json
{
  "approvals": [
    {
      "id": "appr_01HXYZ...",
      "job_id": "job_01HXYZ...",
      "kind": "force_push",
      "summary": "Force-push feature/oauth-callback to origin (1 commit ahead, 2 commits behind).",
      "details": {
        "remote": "origin",
        "branch": "feature/oauth-callback",
        "ahead": 1,
        "behind": 2
      },
      "expires_at": "2026-05-23T19:00:00Z"
    }
  ]
}
```

### `POST /v1/cockpit/approvals/{id}`

```json
{
  "decision": "approve",
  "notes": "Yes, this is the intended rebase."
}
```

`decision ∈ {"approve", "deny"}`. `409` if already decided or expired.

---

## 10a. Memory — **canonical, implemented**

The cockpit memory routes are **live** and emit the canonical schema
below (server is the source of truth; the Android `MemoryItem` mirrors
it field-for-field). Backed by the real JARVIS-Prime `MemoryStore` via
the adapter in `gateway/cockpit/contract.py` — no fabricated fields; a
field with no source signal is an explicit `null` or the `UNCATEGORIZED`
category, never a guess. Secrets are rejected at write time (→ `422`),
never stored or redacted-after-the-fact.

### Memory item

```json
{
  "id": "deploy_window",
  "category": "OWNER_PREFERENCE",
  "title": "deploy_window",
  "content": "Owner prefers deploys after 6pm ET",
  "durability": "PERMANENT",
  "confidence": "HIGH",
  "provenance": {
    "source": "agent",
    "session_id": null,
    "recorded_at": "2026-05-30T12:00:00Z",
    "note": "seen in chat"
  },
  "created_at": "2026-05-30T12:00:00Z",
  "updated_at": "2026-05-30T12:00:00Z",
  "last_accessed_at": "2026-05-30T13:00:00Z",
  "tags": ["ops"],
  "redacted": false,
  "hidden": false
}
```

- `category ∈ {OWNER_PREFERENCE, PROJECT_MEMORY, WORKFLOW_LESSON,
  TASK_CONTEXT, DECISION_RECORD, SOCIAL_SPEECH_PATTERN, SESSION_MEMORY,
  UNCATEGORIZED}` — `UNCATEGORIZED` is the honest "no classification"
  member (added to the canonical vocabulary so the server never invents a
  category). The Android `MemoryCategory` enum gains `UNCATEGORIZED` when
  it is aligned to this contract.
- `durability ∈ {EPHEMERAL, SESSION, SHORT_TERM, LONG_TERM, PERMANENT}`
  (store tiers `working`/`session`/`durable` map to
  `EPHEMERAL`/`SESSION`/`PERMANENT`).
- `confidence ∈ {LOW, MEDIUM, HIGH, CONFIRMED}` (derived from the store's
  confidence float).
- `id == title == key`: the store key is the stable identity, so
  `DELETE /v1/cockpit/memory/{id}` addresses the real record.

### `GET /v1/cockpit/memory`

Query: `q`/`query` (optional recollection), `limit`. Returns
`{ "items": [ ...Memory item... ] }`.

### `POST /v1/cockpit/memory`

Accepts the canonical fields (`title`, `content`, `category`,
`durability` enum, `confidence` enum, `tags`, `hidden`); the legacy flat
`key`/`value` is still accepted. `201` + `{ "stored": true, "item": {...} }`,
or `422` + `{ "stored": false, "reason": ... }` when the store rejects it
(secret-like or below the durable-confidence floor).

### `DELETE /v1/cockpit/memory/{id}`

`{ "removed": <int> }`.

---

## 10b. Audit — **canonical, implemented** (list + proof)

`GET /v1/cockpit/audit` and `GET /v1/cockpit/audit/{id}/proof` are **live**,
projecting the JARVIS-Prime **decision ledger** into the Android
`AuditRecord` / `ProofRecord` (adapter in `gateway/cockpit/contract.py`).

The ledger's 15 prose sections map onto the audit model; enum fields are
**derived honestly** from real text:
- `risk_tier` — `LOW` when `Open Risks` is empty/`N/A`, else `MODERATE`
  (the ledger has no explicit tier; never a fabricated specific band).
- `approval_state` — from the `Approval Required` verb (`no→UNNECESSARY`,
  `yes→APPROVED`, `defer→PENDING`).
- `result` — from the `Final Decision` text
  (`blocked`/`failed`/`rolled back`/`partial`/…→`SUCCESS`).
- `route.destination` — from `Selected Model/Worker`
  (`codex→CODEX`, `claude→CLAUDE`, `gateway→HERMES_GATEWAY`, …).
- `confidence` — `low/medium/high` → `0.4/0.7/0.95`.

Fields the ledger genuinely doesn't carry — `files_changed`,
`route.duration_ms`, enumerated `tests_run` — are emitted as empty/`0`,
never invented. `GET .../proof` returns `404` for an unknown id.

---

## 11. Versioning

This contract is versioned via the URL prefix `/v1/cockpit/...`. Any
backwards-incompatible change moves to `/v2/cockpit/...`. The cockpit
APK negotiates by:

1. Hitting `GET /v1/cockpit/runtime/status`. `404` → backend predates
   Phase 18 → cockpit screens are disabled with the empty-state copy
   from the cockpit doc.
2. Reading the gateway version from `/v1/health`.

---

## 12. SDK shape (Android side, sketch)

The matching Kotlin data classes land at
`apps/android/app/src/main/java/com/aci/hermes/data/cockpit/CockpitApi.kt`.
They map field-for-field to the JSON above. The cockpit's
`HermesCockpitClient`
(`apps/android/app/src/main/java/com/aci/hermes/data/cockpit/HermesCockpitClient.kt`,
transport in `CockpitHttp.kt`) is responsible for:

- attaching the bearer token — **implemented**,
- decoding the error envelope into a typed `CockpitError` — **implemented**,
- enforcing the 8-second short-timeout used by `/v1/health` probes
  (so the UI can show a real *Backend unreachable* state quickly) —
  **implemented**,
- reconnecting SSE streams with exponential backoff — *pending* (lands
  with the streaming surfaces).

The token is paired through *Settings → Connection*
(`SettingsRepository.cockpitToken`); chat routes live-vs-mock on pairing
via `RoutingJarvisChatGateway`. Typed accessors currently cover the
routes the gateway serves today (health, runtime status, worker
detection); other routes are reachable via `getRaw` until their server
shapes settle into typed models.

See [`hermes-apk-cockpit.md`](hermes-apk-cockpit.md) §4 for cross-cutting
behaviours (auth storage, destructive-action rules, network policy).
