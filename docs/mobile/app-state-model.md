# Mobile cockpit — State model

> How data flows through the cockpit. Screens consume immutable
> `UiState`; view-models hold `StateFlow<UiState>`; repositories own
> the network and disk. Nothing else.

## 1. Layered architecture

```
        ┌─────────────────────────────────────────────────────┐
        │            Compose screens (ui/screens/*)            │
        │   stateless, render UiState, emit UiIntent events    │
        └───────────────▲──────────────────────┬───────────────┘
                        │ StateFlow<UiState>   │ intent
                        │                      ▼
        ┌─────────────────────────────────────────────────────┐
        │             ViewModels (per-screen)                  │
        │   stateIn(SharingStarted.WhileSubscribed(5_000))     │
        └───────────────▲──────────────────────┬───────────────┘
                        │ repository Flow      │ suspend fun
                        │                      ▼
        ┌─────────────────────────────────────────────────────┐
        │   Repositories (data/*Repository.kt)                 │
        │   merge: API + disk cache + offline queue + SSE      │
        └───────────────▲──────────────────────┬───────────────┘
                        │                      │
              ┌─────────┴───┐   ┌──────────┐  ┌▼───────────────┐
              │ CockpitClient│  │OfflineQ. │  │SettingsRepo (DS)│
              └──────────────┘  └──────────┘  └────────────────┘
```

Every arrow is one-way. No screen reaches into another screen's
view-model. No view-model reaches into another view-model. Repos are
singletons owned by [`AppContainer`](../../apps/android/app/src/main/java/com/aci/hermes/di/AppContainer.kt).

## 2. State types

### 2.1 UiState

`UiState` is a sealed interface per screen. Three concrete shapes
exist on every screen:

```kotlin
sealed interface DashboardUiState {
    data object Loading : DashboardUiState
    data class Ready(
        val jobs: List<JobSummary>,
        val streamState: StreamState,
        val filter: JobFilter,
        val offlinePending: Int,
    ) : DashboardUiState
    data class Failed(val error: CockpitError) : DashboardUiState
}
```

Rules:

- `UiState` is **immutable** (`data class` / `data object` only).
- `UiState` carries the *resolved* values the screen renders. It
  never holds raw API DTOs or `Throwable`.
- Errors are modelled as a typed `CockpitError` so the UI can branch
  on `code` without parsing strings.
- The `Ready` variant always includes `streamState` and
  `offlinePending` — these two badges are present on every screen and
  the type system makes that hard to forget.

### 2.2 UiIntent

User actions are routed through a single `intent(UiIntent)` entry
point on the view-model. This keeps the view-model API small and
makes UI tests trivial.

```kotlin
sealed interface DashboardUiIntent {
    data object Refresh : DashboardUiIntent
    data class ChangeFilter(val filter: JobFilter) : DashboardUiIntent
    data class ApproveJob(val id: JobId) : DashboardUiIntent
    data class CancelJob(val id: JobId, val reason: String?) : DashboardUiIntent
}
```

### 2.3 UiEffect

One-shot side effects (snackbars, navigation pushes, TTS phrases) are
emitted as `SharedFlow<UiEffect>` from the view-model. Screens
collect them in a `LaunchedEffect`. Effects are not state — they
must not survive process death.

## 3. Coroutine and scope rules

- ViewModels use `viewModelScope`.
- Repositories live for the app's lifetime and use a top-level
  `applicationScope` injected from `AppContainer`. Long-running
  collectors (SSE) belong here, not on a screen.
- `HermesService` has its own `serviceScope` cancelled in
  `onDestroy()`.
- **No `GlobalScope`. Anywhere.** CI greps for it.

## 4. Repositories

| Repository | Owns | File |
|---|---|---|
| `SettingsRepository` | gateway URL, bearer token, mock toggle, voice prefs | `data/preferences/SettingsRepository.kt` (existing) |
| `WorkerDirectoryRepository` | available worker profiles + heartbeats | NEW |
| `JobRepository` | jobs list, per-job detail, SSE subscription | NEW |
| `DiffRepository` | diff + files-changed for a job (shared by Approval + Validation) | NEW |
| `ValidationRepository` | per-job validation gate state | NEW |
| `PublishRepository` | publish preview + apply | NEW |
| `DeployRepository` | Supabase / Vercel deploy plan + apply | NEW |
| `DecisionLedgerRepository` | merged local + remote ledger entries | NEW |
| `EventRepository` | event stream + filtered fetch | NEW |
| `VoiceRepository` | recogniser, TTS, dictation buffer | NEW |
| `OfflineQueueRepository` | pending writes when offline | NEW |
| `RuntimeRepository` | gateway/runtime status, Termux state | NEW |

Each repository exposes a `Flow<…>` for read paths and `suspend fun`
for write paths. SSE subscriptions are merged with HTTP reads inside
the repository — view-models never see SSE plumbing.

## 5. Optimistic decisions and the ledger cache

Approvals, overrides, and publishes are slow on flaky networks.
Rather than block the UI on the POST, the cockpit:

