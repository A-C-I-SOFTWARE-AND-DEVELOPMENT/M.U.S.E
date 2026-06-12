# M.U.S.E. mobile architecture (native Android, primary path)

This document describes the architecture implied by the Phase 02
decision in
[`android-vs-flutter-decision.md`](android-vs-flutter-decision.md).

> **Authoritative scope:** the Android native client at `apps/android/`.
> The wire format it speaks is in
> [`muse-mobile-backend-contract.md`](muse-mobile-backend-contract.md).
> The work items to land this architecture are in
> [`muse-app-module-plan.md`](muse-app-module-plan.md).
>
> **The Python runtime is unchanged.** The agent loop, skills, memory,
> tools, scheduling, and orchestration ledger live on the gateway side.
> The phone is a control surface.

---

## 1. Layered mental model

```
                     ┌─────────────────────────────────────────┐
   USER, on phone    │  Compose UI (screens, theming)           │
                     ├─────────────────────────────────────────┤
   ViewModel layer   │  StateFlow<UiState> per screen           │
                     ├─────────────────────────────────────────┤
   Domain layer      │  Repositories (Cockpit, Settings, Logs)  │
                     ├──────────────┬───────────────────────────┤
   Transport layer   │  HermesClient│  TermuxIntentBridge       │
                     │  (HTTP/SSE)  │  (RUN_COMMAND intents)    │
                     ├──────────────┴───────────────────────────┤
   Persistence       │  DataStore  +  EncryptedSharedPreferences│
                     ├─────────────────────────────────────────┤
   OS                │  Foreground service · Keystore · Mic    │
                     └─────────────────────────────────────────┘
                                       │
                                       ▼
                                ┌─────────────────────┐
                                │  M.U.S.E. gateway     │
                                │  (Python, off-phone │
                                │   or in Termux)     │
                                └─────────────────────┘
```

Each layer talks only to the one immediately below it. The transport
layer is the **only** place that touches the gateway or the Termux
sandbox; the rest of the app sees Kotlin data classes.

---

## 2. Kotlin modules (today and tomorrow)

The Gradle module is a single `:app` today. We plan to keep it that way
until a second binary needs to share code — premature module splits
slow Gradle without paying for themselves.

### 2.1 Existing source layout (under `app/src/main/java/com/aci/hermes/`)

| Folder | Purpose |
|---|---|
| `HermesApplication.kt` | App init, process-wide `AppContainer` wiring. |
| `MainActivity.kt` | Single Activity, hosts the Compose `NavHost`. |
| `di/AppContainer.kt` | Hand-rolled DI. No Hilt. Small enough that the indirection isn't worth it. |
| `data/cockpit/CockpitApi.kt` | Kotlin mirror of the cockpit wire format. |
| `data/model/` | `HermesTask`, `HermesRole`, `AiToolProfile` for the local-handoff fallback. |
| `data/network/` | `HermesClient` interface + `Gateway` and `Mock` implementations (lands with cockpit screens; today the local-handoff repo is `data/orchestrator/`). |
| `data/orchestrator/` | The pre-cockpit local handoff: `HermesTaskRepository`, `HandoffLauncher`, `PromptBuilder`. Preserved as the *Local handoff* fallback mode. |
| `data/preferences/` | `SettingsRepository` (DataStore) + EncryptedSharedPreferences for the bearer token. |
| `data/termux/TermuxIntentBridge.kt` | The Termux RUN_COMMAND envelope builder. |
| `service/HermesService.kt` | Foreground service that holds the persistent notification. |
| `ui/theme/` | Material 3 colour, type, theme. |
| `ui/navigation/` | NavHost + `Screen` sealed class. |
| `ui/screens/<name>/` | One folder per screen; each contains `<Name>Screen.kt` + `<Name>ViewModel.kt`. |
| `util/LogBuffer.kt` | In-memory ring buffer for the **Diagnostics** screen. |

### 2.2 New folders this decision lands

The cockpit screens add (without renaming anything above):

| Folder | Why |
|---|---|
| `data/network/HermesCockpitClient.kt` | Concrete OkHttp implementation of the cockpit API. |
| `data/network/CockpitSseClient.kt` | Server-Sent Events consumer for `/v1/cockpit/jobs/stream` and `/v1/cockpit/events/stream`. |
| `data/voice/` | `VoiceRecorder.kt` (Android `AudioRecord` wrapper) and `VoicePlayer.kt` (TTS playback). Used by the Prompt Command Center and any future "hold to talk" affordances. |
| `ui/screens/cockpit/prompt/` | Prompt Command Center. |
| `ui/screens/cockpit/jobs/` | Worker Dashboard and Job Folder Browser. |
| `ui/screens/cockpit/diff/` | Diff and Merge Review. |
| `ui/screens/cockpit/validation/` | Validation Gate. |
| `ui/screens/cockpit/publish/` | GitHub Publisher. |
| `ui/screens/cockpit/termux/` | Android / Termux Control Panel. |
| `ui/screens/cockpit/events/` | Logs and Events. |

