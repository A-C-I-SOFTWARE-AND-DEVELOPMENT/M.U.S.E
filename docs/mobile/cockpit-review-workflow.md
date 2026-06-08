# Cockpit review → publish workflow — from your phone

This is the plain-English walkthrough for the part of the MUSE
cockpit that turns a finished job into a pull request: **watch the work,
review the diff, browse the workspace, run the gates, then open a PR — all
from your phone**, over the cockpit API in
[`gateway/cockpit/`](../../gateway/cockpit/).

It is the review-and-ship companion to the overall
[mobile app guide](mobile-app-guide.md). Every route named here is **live**
in the cockpit gateway and tracked in the
[API contract](../android/hermes-apk-api-contract.md). Routes are written
short (`/jobs/{id}/diff`); the full path is always
`/v1/cockpit/jobs/{id}/diff`.

> **Two gates run through this whole flow.** Publishing needs the exact
> owner phrase `Yes, with authorization.`, and the sensitive routes
> (workspace browsing + publish) only work when the gateway is bound to
> **loopback**. Secrets never leave the gateway. Both are spelled out
> below where they apply.

---

## 0. The shape of the flow

```
pair → watch (SSE) → review (list · detail · diff · files · tree · file)
     → verify (validate · validation · override) → publish (preview · PR)
```

Each step is one or two routes. You can stop at any step — reviewing and
verifying are read-only and need no owner phrase; only the final publish
asks for it.

---

## 1. Pair the app to the cockpit

The cockpit serves on **loopback by default** — `127.0.0.1:8765` — and
requires a bearer token on every route except `GET /v1/health`.

1. Start it on the backend host: `muse cockpit serve` (background
   thread; loopback unless you pass `--allow-external`, which it warns
   about).
2. In the app, open **Settings → Connection**, enter the gateway URL,
   and pair. The app stores the token in `EncryptedSharedPreferences`
   and attaches `Authorization: Bearer <token>` from then on.
3. A missing or wrong token is a `401` on every cockpit route.

The token is the **only** secret the app holds. Provider API keys and the
GitHub PAT stay on the gateway and are never sent in a request body.

---

## 2. Watch the work live

