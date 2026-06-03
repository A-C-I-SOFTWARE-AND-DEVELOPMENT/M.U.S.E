# Hermes APK Cockpit — Phase 18 specification

> **Status:** specification + integration plan. The cockpit is an evolution
> of the existing native Android app at [`apps/android/`](../../apps/android/).
> This document defines the cockpit shape; the API contract lives in
> [`hermes-apk-api-contract.md`](hermes-apk-api-contract.md), wireframes in
> [`hermes-apk-ui-wireframes.md`](hermes-apk-ui-wireframes.md), and the
> on-device Termux integration in [`termux-intent-bridge.md`](termux-intent-bridge.md).

## 1. What "cockpit" means

The APK is a **control surface** for a running Hermes backend. It does not
embed Python, does not execute jobs locally, and does not store secrets that
belong on the backend. It:

- watches the backend's state (jobs, workers, logs),
- submits prompts and approval decisions through the gateway,
- launches and stops the backend when it runs co-located in Termux,
- never silently mutates state — every destructive or publishing action
  is gated on an explicit on-device tap.

The mental model is the same as a flight cockpit over an autopilot — the
backend flies, the phone arms switches and reads instruments.

The existing local-orchestrator handoff flow in `apps/android/` (clipboard
copy of prompts to Codex / Claude / ChatGPT) is preserved as a **fallback
mode** for users without a running Hermes backend, exposed under
*Settings → Mode → Local handoff*.

## 2. Two operating modes

| Mode | Backend location | Reachable as |
|------|------------------|--------------|
| **Remote gateway** | A Hermes gateway on a server / VPS | `https://<host>` |
| **On-device Termux** | `hermes gateway start` inside Termux on the same phone | `http://127.0.0.1:8080` |

Mode is a runtime choice — the cockpit detects on first launch and falls
back to **Local handoff** if neither reaches.

## 3. Required screens

Each screen below carries:

- **Purpose** — what the user accomplishes here.
- **Data source** — which gateway endpoint(s) or local source it reads.
- **Actions** — what the user can tap.
- **Error states** — what the screen shows when reads / writes fail.
- **Loading states** — the placeholder while data is in flight.
- **Phone-first UX** — design constraints unique to a 6" portrait surface.

### 3.1 Prompt Command Center

- **Purpose:** Author and dispatch a new worker prompt. The central
  "compose" surface.
- **Data source:** `GET /v1/cockpit/workers` for the worker picker;
  `GET /v1/cockpit/templates` for prompt templates (optional, falls back
  to bundled defaults); `POST /v1/cockpit/jobs` to dispatch.
- **Actions:**
  - Select worker (Codex CLI / Claude Code / Hermes batch / custom).
  - Pick prompt template or write freeform.
  - Attach workspace path or branch hint.
  - Tap **Dispatch** → creates a job and navigates to its dashboard row.
  - Tap **Save as draft** → stores locally in `DataStore`, not on backend.
  - Long-press **Dispatch** for *Dispatch + watch* (auto-subscribes to
    SSE log stream).
- **Error states:**
  - Worker list 5xx → keep last known list, show muted banner *"worker
    list is stale (last refreshed HH:MM)"*; dispatch still allowed.
  - Dispatch 4xx (validation) → inline error attached to the offending
    field; the body of the prompt is preserved.
  - Dispatch 5xx → top snackbar with **Retry** and **Copy to clipboard**
    actions; never silently retries.
- **Loading states:**
  - Worker picker shows shimmer chips while the list loads.
  - **Dispatch** button shows an inline circular spinner and is disabled
    until the gateway returns the job id.
- **Phone-first UX:**
  - The prompt field expands to fill ~70 % of the viewport height when
    focused; the keyboard never overlaps the *Dispatch* button.
  - Worker picker is a horizontal chip row, not a dropdown, so one-thumb
    selection is possible.
  - The Safety block from `PromptBuilder.SAFETY_BLOCK` is appended on the
    backend; the UI shows a single-line "Safety block applied" footer so
    the user knows the prompt going out is not raw.

### 3.2 Worker Dashboard

