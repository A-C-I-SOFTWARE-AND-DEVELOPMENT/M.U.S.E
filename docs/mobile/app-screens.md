# Mobile cockpit — Screens

> Authoritative behavioural spec is Phase 18's
> [`muse-apk-cockpit.md`](../android/muse-apk-cockpit.md). This file is
> the **implementation** view: routes, view-models, files-to-create,
> and the UX checklist that every screen must satisfy before it is
> considered done.

## UX checklist (every screen)

Every screen in this document is reviewed against the same five rules:

1. **Thumb-friendly.** Primary action sits in the bottom 25 % of the
   viewport. No primary action lives inside the top app bar.
2. **Large buttons.** Minimum tap target 56 dp; the *Dispatch*,
   *Approve*, *Publish*, *Cancel*, and *Override* buttons are 64 dp.
3. **Status-first.** The first paint of the screen shows the *state*
   of whatever the screen represents (a coloured pill, a glyph) before
   the body content renders.
4. **Minimal typing.** Every screen has at least one path that does
   not require the soft keyboard — chips, swipe, long-press, or voice.
5. **Voice confirmation.** Destructive actions (approve, publish,
   override, cancel, force-push) play a text-to-speech confirmation
   before firing. The user can disable TTS in *Settings → Voice*, but
   the on-screen confirmation sheet still appears.
6. **Offline queue visible.** Every screen shows the offline queue
   badge in the top app bar when there are pending writes.
7. **Never hide agent state.** No screen waits silently. If the data
   is stale, show a banner. If a stream dropped, show the amber
   *Live updates paused* pill. If the backend is unreachable, show it.

## Route table

| Route | Screen | Composable |
|---|---|---|
| `command` | Prompt Command Center | `PromptCommandCenterScreen` |
| `voice` | Voice Capture / Driving Mode | `VoiceCaptureScreen` |
| `dashboard` | Worker Dashboard | `WorkerDashboardScreen` |
| `jobs/{id}/tree` | Job Folder Browser | `JobFolderBrowserScreen` |
| `jobs/{id}/ledger` | Decision Ledger Viewer | `DecisionLedgerScreen` |
| `jobs/{id}/approval` | Approval Gate | `ApprovalGateScreen` |
| `jobs/{id}/validation` | Validation Gate | `ValidationGateScreen` |
| `jobs/{id}/publish` | GitHub Publisher | `GitHubPublisherScreen` |
| `jobs/{id}/deploy` | Supabase / Vercel Deploy Planner | `DeployPlannerScreen` |
| `remote/windows` | Remote Windows Worker Status | `RemoteWindowsScreen` |
| `settings` | Settings / Secrets / Integrations | `SettingsScreen` (extend existing) |
| `logs` | Logs / Events | `LogsScreen` |

These get appended to
[`Screen.kt`](../../apps/android/app/src/main/java/com/aci/hermes/ui/navigation/Screen.kt)
and wired into
[`HermesNavGraph.kt`](../../apps/android/app/src/main/java/com/aci/hermes/ui/navigation/HermesNavGraph.kt).

---

## 1. Prompt Command Center

- **Route:** `command`
- **Files:**
  `ui/screens/command/PromptCommandCenterScreen.kt`,
  `ui/screens/command/PromptCommandCenterViewModel.kt`,
  `ui/screens/command/PromptDraft.kt`
- **State:** `PromptCommandCenterUiState { workers, draft, isDispatching, error }`
- **Reads:** `cockpit.workers()`, `cockpit.promptTemplates()`
- **Writes:** `cockpit.dispatchJob(prompt: PromptDraft): JobId`
- **Layout:**
  - Top: worker chip row, horizontal scroll, one-thumb reachable.
  - Middle: prompt editor; grows to 70 % viewport when focused.
  - Below editor: template chip row + "*Safety block applied*" footer.
  - Bottom action bar: **Dispatch** (primary, 64 dp), long-press for
    *Dispatch + watch*, *Save as draft* secondary.
- **Voice hook:** mic FAB top-right opens the **Voice Capture** screen
  with the current draft pre-loaded.
- **Acceptance:** dispatch returns within 2 s on a healthy gateway; on
  failure the prompt body is preserved and a *Retry* / *Copy* snackbar
  appears.

## 2. Voice Capture / Driving Mode

- **Route:** `voice`
- **Files:**
  `ui/screens/voice/VoiceCaptureScreen.kt`,
  `ui/screens/voice/VoiceCaptureViewModel.kt`,
  bound to `service/VoiceCaptureService.kt`.
- **State:** `VoiceCaptureUiState { phase, partialTranscript, finalPrompt, dispatchState }`
- **Phases:**
  `idle → listening → transcribing → confirming → dispatching → done | error`
- **Layout (driving-mode):**
  - One enormous mic button centred, 200 dp.
  - Single-line current phase label above ("**Listening — speak now**").
  - Live partial transcript below in 32 sp text, high-contrast.
  - Bottom action bar shows **Confirm & dispatch** (green) and
    **Cancel** (red); both are voice-actionable ("confirm dispatch" /
    "cancel").