Two Server-Sent Events streams keep the cockpit current without polling.
Both are bearer-authed, send a `heartbeat` every 15s, and exit promptly
when you disconnect or the gateway shuts down. If a stream drops (or your
build hasn't wired SSE yet), the cockpit **falls back to REST polling** —
the same data, just on an interval.

### Jobs stream — `GET /jobs/stream`

A snapshot-diff stream. On connect you get a `job.upsert` for **every**
job (the full current state), then `job.upsert` / `job.removed` deltas as
jobs change or disappear, plus the heartbeat. It merges JobQueue **and**
orchestrator (`/orchestrate`) jobs, so every backend job shows up.

```
event: job.upsert
data: { ...job... }

event: job.removed
data: { "id": "job_01HXYZ..." }

event: heartbeat
data: { "ts": "2026-06-04T18:45:00Z" }
```

### Events stream — `GET /events/stream`

A leveled **log** tail — each new gateway/worker log line arrives as an
SSE `log` event. Supports `?level=`, `?source=`, and `?job_id=` filters,
so you can watch one job's output or just errors.

```
event: log
data: { "ts": "...", "level": "info", "source": "worker", "job_id": "...", "message": "..." }
```

> The buffered list route `GET /events` still returns decision-ledger
> summaries (the leveled-log rewrite is the one remaining gap); the
> **stream** above is the live leveled source. For "what did the job
> actually do," the Activity timeline (`/ledger`) is the richer,
> secret-redacted view.

---

## 3. Review a job

### List and open it

- `GET /jobs` — every job as a `CockpitJob` (newest first). Git/publish
  fields like `branch` and `validation_summary` are surfaced only when the
  pipeline has populated them, and are `null` otherwise — never faked.
- `GET /jobs/{id}` — one job.
- `GET /jobs/{id}/ledger` — the read-only execution story (objective, plan,
  workers, timeline, files touched, test results, approvals). Honest
  derivation only: a field the source genuinely lacks comes back empty.

### Browse what changed

- `GET /jobs/{id}/files-changed` — just the changed-file list (path +
  additions/deletions), from `git --numstat`. Honest-empty `{"files": []}`
  when the job has no git workspace (orchestrator jobs don't carry one).
- `GET /jobs/{id}/diff` — the full unified diff blob plus that file list.
  Large diffs come back with `truncated: true`.

### Browse the whole workspace

Two read-only, path-sandboxed browsers let you open any file in the job's
workspace, not just changed ones:

- `GET /jobs/{id}/tree?path=…` — one directory level (name, kind, size,
  mtime). Default `path` is `.`.
- `GET /jobs/{id}/file?path=…` — one file's contents. Capped at 1 MB; a
  bigger or binary file returns `200` with `truncated: true` and
  `content: null` (use the "open in Termux" fallback there).

> **These two are loopback-only and self-protecting.** They are **disabled
> on a non-loopback cockpit** (`403`), a `path` that escapes the workspace
> root is a `400` (never followed), and any path resolving into `~/.hermes`
> is **refused** (`403`). The workspace root is unvalidated input from job
> dispatch, so these guards stop the readers being turned into a way to
> read the gateway's own `.env`, bearer token, or memory.

---

## 4. Verify — run the gates

Before you ship, run the workspace's verification gates and read the
result. Pass/fail come from the real `ValidationRunner` — nothing is
fabricated.

| Route | What it does |
|---|---|
| `POST /jobs/{id}/validate` | Run the gates now; persists `validation/results.json`; returns the `ValidationSnapshot`. `409` if the job has no workspace. |
| `POST /jobs/{id}/revalidate` | Same as `validate` — the explicit "re-run" verb. |
| `GET /jobs/{id}/validation` | Read the **last** persisted result (with any overrides applied) **without** re-running. Honest-empty gates before the first validate. |
| `POST /jobs/{id}/override` | Record an owner override for non-critical gates, with a required note. |

`validate` and `validation` share one projection, so the "run" and the
"read" views can't drift. Each gate carries a `status`
(`PASS`/`FAIL`/`WARN`/…) and an `override_allowed` flag.

### Override a non-critical gate

When a non-critical gate fails for a reason unrelated to your change, you
can override it so it no longer blocks publish:

```json
POST /v1/cockpit/jobs/{id}/override
{
  "gate_ids": ["ty_check"],
  "note": "Pre-existing failures unrelated to this change."
}
```

The override is persisted to `validation/overrides.json` and the snapshot
comes back with `publish_allowed` recomputed. Rules the handler enforces:

- A **critical gate cannot be overridden** — `403` (`gate is critical and
  not overridable`). Only gates marked `override_allowed` qualify.
- The `note` is **required** — `403` without it
  (policy: `override_requires_note`).
- An unknown gate id is a `404`; overriding before anything is validated is
  a `409` ("run validate first").

---

## 5. Publish — open a real PR

Publishing is a two-step: preview what would open, then open it. **The PR
step is owner-gated.**

### Preview — `GET /jobs/{id}/publish/preview`

Read-only and pure-git: it derives the remote, branch, and base; lists the
commits on the branch vs base; and proposes a default PR title and body.
No network, no writes. Honest nulls/empty when the job has no git
workspace.

### Open the PR — `POST /jobs/{id}/publish`

This is the owner-gated action. It behaves in three distinct ways:

1. **Without the owner phrase** → `200` with
   `status: "approval_required"` and the publish preview embedded. **No
   GitHub call is made.** This is the staged-approval state the cockpit
   shows you before you confirm.
2. **With the exact phrase** `Yes, with authorization.` → it opens a
   **real** PR via the GitHub REST API.
3. It is **disabled on a non-loopback cockpit** (`403`) — same loopback
   guard as the workspace browsers and `approve`.

```json
POST /v1/cockpit/jobs/{id}/publish
{
  "authorization": "Yes, with authorization.",
  "title": "feat(auth): add OAuth callback handler",
  "body": "## Summary\n...",
  "draft": true,
  "base": "main"
}
```

Two things to know before you rely on it:

- **It needs a PAT on the gateway.** Without
  `GITHUB_PERSONAL_ACCESS_TOKEN` in `~/.hermes/.env`, you get `403
  github_not_configured`. The token lives on the gateway — it is never sent
  from the phone.
- **It opens a PR for an already-pushed branch; it does not run `git
  push`.** The worker/CI pushes the branch; the cockpit only opens the PR
  against it. The repo deliberately keeps the PAT out of `git push`. If an
  open PR already targets the branch, you get `409 pr_already_exists` with
  the existing `pr_url` (the cockpit then offers "update existing PR").

On success:

```json
{
  "pr_url": "https://github.com/owner/repo/pull/42",
  "pr_number": 42,
  "branch": "feature/oauth-callback",
  "remote": "origin",
  "state": "open",
  "is_draft": true
}
```

> Prefer named starting points? `GET /templates` returns the owner's
> prompt templates (from `~/.hermes/cockpit/templates.json`), honest-empty
> when none are defined so the cockpit uses its bundled defaults.

---

## 6. Security posture — the short version

| Guard | What it protects |
|---|---|
| **Loopback-only for sensitive routes** | `/jobs/{id}/tree`, `/file`, `/publish`, and `approve`/`run` are refused (`403`) when the gateway is bound beyond loopback (`--allow-external`). A network-reachable cockpit cannot browse a workspace or open a PR. |
| **`~/.hermes` is off-limits** | The workspace readers refuse any path resolving into the M.U.S.E. state dir, so a job workspace can't be used to read the gateway's `.env`, bearer token, or memory. |
| **Owner phrase for publish** | Opening a PR needs exactly `Yes, with authorization.`. Anything short of that stages an `approval_required` and makes no GitHub call. |
| **Secrets never leave the gateway** | The app holds only the bearer token. Provider keys and the GitHub PAT stay on the gateway; no route accepts them in a request body. |
| **Read steps need no phrase** | Listing, diffs, file/tree browsing, and validation all act inside the already-approved local workspace and require only the bearer token. |

---

## See also

- [`../android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md)
  — the canonical route contract and the live-vs-planned status table.
- [mobile-app-guide.md](mobile-app-guide.md) — the cockpit overall:
  pairing, screens, approvals, notifications.
- [../voice/voice-first-user-guide.md](../voice/voice-first-user-guide.md)
  — driving the same backend by voice.