- **Purpose:** See every job in flight, queued, or recently finished.
- **Data source:** `GET /v1/cockpit/jobs?status=...` (paginated, default
  page 25), with **live updates via SSE** on `/v1/cockpit/jobs/stream`.
- **Actions:**
  - Tap a job → opens the **Job Folder Browser** for that job.
  - Swipe right on a job → quick **Approve** (only enabled when the job
    is in a `waiting_for_approval` state).
  - Swipe left on a job → quick **Cancel** (with confirm dialog).
  - Pull to refresh → forces an HTTP re-read.
- **Error states:**
  - SSE drops → status pill turns amber "Live updates paused";
    auto-reconnect with exponential backoff (2 s → 30 s); manual
    **Reconnect** action in the overflow menu.
  - HTTP 401 → routes to **Settings → Connection** with the explanation
    *"Gateway token rejected"*.
- **Loading states:**
  - Skeleton rows for the first page.
  - Subsequent pages show a thin progress bar above the list.
- **Phone-first UX:**
  - Each row is two-line: title + worker chip on line one, status badge +
    relative time on line two.
  - Status badges use colour **and** glyph so the screen is legible in
    high-contrast and grayscale modes.
  - Filter chips (`all / running / waiting / done / failed`) sit in a
    sticky header that collapses on scroll.

### 3.3 Job Folder Browser

- **Purpose:** Inspect the working tree the backend is operating against
  for a given job.
- **Data source:** `GET /v1/cockpit/jobs/{id}/tree?path=...` and
  `GET /v1/cockpit/jobs/{id}/file?path=...` (returns truncated content
  with a max-size guard).
- **Actions:**
  - Tap a folder → drills in (path breadcrumb above).
  - Tap a file → opens a read-only preview pane with syntax-highlighted
    text (no editor; this is a cockpit).
  - Overflow → **Copy path**, **Open in Termux** (intent bridge), **View
    in GitHub** (if the job has a known origin remote).
- **Error states:**
  - Path 404 → empty-state card *"This path no longer exists on the
    worker"* with **Refresh** action.
  - File >1 MB → preview blocked, show file size, offer **Open in Termux**
    fallback.
- **Loading states:**
  - Tree shows a single shimmer column.
  - File preview shows a shimmer of the first 30 lines.
- **Phone-first UX:**
  - Breadcrumb scrolls horizontally; the right-most segment (current dir)
    is always pinned visible.
  - Preview uses 14 sp monospace with horizontal scroll for long lines;
    no soft-wrapping (it lies about structure).
  - File-type icons are minimal: code-square, doc, image, archive — that's
    it. No mime guessing fan.

### 3.4 Diff and Merge Review

- **Purpose:** Approve or reject the changes a worker produced before
  they are pushed anywhere.
- **Data source:** `GET /v1/cockpit/jobs/{id}/diff` (unified diff
  produced by `git diff --no-color` on the worker side) and
  `GET /v1/cockpit/jobs/{id}/files-changed` for the summary chips.
  **Approval write:** `POST /v1/cockpit/jobs/{id}/approve` with
  `{decision: "merge"|"reject", notes?: string}`.
- **Actions:**
  - Toggle file in the side strip → jumps the diff viewport.
  - Tap **Approve & merge** → confirm sheet, then POST.
  - Tap **Request revision** → opens a text input for reviewer notes,
    sends `decision=reject` with notes.
  - Long-press a hunk → **Copy hunk** to clipboard for sharing.
- **Error states:**
  - Diff fetch >250 kB → truncated banner with **Open in Termux** link.
  - Approval 409 (state changed since fetch) → block the POST, refresh
    the screen, show *"This job moved to <state> on the backend; review
    its current diff before approving."*
- **Loading states:**
  - File list and diff body each show separate skeletons so a quick
    file-list response doesn't block the user reading metadata.
  - The Approve button is disabled until both have loaded.
- **Phone-first UX:**
  - Unified diff only (no side-by-side — the viewport is too narrow).
  - Sticky file path header on each chunk.
  - The Approve/Reject buttons live in the bottom action bar (always
    reachable by thumb), not at the bottom of the scrolling diff.

### 3.5 Validation Gate

