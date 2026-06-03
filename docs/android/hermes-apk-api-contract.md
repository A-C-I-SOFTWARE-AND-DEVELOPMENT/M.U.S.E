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

## 4. Jobs — **canonical, implemented** (read + dispatch + controls)

A **job** is one prompt × one worker × one execution. The cockpit
treats it as the unit of progress.

`GET /v1/cockpit/jobs`, `GET /v1/cockpit/jobs/{id}`,
`POST /v1/cockpit/jobs` (dispatch), `POST /v1/cockpit/jobs/{id}/run`,
`POST /v1/cockpit/jobs/{id}/cancel`, and the control + detail surface
`GET /v1/cockpit/jobs/{id}/ledger`, `POST …/pause`, `POST …/resume`,
`POST …/rerun`, `POST …/approve`, `GET …/diff`, `POST …/validate`
are **live**, backed by the real `JobQueue` + orchestrator via the
adapters in `gateway/cockpit/contract.py` (`cockpit_job`,
`orchestrator_job`, `orchestrator_job_detail`, `queue_job_detail`). The
list merges JobQueue **and** orchestrator (`/orchestrate`) jobs so every
backend job appears. The **SSE stream** (`/jobs/stream`) and the
publish-preview/publish sub-resources remain specified-but-pending — see
`MOBILE-JOBS-STREAMING-001` in `docs/orchestration/next-roadmap.md`;
the Android cockpit uses REST polling + foreground notifications today,
not SSE. Git/publish metadata (`branch`, `validation_summary`,
`publish_state`, …) is surfaced from the job's `metadata` when the
pipeline has populated it, and is `null` otherwise — never fabricated.

> **Owner gate preserved.** `…/approve` (and the execute lanes of
> `…/run`) require the exact owner authorization phrase **and** a
> loopback bind; a non-loopback cockpit is refused. `pause`/`resume`/
> `rerun`/`diff`/`validate` act only inside the already-approved local
> workspace and need no phrase.

### Job detail / ledger — `GET /v1/cockpit/jobs/{id}/ledger`

Read-only execution story for the Job Detail screen. Honest derivation
only — a field the source genuinely lacks is empty/null (e.g. the
orchestrator ledger records no shell commands, so `commands_run` is `[]`
for orchestrator jobs).

```json
{
  "id": "job_01HXYZ...",
  "objective": "Add OAuth callback handler",
  "status": "RUNNING",
  "plan": "",
  "current_step": "running worker codex-execute",
  "workers": [ { "id": "codex-execute", "worker": "codex-execute", "status": "RUNNING", "summary": "", "error": null, "attempts": 0 } ],
  "timeline": [ { "ts": "2026-05-23T18:30:00Z", "kind": "submit", "phase": null, "actor": "owner", "summary": "Add OAuth callback" } ],
  "evidence": [],
  "files_touched": ["src/auth.py"],
  "commands_run": [],
  "test_results": { "pass": 4, "fail": 0, "pending": 1 },
  "approvals": [ { "id": "…", "approver": "owner", "state": "APPROVED", "comment": "phase 'execute' approved" } ],
  "rollback": null
}
```

### Controls

| Method | Path | Effect |
|---|---|---|
| `POST` | `…/pause` | Pause a running/queued queue job. `409` if terminal or an orchestrator job. |
| `POST` | `…/resume` | Re-queue a paused/blocked/disconnected/failed job — the unblock action. |
| `POST` | `…/rerun` | Reset a failed/blocked worker (`worker_id` optional; first failed otherwise). |
| `POST` | `…/approve` | Grant a gated phase (`{phase, authorization}`); owner phrase + loopback gated. |
| `GET`  | `…/diff` | Working-tree `git diff` for the job's workspace ("open patch"); honest empty when none. |
| `POST` | `…/validate` | Run the workspace's verification gates ("run verification"); returns the `ValidationSnapshot` shape. |

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

## 10d. Learning Queue — **canonical, implemented**

The JARVIS learning-dataset candidate queue: validated, source-backed
traces awaiting owner approval before they are eligible for export
(fine-tuning / preference / eval / skill candidates). Backed by
`hermes_cli/jarvis_prime/learning_dataset.py`; secrets and raw
chain-of-thought are stripped at write time, so the list never carries
the raw trace payload.

### `GET /v1/cockpit/learning`

