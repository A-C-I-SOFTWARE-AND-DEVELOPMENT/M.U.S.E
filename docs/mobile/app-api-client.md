# Mobile cockpit — API client

> One typed entry point for every call to a M.U.S.E. gateway. The wire
> format is fixed by
> [`docs/android/muse-apk-api-contract.md`](../android/muse-apk-api-contract.md);
> this file specifies the **client implementation** that maps that
> contract into Kotlin.

## 1. Surface

```kotlin
// data/api/CockpitClient.kt
interface CockpitClient {
    suspend fun health(): Result<HealthResponse, CockpitError>

    // Workers + runtime
    suspend fun runtimeStatus(): Result<RuntimeStatus, CockpitError>
    suspend fun workers(kind: WorkerKind? = null): Result<List<Worker>, CockpitError>

    // Jobs
    suspend fun jobs(filter: JobFilter, page: Cursor?): Result<Page<JobSummary>, CockpitError>
    suspend fun job(id: JobId): Result<JobDetail, CockpitError>
    suspend fun dispatchJob(draft: PromptDraft, idempotencyKey: String): Result<JobId, CockpitError>
    fun jobsStream(filter: JobFilter): Flow<JobStreamEvent>

    // Tree + diff
    suspend fun tree(id: JobId, path: String): Result<TreeListing, CockpitError>
    suspend fun file(id: JobId, path: String): Result<FilePreview, CockpitError>
    suspend fun diff(id: JobId): Result<UnifiedDiff, CockpitError>
    suspend fun filesChanged(id: JobId): Result<List<FileChange>, CockpitError>

    // Gates
    suspend fun validation(id: JobId): Result<ValidationReport, CockpitError>
    suspend fun revalidate(id: JobId, idempotencyKey: String): Result<Unit, CockpitError>
    suspend fun override(id: JobId, note: String, idempotencyKey: String): Result<Unit, CockpitError>
    suspend fun approveJob(id: JobId, decision: Decision, notes: String?, idempotencyKey: String): Result<Unit, CockpitError>

    // Publish + deploy
    suspend fun publishPreview(id: JobId): Result<PublishPreview, CockpitError>
    suspend fun publish(id: JobId, req: PublishRequest, idempotencyKey: String): Result<PublishResult, CockpitError>
    suspend fun deployPlan(id: JobId): Result<DeployPlan, CockpitError>
    suspend fun deployApply(id: JobId, idempotencyKey: String): Result<DeployResult, CockpitError>

    // Ledger + events
    suspend fun ledger(id: JobId, since: Instant?): Result<List<LedgerEntry>, CockpitError>
    fun ledgerStream(id: JobId): Flow<LedgerEntry>
    suspend fun events(since: Instant?, levels: Set<Level>, sources: Set<Source>): Result<List<EventRow>, CockpitError>
    fun eventStream(levels: Set<Level>, sources: Set<Source>): Flow<EventRow>
}
```

The interface is intentionally small. Every screen depends on a
**repository**, not the client directly; this makes mock mode and
replay testing trivial.

## 2. Implementation: `OkHttpCockpitClient`

- **Transport:** OkHttp + OkHttp-SSE (already in the existing
  `app/build.gradle.kts`).
- **Serialisation:** `kotlinx.serialization.json.Json {
    ignoreUnknownKeys = true
    explicitNulls = false
  }`.
- **Base URL** comes from `SettingsRepository.gatewayUrl()`. It is
  resolved per request (so changing the URL in Settings does not
  require a process restart), but the `OkHttpClient` itself is a
  singleton.
- **Auth:** an `Interceptor` reads the bearer token from
  `EncryptedSharedPreferences` and adds
  `Authorization: Bearer <token>` to every cockpit route. The
  interceptor short-circuits with a `401 Local` envelope if no token
  is set, so screens get the same error shape regardless of cause.

## 3. Error envelope

The gateway error envelope is mapped to `CockpitError`:

```kotlin
sealed interface CockpitError {
    data class Validation(val field: String, val message: String) : CockpitError
    data class Auth(val message: String) : CockpitError              // 401
    data class Policy(val message: String) : CockpitError            // 403
    data class NotFound(val message: String) : CockpitError          // 404
    data class StateMismatch(val message: String) : CockpitError     // 409
    data class Server(val code: String, val message: String) : CockpitError
    data class Network(val cause: IOException) : CockpitError
    data class Cancelled(val message: String) : CockpitError
    data class Unknown(val message: String) : CockpitError
}
```

Reasons to keep this typed:

- Screens branch on shape, not string match.
- TalkBack and error analytics surfaces have stable labels.
- The Approval Gate's "*This job moved to <state>*" recovery path
  depends on `StateMismatch` being identifiable.

`CockpitError.userMessage` returns a localised, screen-safe summary.
Raw `Throwable` messages are never displayed.

## 4. Retries

The cockpit retries network failures conservatively. The matrix:

| Verb | Idempotent? | Retry policy |
|---|---|---|
| `GET` | yes | 3 attempts, exponential backoff `0.5s → 2s → 5s` |
| `POST` with `Idempotency-Key` | yes from server's POV | 3 attempts, same backoff |
| `POST` without `Idempotency-Key` | no | **no automatic retry** |
| SSE connect | yes | exponential backoff `2s → 4s → 8s → 16s → 30s cap` |

Retries only happen for **transport** errors and `5xx`. `4xx`
responses bubble up immediately. The retrier never reads the
response body to decide whether to retry — only the status code and
the absence of a body for transport failures.

## 5. Idempotency keys