The existing `ui/screens/chat/`, `ui/screens/orchestrator/`,
`ui/screens/settings/`, `ui/screens/diagnostics/`, `ui/screens/splash/`
remain. The **Local handoff** mode keeps the orchestrator screens; the
**Remote gateway** and **Termux gateway** modes use the cockpit screens.

---

## 3. State management

### 3.1 ViewModel pattern

Each screen pairs `<Name>Screen.kt` (Composable, dumb renderer) with
`<Name>ViewModel.kt` (state + side effects). The ViewModel:

- Holds a single `StateFlow<UiState>` data class.
- Mutates state via `_state.update { it.copy(...) }`.
- Exposes side-effecting suspend methods (`dispatch()`, `refresh()`,
  `approve()`, etc.) that launch inside `viewModelScope`.
- Never touches Android `Context` directly. Anything OS-flavoured lives
  in a repository or in `AppContainer`.

ViewModels are constructed by an `AppContainer.<screen>VmFactory()` and
handed to `androidx.lifecycle.viewmodel.compose.viewModel(factory = ...)`.
The factory is queried per screen instance.

### 3.2 Why no Hilt / Koin / Dagger

The dependency graph is shallow (≈ 10 leaf services). A factory in
`AppContainer` is cheaper than a DI runtime and surfaces wiring errors
at compile time. If the graph crosses ~20 leaves or a second
`:feature_*` module appears, revisit.

### 3.3 Cross-cutting state

- `SettingsRepository` exposes a `Flow<Settings>` cold-stream of the
  current connection config (URL, token, mock-mode flag, theme).
  ViewModels collect it the same way they collect their own state.
- The cockpit's "live" data (jobs, events) is owned by a small set of
  process-scoped `Mutex`-guarded caches in repositories — not by any
  ViewModel. The repos expose `SharedFlow<UpdateEvent>` so multiple
  screens (e.g. Worker Dashboard + Logs) can subscribe without
  duplicating SSE connections.

---

## 4. Transport layer

### 4.1 HTTP / SSE client

- **OkHttp** is the HTTP engine. We already have it in the module via
  the version catalog.
- **OkHttp-SSE** consumes Server-Sent Events. The
  `/v1/cockpit/jobs/stream` and `/v1/cockpit/events/stream` endpoints
  are the planned SSE surfaces; the live chat endpoint
  (`POST /v1/jarvis/chat`) streams **NDJSON** (`application/x-ndjson`),
  not SSE.
- **kotlinx.serialization** decodes JSON. `CockpitApi.kt` already
  declares the schemas with `@Serializable`.
- **Timeouts:** the health probe uses a short-timeout OkHttp clone
  (5s connect, 8s call). The cockpit's long-lived streams use the
  default OkHttp client with `pingInterval = 15s`.
- **Heartbeat policy:** server sends `event: heartbeat` every 15s. If
  the cockpit goes >45s without one, the connection is torn down and
  reopened with exponential backoff (2s → 30s, capped).
- **Backoff:** consistent exponential backoff with jitter for both HTTP
  retries and SSE reconnects, in a single `RetryPolicy` helper.

### 4.2 Termux intent bridge

`TermuxIntentBridge.kt` exists. It builds (but does not fire) the three
intents the cockpit uses: `com.termux.RUN_COMMAND`, `ACTION_MAIN`
(Termux launcher), `ACTION_VIEW` (Termux:Files). The wire details and
permission flow are in
[`docs/android/termux-intent-bridge.md`](../android/termux-intent-bridge.md).

The transport layer wraps every intent fire in a `TermuxFireResult`
sealed type (`Sent`, `TermuxMissing`, `PermissionDenied`, `Failed`) so
ViewModels can show actionable errors without inspecting OS state.

### 4.3 Mock implementation

`HermesClient.Mock` (existing) streams canned responses for the
chat surface. We add `HermesCockpitClient.Mock` that returns synthetic
job lists, diffs, validation reports, etc. **All cockpit screens must
be navigable in mock mode**; this is the test harness we use when no
gateway is reachable.

---

## 5. Foreground service and background work

### 5.1 The service we already have