- **Purpose:** Show whether a job's output passes the gates configured
  on the backend (tests, lint, type-check, custom hooks) before merge or
  publish is offered.
- **Data source:** `GET /v1/cockpit/jobs/{id}/validation` returns a list
  of `{name, status, summary, log_excerpt?}`. The gateway is the source
  of truth for *which* gates apply — the cockpit never decides.
- **Actions:**
  - Tap a gate row → expands the log excerpt inline.
  - Tap **Re-run gates** (overflow) → `POST /v1/cockpit/jobs/{id}/revalidate`.
  - Tap **Override and continue** → only visible if the backend's policy
    permits override; opens an audit-note text field; sends
    `POST /v1/cockpit/jobs/{id}/override` with the note.
- **Error states:**
  - All gates failed → screen header turns red, the **Open Publisher**
    button becomes hidden (not just disabled) so the path forward is
    "fix or override", never accidental.
  - Validation endpoint 5xx → keep the last successful snapshot, show
    an amber strip *"Validation status is stale"*.
- **Loading states:**
  - Each gate row is a single skeleton; gates report independently as
    the backend resolves them, so rows flip from skeleton → result in
    place.
- **Phone-first UX:**
  - Per-gate icon language is binary: ✅ pass, ❌ fail, ⏳ pending,
    ⚠️ override-allowed.
  - Override is **never** swipeable — it requires a dialog confirmation
    plus a non-empty note.

### 3.6 GitHub Publisher

- **Purpose:** Push the approved branch and open a PR (or update an
  existing one).
- **Data source:** `GET /v1/cockpit/jobs/{id}/publish/preview` returns
  `{remote, branch, base, commits, pr_url?}`. Publishing is
  `POST /v1/cockpit/jobs/{id}/publish` with
  `{title, body, draft, base?}`.
- **Actions:**
  - Edit title / body (pre-filled from the worker's commit message and
    `PromptBuilder` metadata).
  - Toggle **Draft** (on by default — Phase 12 + Phase 17 convention).
  - Tap **Publish** → confirm sheet showing the remote / branch / base
    one more time, then POST.
- **Error states:**
  - 403 from gateway (GitHub PAT missing/expired) → block publish,
    surface *"Backend has no GitHub credentials configured."* with a
    deep link to `Settings → Backend GitHub status` (read-only;
    PATs are entered on the backend, never in the APK).
  - 409 PR already exists → show the existing PR URL and switch
    **Publish** to **Update existing PR**.
- **Loading states:**
  - Title and body show shimmer until the preview loads.
  - Publish button shows an inline spinner during the POST.
- **Phone-first UX:**
  - The PR URL is rendered as a tap-to-open link the moment the POST
    succeeds; nothing else changes layout, so the user knows immediately
    where the result landed.

### 3.7 Android / Termux Control Panel

- **Purpose:** Drive the local Hermes gateway when it lives inside
  Termux on the same device — start / stop / restart, hold wake-locks,
  jump into Termux for shell-level diagnosis.
- **Data source:**
  - `GET /v1/cockpit/runtime/status` (gateway reports its own runtime)
    for the *Backend status* card.
  - Local Android signals for the wake-lock toggle and the Termux
    install / `RUN_COMMAND` reachability check.
- **Actions:** described in detail in
  [`termux-intent-bridge.md`](termux-intent-bridge.md). Summary:
  - Start / Stop / Restart the gateway (Termux `RUN_COMMAND` intent).
  - Toggle "Keep device awake while orchestrating" (Android partial wake
    lock held by the foreground service).
  - **Open Termux** (intent) for the user to do anything manual.
  - **Copy worker prompt** (last dispatched prompt, for paste-into-Termux
    workflows).
  - **Approve publish** — surfaces the most recent publish-pending job
    as a one-tap shortcut.
  - **Approve destructive command** — surfaces any backend request that
    needs an explicit on-device green-light (e.g. force-push approval).
  - **View logs** → routes to the **Logs and Events** screen scoped to
    the local runtime.