- **Voice grammar (no NLU; literal keywords):**
  - `dispatch` — start dispatch flow.
  - `confirm dispatch` — fire `POST /v1/cockpit/jobs`.
  - `cancel` — discard.
  - `approve <job-id>` — open Approval Gate for that job.
- **Acceptance:** with the screen visible and headphones in, the user
  speaks → cockpit dispatches → TTS says "*Job 47 dispatched on worker
  codex*". No taps required.

See [`app-voice-service.md`](app-voice-service.md) for the pipeline.

## 3. Worker Dashboard

- **Route:** `dashboard`
- **Files:** `ui/screens/dashboard/WorkerDashboardScreen.kt`,
  `WorkerDashboardViewModel.kt`
- **State:** `WorkerDashboardUiState { jobs, filter, streamState }`
- **Reads:** `cockpit.jobs(filter, cursor)` paginated +
  `cockpit.jobsStream()` SSE.
- **Writes:** `cockpit.approveJob(id)`, `cockpit.cancelJob(id)` via
  swipe with confirm dialog.
- **Layout:** two-line rows; sticky filter chip row (`all / running /
  waiting / done / failed`); each row a status badge with colour +
  glyph.
- **Acceptance:** SSE drop → amber *Live updates paused* pill ≤2 s;
  manual reconnect available in overflow.

## 4. Job Folder Browser

- **Route:** `jobs/{id}/tree`
- **Files:** `ui/screens/jobs/folder/JobFolderBrowserScreen.kt` +
  `…/JobFolderViewModel.kt`
- **Reads:** `cockpit.tree(jobId, path)`, `cockpit.file(jobId, path)`
- **Layout:** horizontally scrolling breadcrumb pinned to the
  right-most segment, then list. File preview opens in a bottom sheet
  occupying 80 % height; monospace 14 sp, horizontal scroll, no
  soft-wrap.
- **Long-press menu:** *Copy path*, *Open in Termux*, *View in GitHub*.
- **Acceptance:** >1 MB files are blocked from preview, *Open in
  Termux* offered.

## 5. Decision Ledger Viewer

- **Route:** `jobs/{id}/ledger`
- **Files:** `ui/screens/jobs/ledger/DecisionLedgerScreen.kt` +
  `…/DecisionLedgerViewModel.kt`
- **Reads:** `cockpit.ledger(jobId, since)` + SSE
  `cockpit.ledgerStream(jobId)`.
- **State:** `DecisionLedgerUiState { entries, streamState, filter }`
- **Layout:** vertical timeline; each entry shows
  `ts | actor (cockpit | worker | gateway | hook) | decision | rationale`.
  Tap-to-expand a long rationale; never truncates silently.
- **Filter chips:** `all / decisions / observations / errors`.
- **Optimistic merge:** entries written by `DecisionLedgerCache`
  (local cockpit decisions) are blended in until the SSE echo
  arrives, then deduplicated by `(ts, actor, decision)`.

## 6. Approval Gate

- **Route:** `jobs/{id}/approval`
- **Files:** `ui/screens/gates/approval/ApprovalGateScreen.kt`,
  `…/ApprovalGateViewModel.kt`
- **Reads:** `cockpit.job(id)`, `cockpit.diff(id)`,
  `cockpit.filesChanged(id)` (drives both Approval and Validation
  screens — both repositories share `DiffRepository`).
- **Writes:** `cockpit.approveJob(id, decision, notes?)`.
- **Layout:**
  - Top: job title, worker chip, status pill.
  - Body: unified diff (no side-by-side; viewport too narrow).
  - Bottom action bar (always reachable): **Approve & merge** (green,
    64 dp), **Request revision** (amber, opens notes input).
- **Destructive flow:** confirm sheet → optional TTS confirmation →
  POST with `Idempotency-Key`.
- **Acceptance:** stale state (HTTP 409) refreshes the screen
  silently and re-asks for confirmation; the original button never
  fires twice.

## 7. Validation Gate

- **Route:** `jobs/{id}/validation`
- **Files:** `ui/screens/gates/validation/ValidationGateScreen.kt`,
  `…/ValidationGateViewModel.kt`
- **Reads:** `cockpit.validation(id)`.
- **Writes:** `cockpit.revalidate(id)` (overflow),
  `cockpit.override(id, note)` (only if backend policy allows; the
  button is hidden, not just disabled, when policy forbids it).
- **Per-gate icons:** ✅ pass, ❌ fail, ⏳ pending, ⚠️ override-allowed.
- **Override flow:** dialog **plus** non-empty note **plus** TTS
  confirmation. Three confirmations because override bypasses tests
  and we want it to feel like that.

## 8. GitHub Publisher

- **Route:** `jobs/{id}/publish`
- **Files:** `ui/screens/publish/github/GitHubPublisherScreen.kt`,
  `…/GitHubPublisherViewModel.kt`