[`HermesService.kt`](../../apps/android/app/src/main/java/com/aci/hermes/service/HermesService.kt)
holds a persistent notification with `foregroundServiceType="dataSync"`.
It currently has no business logic — it exists to keep the process
above the OS's background-execution cutoff.

### 5.2 What the service will own

- **Long-lived SSE subscriptions** to the gateway (jobs stream, events
  stream) when the user has opted into "watch in background" for at
  least one job.
- **Wake lock** acquisition while a watched job is in flight, released
  the moment the job terminates or the user revokes the "keep awake"
  toggle.
- **Notification rebroadcast** of approval-pending events — when a job
  enters `waiting_for_approval`, the service surfaces a notification
  with **Approve** / **Reject** actions that route back into the app
  for the confirmation sheet (never approve in-place from the
  notification).
- **Voice capture during hold-to-talk** when (and only when) the user
  has the cockpit on screen with the mic affordance active. The
  service is not a "always-on listener" — Android battery hygiene
  forbids that, and so does our threat model.

### 5.3 What the service does *not* own

- Not the agent loop. Not skill execution. Not tool dispatch. Not
  cron. Those are gateway concerns.
- Not arbitrary "keep the network alive forever" — the service tears
  down its streams as soon as no job is being watched and no approval
  is pending.

---

## 6. Voice layer

### 6.1 Capture

`data/voice/VoiceRecorder.kt` wraps Android's `AudioRecord` with
sensible defaults (16 kHz, 16-bit PCM, mono). The recorder emits a
`Flow<ByteArray>` of PCM frames. The cockpit's prompt screen pipes
those frames into the transport's chunked upload.

### 6.2 Permissions

`RECORD_AUDIO` is requested **lazily**, the first time the user taps
the mic affordance. We never request it at install time and never on
app launch — the permission ask is tied to the action that needs it.

### 6.3 Streaming to the gateway

Gateway-side ASR is the source of truth. The mobile app uploads PCM
chunks over a multipart POST or WebSocket frame (TBD with the
gateway-side voice feature) and renders the transcript as it streams
back. We do not ship a local ASR model in the APK in this phase.

### 6.4 TTS playback

`VoicePlayer.kt` plays back audio chunks the gateway emits as SSE
`event: tts.frame` data lines (base64-encoded). The implementation
uses Android's `AudioTrack` with a small jitter buffer.

### 6.5 Voice is opt-in, not default

Until the gateway-side voice surface is GA, voice in the cockpit lives
behind a feature flag in `SettingsRepository`. The flag defaults to
**off**; users enable it in Settings → Behaviour.

---

## 7. Secure storage

Two stores, deliberately split. Documented in
[`apps/android/docs/ARCHITECTURE.md`](../../apps/android/docs/ARCHITECTURE.md)
§"Secure storage"; restated here for completeness.

| Store | What goes in | Cloud backup |
|-------|--------------|--------------|
| DataStore (`hermes_settings`) | Gateway URL, theme, default provider id, mock-mode flag, onboarding flag, voice-enabled flag. | Backed up (no secrets). |
| EncryptedSharedPreferences (`hermes_secure_prefs.xml`) | Gateway bearer token; that is the **only** secret the cockpit holds. | **Excluded** via `data_extraction_rules.xml` + `backup_rules.xml`. |

Provider API keys (OpenAI / Anthropic / OpenRouter / etc.) live in
`~/.hermes/.env` on the gateway side and never leave it. If the
cockpit needs the gateway to call a provider, the gateway uses its own
credentials — the phone never carries one.

Token rotation: changing the gateway URL in Settings **clears** the
stored token. We never inherit a token across hosts.

---

## 8. Local API client

The local API client is `HermesCockpitClient`, an OkHttp-based
implementation of the cockpit interface. Key shape:

```kotlin
interface HermesCockpitClient {
    suspend fun runtimeStatus(): Result<RuntimeStatus>
    suspend fun listJobs(filter: JobFilter, cursor: String?): Result<JobList>
    fun jobStream(): Flow<JobStreamEvent>          // SSE
    suspend fun dispatch(request: DispatchJobRequest): Result<CockpitJob>
    suspend fun approve(jobId: String, decision: ApproveJobRequest): Result<CockpitJob>
    suspend fun diff(jobId: String): Result<DiffSnapshot>
    suspend fun validation(jobId: String): Result<ValidationSnapshot>
    suspend fun publishPreview(jobId: String): Result<PublishPreview>
    suspend fun publish(jobId: String, request: PublishRequest): Result<PublishResult>
    fun eventStream(filter: EventFilter): Flow<CockpitEvent>   // SSE
    suspend fun pendingApprovals(): Result<ApprovalList>
    suspend fun decideApproval(id: String, request: DecideApprovalRequest): Result<Unit>
}
```