```json
{
  "learning": [
    {
      "id": "abc123",
      "title": "research answer trace",
      "trace_type": "research_answer_trace",
      "status": "pending",
      "labels": [],
      "is_negative": false,
      "quality": {
        "tests_passed": false,
        "citations_verified": true,
        "owner_approved": false,
        "reviewer_passed": false,
        "rollback_available": false
      },
      "provenance": {
        "source_kind": "research_vault",
        "source_uri": "https://example.org",
        "citations": ["https://example.org"]
      },
      "created_at": "2026-06-01T00:00:00Z"
    }
  ]
}
```

Optional query filters: `trace_type`, `status`.

### `POST /v1/cockpit/learning/{id}`

```json
{ "decision": "approve", "authorization": "Yes, with authorization." }
```

`decision ∈ {"approve", "reject"}`. **Approve requires the exact owner
phrase** (`authorization`) — `403` otherwise (the owner gate is never
bypassed). Reject needs no phrase. `404` for an unknown candidate.

### `GET /v1/cockpit/learning/export`

Read-only export readiness (counts per format) — never streams the raw
payload:

```json
{
  "formats": ["jsonl", "preference_pairs", "eval_cases", "skill_candidates"],
  "approved": 3,
  "exportable": 2,
  "pending": 5
}
```

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

## 10c. Approvals — **canonical, implemented** (cards + owner-phrase decide)

The Android Approvals screen is one `ApprovalCard` queue. The server's one
real owner-gated queue is the JARVIS **self-update proposal** store, so:

- `GET /v1/cockpit/approvals` → canonical `ApprovalCard`s projected from
  proposals (risk class `RC0–RC4` → `tier` `LOW/LOW/RISKY/SERIOUS/CRITICAL`
  — never `SAFE`, since a queued item always needs approval; status
  `proposed/approved/rejected` → `PENDING/APPROVED/REJECTED`). Multi-step
  serious/critical state is UI-runtime and defaulted client-side, not
  fabricated server-side.
- `POST /v1/cockpit/approvals/{id}` → approve/reject. **Approve requires the
  exact owner phrase** `Yes, with authorization.` (else `403`); the owner
  gate is never bypassed.
- `GET /v1/cockpit/proposals` → the self-update-native shape (`risk_class`,
  `risk_level`, `target`, …) for a proposal-specific view.

Future destructive-command approvals join the same card queue — no second
store is invented.

---

## 10d. Evidence Engine — **canonical, implemented** (RAG + cite + verify)

The Android Evidence screen renders source-cited artifacts from the JARVIS
**Research Vault** (`hermes_cli/jarvis_prime/research_vault.py`), ranked by
the **Evidence Engine** (`hermes_cli/jarvis_prime/evidence_engine.py`).
Adapters live in `gateway/cockpit/contract.py` (`evidence_card`,
`evidence_hit`, `evidence_verify_result`). Trust labels reuse the
`SourceTrust` ladder (`owner` > `primary` > `official_doc` > `reputable` >
`community` > `unverified`).

### Evidence item

```json
{
  "id": "16-hex",
  "title": "vLLM continuous batching",
  "source_uri": "https://docs.vllm.ai/serving",
  "source_type": "official_doc",
  "evidence_strength": "primary",
  "trust": "primary",
  "excerpt": "vLLM uses continuous batching ...",
  "summary": "...",
  "tags": ["vllm"],
  "license_notes": "",
  "retrieved_at": "2026-05-30T12:00:00+00:00",
  "freshness_due": null,
  "checksum": "sha256-hex",
  "citation_anchors": ["serving.md:12"],
  "added_at": "2026-05-30T12:00:00+00:00"
}
```

### `GET /v1/cockpit/evidence`

Query: `q`/`query` (optional), `limit`. Without `q`: `{ "items": [ ...Evidence
item... ] }`. With `q`: hybrid retrieval (BM25 over the vault blended with
Memory-Tree search) returns `{ "items": [], "hits": [ ...ranked hit... ] }`,
where a hit is `{ kind, title, uri, excerpt, trust, score, artifact_id,
citation_anchors }`.

### `GET /v1/cockpit/evidence/{id}`

`{ "item": { ...Evidence item... } }`, or `404` for an unknown id.

### `POST /v1/cockpit/evidence/verify`

Body `{ "claims": [string], "query"?: string }`. Returns
`{ "citations": [{ claim, supported, hits }], "uncertain": [string],
"contradictions": [{ subject, a, b, reason }], "rejected": [string] }`.
`rejected` holds claims dropped as secret-like / chain-of-thought (they never
become evidence). Unsupported claims appear in both `citations`
(`supported:false`) and `uncertain`.