- **Reads:** `cockpit.publishPreview(id)`.
- **Writes:** `cockpit.publish(id, title, body, draft, base?)`.
- **Layout:** title (single line), body (markdown editor, monospace),
  *Draft* toggle (on by default), remote/branch/base preview card.
- **Confirm sheet** shows remote, branch, base, draft state, target
  PR ("creating new" vs "updating #123") before POST.
- **Acceptance:** 403 routes the user to a read-only *Backend GitHub
  status* card; PATs are never enterable from the cockpit.

## 9. Remote Windows Worker Status

- **Route:** `remote/windows`
- **Files:** `ui/screens/remote/RemoteWindowsScreen.kt`,
  `RemoteWindowsViewModel.kt`
- **Reads:** `cockpit.workers(kind = WINDOWS)` filtered subset.
- **Layout:** one card per Windows worker:
  - hostname, last-seen, ping ms, GPU presence, queue depth.
  - status dot (green / amber / red) reflects `last_heartbeat_age`.
  - **Wake** action (POST `/v1/cockpit/workers/{id}/wake`) is gated on
    the backend policy; if the backend says no, the button is hidden.
  - **Restart agent** (POST `/v1/cockpit/workers/{id}/restart-agent`)
    requires confirm sheet + TTS confirmation.
- **Acceptance:** stale heartbeats (≥30 s) flip the dot to amber
  client-side, regardless of what the worker self-reports.

## 10. Supabase / Vercel Deploy Planner

- **Route:** `jobs/{id}/deploy`
- **Files:** `ui/screens/publish/deploy/DeployPlannerScreen.kt`,
  `…/DeployPlannerViewModel.kt`
- **Reads:** `cockpit.deployPlan(id)` returns
  `{provider, env, dry_run_summary, risks: [{level, message}]}`.
- **Writes:** `cockpit.deployApply(id, providerToken?)`. The cockpit
  **does not hold the Supabase / Vercel token**; if the gateway
  requires the user to attach one to the request, the cockpit shows a
  *Bring credentials from gateway secret store* message and surfaces
  the secret IDs the gateway has registered. Provider tokens are
  never stored client-side.
- **Layout:**
  - Top: provider chip (Supabase / Vercel / "both — staged").
  - Middle: risk list, sorted critical → info.
  - Bottom: **Apply deploy** primary action, gated on *no critical
    risks remaining* unless the backend policy allows override.
- **Acceptance:** dry-run summary is rendered as-is from the gateway;
  the cockpit does not synthesise risks of its own.

## 11. Settings / Secrets / Integrations

- **Route:** `settings`
- **Files:** existing `ui/screens/settings/SettingsScreen.kt` +
  `SettingsViewModel.kt`; extend with new sections.
- **Sections (collapsible):**
  - **Connection** — gateway URL, bearer token (write-only field with
    obscured placeholder), *Test connection*, *Mock mode* toggle.
  - **Backend secrets (read-only)** — list of secret IDs the gateway
    has registered (e.g. `github.pat`, `supabase.service_role`,
    `vercel.token`). Each row is a glyph + ID + last-rotated date.
    The cockpit cannot edit them; tapping a row shows
    *"This secret lives on the gateway. Edit it on the host running
    `muse`."*
  - **Integrations** — per-integration ping (GitHub, Supabase, Vercel,
    OpenAI/Anthropic provider, Termux). Each row is a status dot.
  - **Voice** — toggle TTS confirmations, push-to-talk button (system
    media key vs. on-screen FAB), driving-mode auto-enter when
    Bluetooth A2DP is connected.
  - **Behaviour** — auto-subscribe new jobs to live events, show
    safety reminders before destructive approvals.
  - **About** — build info, version, cleartext-allowed badge.
  - **Reset** — clears cockpit settings only.

## 12. Logs / Events

- **Route:** `logs`
- **Files:** `ui/screens/logs/LogsScreen.kt`, `LogsViewModel.kt`
- **Reads:** `cockpit.events(since, levels, sources)` + SSE
  `cockpit.eventStream(filters)`.
- **Layout:** filter chips (`info / warn / error`) and
  (`gateway / worker / hook / cron`). Each row one wrapped line with
  a tappable meta strip that expands inline (does not push a screen).
- **Acceptance:** SSE drop → amber pause indicator; *Pause stream*
  toggle preserved across rotation.

---

## Cross-screen invariants

These are bugs the moment they happen — make them assertions in code,
not aspirations in docs:

- **No screen issues a POST without an `Idempotency-Key`.** Enforced
  in `CockpitClient` ([`app-api-client.md`](app-api-client.md)).
- **No screen reads a gateway URL or bearer token from anywhere
  other than `SettingsRepository`.** ViewModels do not see the raw
  token.
- **No screen reads the offline queue size from anywhere other than
  `OfflineQueue.flow`.** A single top-bar badge component subscribes
  once.
- **No screen calls `SpeechRecognizer` directly.** Voice flows go
  through `VoiceCaptureService` so the foreground notification stays
  consistent.
- **No screen swallows an error.** If a repository returns
  `Result.Failure`, the UI surfaces it (banner, snackbar, dialog) —
  never an empty placeholder.