1. Writes a `LocalLedgerEntry` to `DecisionLedgerCache`
   (`origin = COCKPIT_PENDING`).
2. Fires the POST via `CockpitClient` with the same
   `Idempotency-Key`.
3. On success → repository marks the entry `COCKPIT_CONFIRMED`.
4. On failure → entry marked `COCKPIT_FAILED`, with the error
   surfaced as a `UiEffect.SnackbarError`. The user can retry from
   the ledger row.
5. On SSE echo from the gateway → the gateway-origin entry replaces
   the pending entry, deduped by `(idempotency_key | ts+actor+decision)`.

The Decision Ledger Viewer always shows pending entries with a
*pending* glyph and a *Retry* / *Cancel* action so a write that
disappeared into the network does not vanish from the user's view.

## 6. Offline queue

`OfflineQueueRepository` persists pending writes to disk as JSON
records:

```kotlin
data class PendingWrite(
    val id: UUID,
    val createdAt: Instant,
    val verb: HttpVerb,
    val path: String,
    val body: String,
    val idempotencyKey: String,
    val attempts: Int,
    val lastError: String?,
)
```

The queue is drained by `HermesService` (see
[`app-background-service.md`](app-background-service.md)) with
exponential backoff. Every screen displays the pending count in its
top app bar; tapping it opens an inline sheet listing pending writes
with **Retry now** and **Discard** actions.

## 7. Mock mode parity

`AppContainer` constructs a `MockCockpitClient` when mock mode is
enabled. Every repository sees the same interface; nothing in the
view-model layer changes. Mock mode is the canonical UI test
fixture — if you add a new screen, you add the mock fixtures next to
the production wiring in the same PR.

## 8. Persistence boundaries

| Data | Where | Why |
|---|---|---|
| Gateway URL, voice prefs, mock toggle, UI flags | `DataStore<Preferences>` | Non-secret, survives process death. |
| Gateway bearer token | `EncryptedSharedPreferences` | Secret, must not leak via backups (excluded in `data_extraction_rules.xml`). |
| Offline queue | App-internal file under `filesDir/queue/*.json` | Crash-safe with `synchronized()` writes + `.tmp` rename. |
| Decision ledger cache | App-internal SQLite (`Room`) keyed by `(jobId, idempotencyKey)` | Survives process death; small enough that an LRU eviction by row count (default 5_000) is fine. |
| Diff / file / event bodies | In-memory only | They can be re-fetched; not worth disk. |

## 9. Threading rules

- Compose lambdas are main-thread; never block them.
- Repositories run network on `Dispatchers.IO`, disk I/O on
  `Dispatchers.IO`, parse on `Dispatchers.Default` if the payload is
  >32 kB.
- View-models marshal state back to the main thread via
  `StateFlow` — Compose collects it lifecycle-aware via
  `collectAsStateWithLifecycle()`.

## 10. Anti-patterns the codebase rejects

These show up in PRs sometimes; reject them:

- **Repository fields in ViewModels.** Use intent + state, not direct
  mutation.
- **`MutableStateFlow` exposed publicly.** Always `asStateFlow()` or
  `stateIn(…)` so callers cannot mutate it.
- **Result types squeezed through `Throwable`.** Use the typed
  `CockpitError` from `data/api/`.
- **`runBlocking` anywhere.** Use `suspend` all the way down.
- **Polling.** Subscribe to SSE; if the data lacks a stream
  endpoint, add one on the gateway side rather than schedule a
  polling loop on the device.
- **`LiveData`.** This codebase is `StateFlow` end-to-end.

## 11. Example: Approval Gate state flow

```kotlin
class ApprovalGateViewModel(
    private val jobs: JobRepository,
    private val diffs: DiffRepository,
    private val voice: VoiceRepository,
    private val savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val jobId: JobId = savedStateHandle.require("jobId")

    val state: StateFlow<ApprovalGateUiState> =
        combine(
            jobs.job(jobId),
            diffs.diff(jobId),
            diffs.filesChanged(jobId),
            jobs.streamState,
            offline.pending,
        ) { job, diff, files, stream, pending ->
            ApprovalGateUiState.Ready(job, diff, files, stream, pending)
        }
        .catch { e -> emit(ApprovalGateUiState.Failed(CockpitError.from(e))) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), ApprovalGateUiState.Loading)

    private val _effects = MutableSharedFlow<ApprovalGateUiEffect>()
    val effects = _effects.asSharedFlow()

    fun intent(intent: ApprovalGateUiIntent) {
        when (intent) {
            is ApprovalGateUiIntent.Approve -> approve(intent.notes)
            is ApprovalGateUiIntent.RequestRevision -> requestRevision(intent.notes)
        }
    }

    private fun approve(notes: String?) = viewModelScope.launch {
        val result = jobs.approve(jobId, Decision.Merge, notes)
        result
            .onSuccess { _effects.emit(ApprovalGateUiEffect.NavigateBack) }
            .onFailure { _effects.emit(ApprovalGateUiEffect.Snackbar(it.userMessage)) }
    }
}
```

This is the canonical shape. New screens follow it.