### `POST /v1/cockpit/evidence/{id}/promote`

Body `{ "authorization"?: "Yes, with authorization." }`. Promotes the artifact
into the **durable Memory Tree** via `MemoryTreeStore.write`, so the memory
write policy is preserved: secrets / chain-of-thought are rejected, and a
low-confidence/unverified promotion needs the owner phrase. `201` +
`{ "promoted": true, "node_id": ... }`, or `422` +
`{ "promoted": false, "reasons": [...], "hint": ... }` — **unverified data
never becomes durable memory automatically.**

### `DELETE /v1/cockpit/evidence/{id}`

Demote (remove) an artifact: `{ "removed": <int> }`.

## 10e. GraphRAG knowledge graph — **canonical, implemented**

A typed, source-backed knowledge graph over the cognition plane (repo code,
docs, Research Vault, Memory Tree, and the job + decision ledgers). It
**supplements** existing RAG/memory — it does not replace them. Adapters in
`gateway/cockpit/contract.py` (`graph_related_view`, `graph_answer_view`);
the engine is `hermes_cli/jarvis_prime/graphrag/`.

### `GET /v1/cockpit/graph/related`

Related files / sources / decisions for an entity. Pass exactly one of
`job_id`, `memory_id`, `evidence_id`, or `node` (a graph node id/key).
Powers the "Related in knowledge graph" panel on the Task (job), Audit, and
Memory screens. Honest empty (`{"node":"","related":[]}`) when the entity is
not in the graph yet — never a fabricated relationship.

```json
{
  "node": "task:abc123",
  "origin": "orc-1",
  "related": [
    {"kind": "FILE", "node_type": "file", "title": "run_agent.py",
     "ref": "run_agent.py", "relation": "depends_on", "source_backed": true,
     "sources": [{"uri": "orc-1", "kind": "job_ledger"}]},
    {"kind": "DECISION", "node_type": "decision", "title": "Localization approach",
     "ref": "memory:9f…", "relation": "cites", "source_backed": true, "sources": []}
  ]
}
```

`kind` is one of `FILE` / `SOURCE` / `DECISION` (the Android `RelatedKind`
enum constants). `source_backed` is true when the node carries provenance.

### `GET /v1/cockpit/graph/query?mode=…&q=…`

Run a GraphRAG query. `mode` is `local` (nearest nodes), `global` (community
summary), or `coding` (relevant files + tests + docs + prior decisions, so a
coding task reuses what exists). Returns a `GraphAnswer`:

```json
{
  "mode": "coding",
  "question": "where is job dispatch handled?",
  "nodes": [{"id": "file:…", "type": "file", "title": "orchestrator.py", "key": "hermes_cli/orchestrator.py"}],
  "edges": [{"src": "file:…", "dst": "function:…", "type": "owns"}],
  "citations": [{"uri": "hermes_cli/orchestrator.py", "kind": "repo"}],
  "communities": []
}
```

### `POST /v1/cockpit/graph/build`

Rebuild + persist the graph cache (`~/.hermes/jarvis_prime/graph/graph.json`).
Read-only over the repo and local stores — no repo edits, no network — so it
is **not** an owner-gated action. Returns `{"saved": "...", "nodes": N,
"edges": M, "by_node_type": {...}, "by_edge_type": {...}}`.

## 10f. Autonomy & emergency stop — **canonical, implemented**

Owner High-Autonomy Coding mode reduces friction for coding work *inside an
approved workspace* while every irreversible/external/high-risk action stays
gated. The level is the existing `hermes_cli/approval_policy.py` engine
(`read_only/assisted/autonomous/yolo/owner_high_autonomy_coding`); the cockpit
endpoints set/read it and surface the capability list straight from
`approval_policy.capabilities()` (never a hand-maintained copy).

### `GET /v1/cockpit/autonomy`

```json
{
  "level": "owner_high_autonomy_coding",
  "display_name": "High-Autonomy Coding",
  "workspace_root": "/home/me/project",
  "updated_at": 1717430400.0,
  "set_by": "cockpit",
  "revocable": true,
  "capabilities": {
    "auto_approved": ["safe_read", "safe_local_write", "local_command",
      "dependency_install", "local_server", "branch_create", "local_commit",
      "code_worker_exec", "secret_access"],
    "requires_approval": ["destructive_command", "github_push", "supabase_change",
      "vercel_deploy", "outbound_message", "remote_command", "continuous_listen"],
    "always_deny": ["github_force_push", "remote_secret_transfer", "public_tunnel"],
    "workspace_scoped": ["safe_local_write", "code_worker_exec"]
  }
}
```