- **Error states:**
  - Termux not installed → install card with link to the F-Droid /
    GitHub builds (cockpit never sideloads, it links out).
  - `RUN_COMMAND` denied → instruction card to grant the permission in
    Termux's settings; cockpit links to the Termux settings activity.
  - Backend status endpoint unreachable → status card flips to
    *"Gateway not running"* and the **Start** button becomes primary.
- **Loading states:**
  - Status card is skeleton-then-content; the action buttons stay
    enabled even during loads (start/stop are idempotent on the
    gateway).
- **Phone-first UX:**
  - Big, two-state action: a single **Start gateway** / **Stop gateway**
    button that swaps colour and label based on status.
  - Wake-lock toggle is a Material 3 switch with a one-line description
    of the trade-off.
  - All Termux interop actions live behind a single *"Open in Termux"*
    section to keep the rest of the screen un-cluttered for users on
    remote-gateway mode (the section auto-collapses if Termux is absent).

### 3.8 Logs and Events

- **Purpose:** Tail recent backend events (per-job and global) without
  needing to SSH or open Termux.
- **Data source:** `GET /v1/cockpit/events?since=...` and live via SSE
  on `/v1/cockpit/events/stream`. Events carry
  `{ts, level, source, job_id?, message, attributes?}`.
- **Actions:**
  - Filter by level (info / warn / error) and by source (gateway /
    worker / hook / cron).
  - Filter to *current job* when entered from the Worker Dashboard.
  - Long-press an event → **Copy line**.
  - Overflow → **Pause stream**, **Clear screen** (visual only — does
    not delete backend events).
- **Error states:**
  - SSE drops → same amber paused-stream model as the dashboard.
  - HTTP fetch 5xx → empty state with **Retry**; never auto-spams.
- **Loading states:**
  - Initial screen shows skeleton rows; live tail appends from the top.
- **Phone-first UX:**
  - Each row is one wrapped line + a meta strip; the meta strip is
    tappable for *show details*, which expands inline rather than
    pushing a new screen.
  - Colour is **augmented** by glyph (warning ⚠️, error ✕) for
    grayscale-mode legibility.

### 3.9 Settings / Worker Detection

- **Purpose:** Configure the cockpit's connection to the backend,
  detect which workers the backend has available, and toggle
  cockpit-side behaviours.
- **Data source:**
  - Local `SettingsRepository` (DataStore) for cockpit preferences.
  - Local `EncryptedSharedPreferences` for the gateway bearer token.
  - `GET /v1/cockpit/runtime/workers` for backend-side detection
    (which CLIs / providers / skills are reachable from where the
    gateway is running).
- **Actions:**
  - Edit gateway URL.
  - Edit gateway bearer token (write-only; the field never displays the
    stored value, only an obscured placeholder).
  - **Test connection** → calls `GET /v1/health`.
  - **Refresh worker detection** → re-reads
    `/v1/cockpit/runtime/workers`.
  - Toggle: *Auto-subscribe new jobs to live events*.
  - Toggle: *Allow Termux intents from this app* (cockpit-side hint;
    the OS still authorizes per-call).
  - Toggle: *Show safety reminders before destructive approvals*.
  - **Reset all cockpit settings** (does not touch the backend).
- **Error states:**
  - `/v1/cockpit/runtime/workers` 404 → backend predates Phase 18;
    show a small *"backend not on cockpit protocol"* hint and disable
    cockpit-only screens (dashboard, validation, publisher) with an
    explanatory empty state rather than blank screens.
  - Token save → if EncryptedSharedPreferences write fails, surface a
    snackbar and keep the field marked dirty so the user can retry.
- **Loading states:**
  - Worker-detection card has a single skeleton; each detected worker
    is a row with `name`, `version`, `path`, and a status dot.