```kotlin
// data/api/IdempotencyKeys.kt
object IdempotencyKeys {
    fun forDispatch(): String = "dispatch:${UUID.randomUUID()}"
    fun forApprove(jobId: JobId): String = "approve:$jobId:${UUID.randomUUID()}"
    fun forPublish(jobId: JobId): String = "publish:$jobId:${UUID.randomUUID()}"
    fun forOverride(jobId: JobId): String = "override:$jobId:${UUID.randomUUID()}"
}
```

Every write-issuing repository:

1. Generates the key once when the user **first** taps the action.
2. Passes the same key through retries until the call either succeeds
   or is cancelled by the user.
3. Hands the key to `OfflineQueueRepository` if the call is queued
   for later replay, so a replay does not create a duplicate.

The Phase 18 API contract guarantees the gateway stores the result
for at least 24 h keyed on `(token, key)`. The cockpit takes that as
load-bearing.

## 6. SSE handling

OkHttp-SSE returns an `EventSource`. The client wraps it as a
`Flow<…>`:

```kotlin
internal fun <T> sseFlow(
    request: Request,
    parse: (String) -> T,
): Flow<T> = callbackFlow {
    val listener = object : EventSourceListener() {
        override fun onEvent(es: EventSource, id: String?, type: String?, data: String) {
            trySend(parse(data))
        }
        override fun onClosed(es: EventSource) { close() }
        override fun onFailure(es: EventSource, t: Throwable?, r: Response?) {
            close(t ?: IOException("SSE closed"))
        }
    }
    val source = EventSources.createFactory(okHttp).newEventSource(request, listener)
    awaitClose { source.cancel() }
}
.retryWhen { cause, attempt ->
    if (cause !is CancellationException) {
        delay(min(2.seconds * (1 shl attempt.toInt().coerceAtMost(4)), 30.seconds))
        true
    } else false
}
```

Repositories augment this flow with a `StreamState` channel
(`Connecting / Live / Reconnecting / Paused`) consumed by every
screen's top-bar pill — the cockpit's *never hide agent state* rule
in action.

## 7. Offline queueing

When a write fails with a `Network` error and an idempotency key was
attached, `CockpitClient` does **not** queue it. The decision to
queue lives in the repository, which owns the local optimistic
write into the decision ledger:

```kotlin
suspend fun approve(jobId: JobId, decision: Decision, notes: String?): Result<Unit, CockpitError> {
    val key = IdempotencyKeys.forApprove(jobId)
    ledgerCache.markPending(jobId, key, decision, notes)
    return client.approveJob(jobId, decision, notes, key)
        .onFailure { err ->
            if (err is CockpitError.Network) {
                offline.enqueue(approveWrite(jobId, decision, notes, key))
            } else {
                ledgerCache.markFailed(jobId, key, err)
            }
        }
        .onSuccess { ledgerCache.markConfirmed(jobId, key) }
}
```

Reading: `client` is dumb, `repository` is policy. The queue is
drained by `HermesService` — see
[`app-background-service.md`](app-background-service.md).

## 8. Mock mode

```kotlin
class MockCockpitClient : CockpitClient {
    // Hard-coded JSON in src/main/assets/mocks/cockpit/
    // Loaded by FixtureLoader on first access, then served from
    // an in-memory map so the cockpit feels fast.
}
```

`AppContainer.cockpitClient` returns the mock when
`SettingsRepository.mockMode().value == true`. Both implementations
satisfy `CockpitClient` byte-for-byte at the type level, so screens
cannot tell the difference.

Mock-mode features that exist primarily for demos:

- **Time-travel fixtures**: a fixture file can declare
  `{"frames": [...]}` to simulate a job moving through queued →
  running → waiting → done at a deterministic cadence.
- **Failure injection**: `?mockFail=approve:409` query param in the
  current URL triggers a `StateMismatch` on the next approval —
  useful for testing the recovery path without a backend.

## 9. Versioning

The gateway exposes `version` on `/v1/health`. The cockpit:

- Records the observed version on every successful `health()`.
- Renders it on the **Settings → About** card.
- If the gateway version is older than the cockpit's "minimum
  understood gateway version" (a const in `BuildConfig`), shows a
  *Upgrade your M.U.S.E. gateway* banner on every screen rather than
  silently failing on routes the gateway doesn't have.
- If the gateway version is **newer**, the cockpit assumes additive
  changes and proceeds. Unknown JSON fields are ignored by the
  serialiser.

## 10. Test plan

- **Replay tests** in `apps/android/app/src/test/resources/cockpit/`
  hold golden JSON for every endpoint. A new endpoint without a
  fixture fails CI.
- **Retry tests** assert that a `503` retried three times and then
  succeeded does *not* create a duplicate on the server-side
  bookkeeping (we stub `OkHttp.dispatcher` to count requests).
- **SSE reconnect tests** assert backoff exponent and cap.
- **Idempotency key tests** assert that a key generated for a tap is
  reused across all retries and into the offline queue.

## 11. Anti-patterns

- Calling `CockpitClient` from a `@Composable`. Never. Compose calls
  view-models; view-models call repositories; repositories call the
  client.
- Mapping `Throwable.message` to a UI string. Use `CockpitError`.
- Adding a third HTTP method shape. Stay with `suspend` for unary
  and `Flow<T>` for streams.
- Sharing an `OkHttpClient` across the whole APK without an explicit
  timeout matrix. The cockpit's timeouts are:
  `connect = 8s, read = 30s, write = 30s, callTimeout = 60s`. SSE
  uses `readTimeout = 0` (infinite) on its own dedicated client to
  avoid disturbing unary calls.