`Result<T>` is `kotlin.Result`; the cockpit's `CockpitError` envelope
is mapped onto `Result.failure` with a typed exception
(`CockpitException(code, httpStatus, message, details)`).

The client is **request-scoped**, not per-app. Authentication header,
base URL, and provider headers are looked up from
`SettingsRepository.current()` for each call so config changes propagate
without restarting any ViewModel.

---

## 9. Offline queueing

Two queues, both local-only:

### 9.1 Draft prompts

When the gateway is unreachable but the user composes and taps
**Save as draft**, the prompt is written into DataStore under
`drafts.<uuid>`. Drafts are visible from the Prompt Command Center's
drawer; tapping one rehydrates the composer.

Drafts are **explicit**. We do not auto-save partial input — that's
how you accidentally store a half-typed credential.

### 9.2 Pending approvals

When the user taps **Approve** on a job and the POST fails (network
loss between tap and gateway response), we record a *pending decision*
in DataStore and surface a banner on the Worker Dashboard:
*"1 approval pending re-send"*. On the next successful health probe
the cockpit replays it via the cockpit contract's
`Idempotency-Key` header so the gateway can deduplicate.

We **never** silently retry. The user always sees the banner before
the replay fires.

---

## 10. Secure approval prompts

Three layers of friction on any destructive action:

1. **UI-level confirmation sheet.** Modal, requires an explicit tap on
   the affirmative button. No swipe-to-confirm. Cancel is always the
   default-focused button.
2. **Backend-side audit log entry.** The cockpit sends
   `{decision, decided_at, decided_by="cockpit"}` so the gateway logs
   the decision before the action runs.
3. **Optional override note.** For validation overrides, a non-empty
   note is required (gateway-enforced; cockpit pre-validates so the
   user sees the requirement before they POST).

Destructive actions inventory: *cancel job, override validation,
approve publish, approve destructive command, force-push, delete
branch*. None of them are reachable from a notification action — the
notification only opens the app to the confirmation sheet.

---

## 11. Connection state model

Single source of truth: `ConnectionState` in
[`HermesStatus.kt`](../../apps/android/app/src/main/java/com/aci/hermes/data/model/HermesTask.kt)
(today; consolidated into `data/network/` with the cockpit work).

| State | Meaning |
|---|---|
| `Unknown` | Nothing probed yet. |
| `Connecting` | Health probe in flight. |
| `Connected(status)` | Health probe returned 2xx. |
| `Failed(reason, kind)` | Probe failed; `kind ∈ {UNREACHABLE, WRONG_URL, TLS, HTTP, UNKNOWN}`. |

The Status, Diagnostics, and Provider screens all render from this
single state. The cockpit's screens layer **on top of it** — they show
their own "is the data fresh" pill but they do not invent their own
connection state.

---

## 12. Build types and flavours

We do **not** introduce product flavours. Two build types only:

| Build type | App id | Mock mode default | Cleartext HTTP | Notes |
|---|---|---|---|---|
| `debug` | `com.aci.hermes.debug` | ON | allowed | sits alongside release; default gateway is `http://127.0.0.1:8765` (`SettingsRepository.DEFAULT_GATEWAY_ENDPOINT`). |
| `release` | `com.aci.hermes` | OFF | gated (planned: off-by-default ahead of 1.0) | user enters gateway URL on first run. |

The release variant is what we ship to Play Store / F-Droid. Future
work: a `signedDebug` variant for over-the-air installs that need a
stable signature without enabling minification.

---

## 13. CI and shipping

- `.github/workflows/android-build.yml` already builds the debug APK
  on every change under `apps/android/` and uploads it as a workflow
  artifact (`hermes-agent-debug-apk`). Lint runs as a separate job.
- Release signing is **not** wired up by default — we do not ship a
  sample because someone would commit a keystore.
- Distribution targets (in priority order): direct APK download from
  releases, F-Droid, Google Play. Each has a tracking checklist in the
  module's `README.md`.

---

## 14. Why this architecture, in one paragraph

M.U.S.E. already chose to be a Python agent. The mobile client's job is
not to re-implement that agent on a phone but to give Jeremiah a way
to *drive* it from his pocket. Native Android, with a thin transport
layer between the cockpit screens and the gateway, is the smallest
amount of code that satisfies the phone-first, voice-aware,
Termux-integrated, background-tolerant constraints. Anything bigger
(re-embedding Python, wrapping a desktop dashboard, picking a
cross-platform stack we'd then have to bridge) costs more than it
buys.