- **Phone-first UX:**
  - Section headers (`Connection`, `Workers`, `Behaviour`, `About`)
    collapse into anchors so the page is one scrollable column instead
    of a tab bar (tabs are awful at 6" portrait).
  - Token is masked input by default, with a one-tap *show* affordance
    that auto-hides after 5 seconds.

## 4. Cross-cutting concerns

### 4.1 Authentication

- Gateway bearer token in `Authorization: Bearer <token>` for every
  call. Stored in EncryptedSharedPreferences (`hermes_secure_prefs.xml`,
  excluded from cloud backup via `data_extraction_rules.xml`).
- Provider API keys live **on the backend**, not in the APK. The
  cockpit never carries an OpenAI / Anthropic key.

### 4.2 Destructive actions

A destructive action is any of: *cancel job*, *override validation*,
*approve publish*, *approve destructive command*, *force-push*,
*delete branch*. All of them:

- require an extra confirmation sheet (not a swipe),
- send the explicit decision token to the backend
  (`{decision: ..., decided_at: <ts>, decided_by: "cockpit"}`),
- write an audit log entry on the backend before the work proceeds.

### 4.3 Network policy

- Cleartext HTTP allowed on debug builds for LAN / emulator testing
  (current `usesCleartextTraffic="true"`). The release variant should
  flip cleartext off — see *Settings → Cleartext* read-only badge.
- All long-poll / SSE connections are torn down when the activity is
  destroyed; the cockpit foreground service does *not* keep streams
  open in the background (battery hygiene).

### 4.4 Mock mode

The local-orchestrator flow already in `apps/android/` is retained as
the *Local handoff* fallback. The cockpit screens (3.1 – 3.8) require a
reachable backend; when no backend is reachable they remain navigable
but each surface the same empty-state card:

> Cockpit screens need a Hermes gateway. Open *Settings → Connection*
> to point at one, start one in Termux from the Control Panel, or
> switch to *Local handoff* mode if you only want to copy prompts to
> Codex / Claude / ChatGPT.

## 5. Telemetry

The cockpit emits **zero** telemetry from the APK itself. Backend events
viewed in *Logs and Events* are read on demand. The user is the audit
trail; nothing is phoned home from the device.

## 6. Open implementation work

This file is the spec. Concrete code stubs landing in this phase:

- `apps/android/app/src/main/java/com/aci/hermes/data/termux/TermuxIntentBridge.kt`
  — the Android-side wrapper around Termux `RUN_COMMAND` intents.
- `apps/android/app/src/main/java/com/aci/hermes/data/cockpit/CockpitApi.kt`
  — typed data classes mirroring the API contract.

The `HermesCockpitClient` implementation and the backend-side cockpit
routes (`/v1/cockpit/*`) now ship; the cockpit surfaces wired today
include health/runtime, memory, audit + proof, owner approvals, control,
avatar persona + room, and live chat streaming.

**Backend orchestration jobs (contract §4) are wired into the Tasks tab.**
The *Backend jobs* section lists real backend jobs (orchestrator + JobQueue,
merged by `GET /v1/cockpit/jobs`). "New backend job" creates a **runnable
orchestrator** job via `POST /v1/cockpit/orchestrate` (not a JobQueue entry,
which `job_run` can't run) — so a job created here can then be run. The run
picker is sourced from `GET /v1/cockpit/jobs/lanes` (the worker ids
`job_run` actually accepts, e.g. `codex-execute` / `hermes-local-planner`),
not the detection lanes from `runtime/workers`. Run is shown only for
runnable orchestrator jobs (`orc-` ids); other entries show Cancel. The
local clipboard-handoff task list is preserved below it, unchanged.

Running an **execute lane** is owner-gated end to end: each lane carries
`requires_approval`, the app collects the exact owner phrase
(`Yes, with authorization.`) for gated lanes, and the gateway re-checks it
server-side — refusing entirely on a non-loopback cockpit
(`POST /v1/cockpit/jobs/{id}/run`). Code:
`data/cockpit/HermesCockpitClient.{jobLanes,orchestrate,jobRun}`,
`CockpitJobsRepository`, `ui/screens/jobs/CockpitJobsViewModel`, and the
*Backend jobs* section in `ui/screens/tasks/TasksScreen.kt`. Backend:
`gateway/cockpit/handlers.py::{job_lanes,orchestrate_submit,job_run}`.

Remaining follow-ups (see `docs/audits/JARVIS_MOBILE_NATIVE_FULL_BUILD_AUDIT.md`):
the live events feed, model scorecards / sessions read views, the skills
catalog reconciliation, Research Vault + ledger-replay surfaces, and the
build→diff→validate→publish-PR workflow.