`workspace_scoped` actions auto-approve **only** when their target path is
inside `workspace_root`; outside it they fall back to a confirmation. The
`requires_approval` set (deploy, publish, push/merge, credential/secret change,
destructive/outside-workspace delete, public posts, purchases) and the owner
gates (`owner_auth.OWNER_GATED_ACTIONS`, exact-phrase) are **never** removed by
this mode.

### `POST /v1/cockpit/autonomy`

Body: `{"level": "owner_high_autonomy_coding", "workspace_path": "/home/me/project"}`
to set, or `{"revoke": true}` to drop back to `assisted`. Setting
`owner_high_autonomy_coding` without a `workspace_path` returns `400`. The mode
change is recorded in the approval audit log (`details.event = "autonomy_change"`).
Returns the same shape as `GET`.

### `GET /v1/cockpit/autonomy/decisions?limit=50`

Recent, already-redacted policy decisions — the per-action auto-approval
*reasons*. Powers the High-Autonomy Coding audit trail.

```json
{"decisions": [
  {"ts": 1717430401.0, "actor": "agent", "action": "local_command",
   "summary": "pytest -q", "decision": "allow",
   "reason": "owner_high_autonomy_coding: auto-approved local_command inside approved workspace /home/me/project"}
]}
```

### `POST /v1/cockpit/emergency-stop`

Body: `{"reason": "..."}` (optional). Cancels every non-terminal queue job
(reusing `JobQueue.cancel_job`), **latches** autonomy to `read_only`, and audits
the event. The latch overrides everything — including `HERMES_AUTONOMY` — so a
stop genuinely halts new auto-approvals; it is released the moment the owner
sets a level again via `POST /v1/cockpit/autonomy`. Returns:

```json
{"engaged": true, "cancelled_jobs": ["job_ab12"], "cancelled_count": 1,
 "autonomy_level": "read_only", "errors": []}
```
## 10d. Research Vault — **canonical, implemented** (recent evidence, read-only)

`GET /v1/cockpit/research` is **live**, projecting the JARVIS **Research
Vault** (`hermes_cli/jarvis_prime/research_vault.py`) for the mobile home
screen's evidence card and any research view.

- Query: `?limit=` (default `10`). Items are **most-recent first**.
- Response: `{ "items": [ ResearchItem ], "error"?: "…" }`. A missing or
  empty vault returns `{ "items": [] }` — **never fabricated evidence**, and
  a read failure degrades to an empty list with a non-fatal `error` string
  (never a crash).

### ResearchItem (one-to-one with `ResearchArtifact.to_dict()`)

```json
{
  "id": "ab12…",
  "title": "Model X benchmark",
  "source_uri": "https://…",
  "source_type": "manual",
  "evidence_strength": "moderate",
  "summary": "Model X tops the board on …",
  "excerpt": "…stored citation text…",
  "tags": ["models", "benchmark"],
  "freshness_due": null,
  "added_at": "2026-06-03T12:00:00Z"
}
```

Kotlin mirror: `CockpitResearchItem` / `CockpitResearchList` in
`CockpitApi.kt`; accessor `HermesCockpitClient.research(limit)`.

This is a **read-only** projection — the app does not write the vault.

---

## 10e. Models / router policy — **read, typed**

`GET /v1/cockpit/models` is **live** (handler `models`), returning the
free-first router policy from `model_bootstrap.load_policy()` (or a
`dry_run` preview when none is written yet). The shape is intentionally
loose; the typed Kotlin mirror `ModelPolicy` / `ModelRoute`
(`HermesCockpitClient.modelPolicy()`) is fully defaulted and the decoder
ignores unknown keys, so an evolving policy never crashes the client. The
handler **never accepts or stores API keys** — detection is env-presence
only.

> **Note (events vs audit):** the home command center's "Audit / ledger"
> card reads the canonical **`GET /v1/cockpit/audit`** records (§10b,
> `auditList()`), not `GET /v1/cockpit/events`. The events handler returns a
> `_ledger_summary` shape (`id/title/type/status/source/timestamp`) that does
> **not** match the contract's `CockpitEvent` (`ts/level/source/message`), so
> the typed `audit` records are the reliable source for the card.

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
