package com.aci.hermes.data.cockpit

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.DeserializationStrategy
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject

/**
 * Live client for the Hermes cockpit API (the piece the contract's §12
 * "SDK shape" calls for). Reaches the loopback gateway stood up by
 * `gateway/cockpit/server.py` (`hermes cockpit serve`).
 *
 * Responsibilities, per the contract:
 *  - attach the paired bearer token to every authenticated route,
 *  - decode the error envelope into a typed [CockpitError],
 *  - use the short health-probe timeout so the UI can show
 *    *Backend unreachable* quickly,
 *  - never surface a fabricated value — an unreachable or unpaired
 *    gateway returns [CockpitResult.Unreachable], not a stub.
 *
 * Endpoint and token are read through providers (not captured at
 * construction) so the client picks up *Settings → Connection* changes
 * and the pairing flow without being rebuilt. Transport is injectable
 * ([executor]) so the request/response mapping is unit-tested without a
 * socket.
 *
 * Scope note: this lands the negotiation + detection reads that the
 * gateway actually serves today (health, runtime status, worker
 * detection) plus a generic [getRaw] passthrough for routes whose typed
 * models are still being reconciled with the live server. Typed
 * memory/events/approvals accessors follow as those server shapes
 * stabilise — this file is the transport every one of them builds on.
 */
class HermesCockpitClient(
    private val endpointProvider: () -> String,
    private val tokenProvider: () -> String?,
    private val executor: CockpitHttpExecutor = JdkHttpExecutor,
    private val json: Json = CockpitHttp.json,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) {

    /** True once the user has paired a token and an endpoint is set. */
    fun isPaired(): Boolean =
        !tokenProvider().isNullOrBlank() && endpointProvider().isNotBlank()

    /** Unauthenticated liveness + version probe. Used for negotiation (contract §11). */
    suspend fun health(): CockpitResult<HealthStatus> =
        request(
            method = "GET",
            path = "/v1/health",
            deserializer = HealthStatus.serializer(),
            requiresAuth = false,
            timeoutMs = CockpitHttp.HEALTH_TIMEOUT_MS,
        )

    /** Live runtime status: gateway, host, queue snapshot (contract §3). */
    suspend fun runtimeStatus(): CockpitResult<RuntimeStatus> =
        request("GET", "/v1/cockpit/runtime/status", RuntimeStatus.serializer())

    /** Detected worker lanes (Claude Code / Codex / internal) — detection only (contract §3). */
    suspend fun runtimeWorkers(): CockpitResult<WorkerDetectionList> =
        request("GET", "/v1/cockpit/runtime/workers", WorkerDetectionList.serializer())

    /**
     * Generic authenticated GET for routes without a settled typed model
     * yet (memory, events, approvals, jobs, sessions). Returns the raw
     * [JsonObject] so a screen can project the fields it needs while the
     * contract and the server converge. Prefer a typed accessor once one
     * exists.
     */
    suspend fun getRaw(path: String): CockpitResult<JsonObject> =
        request("GET", path, JsonObject.serializer())

    // ─── internals ──────────────────────────────────────────────────────

    private suspend fun <T> request(
        method: String,
        path: String,
        deserializer: DeserializationStrategy<T>,
        requiresAuth: Boolean = true,
        body: String? = null,
        timeoutMs: Int = CockpitHttp.DEFAULT_READ_TIMEOUT_MS,
    ): CockpitResult<T> = withContext(ioDispatcher) {
        val endpoint = endpointProvider().trim()
        if (endpoint.isBlank()) {
            return@withContext CockpitResult.Unreachable("No gateway endpoint configured")
        }
        val token = if (requiresAuth) tokenProvider() else null
        if (requiresAuth && token.isNullOrBlank()) {
            return@withContext CockpitResult.Unreachable("Not paired with a gateway (no token)")
        }

        val httpRequest = CockpitRequest(
            method = method,
            url = CockpitHttp.joinUrl(endpoint, path),
            headers = CockpitHttp.headers(token),
            body = body,
            connectTimeoutMs = minOf(timeoutMs, CockpitHttp.DEFAULT_CONNECT_TIMEOUT_MS),
            readTimeoutMs = timeoutMs,
        )

        val raw = try {
            executor.execute(httpRequest)
        } catch (e: Exception) {
            return@withContext CockpitResult.Unreachable(e.message ?: "Gateway unreachable")
        }

        if (raw.status in 200..299) {
            val value = try {
                json.decodeFromString(deserializer, raw.body)
            } catch (e: Exception) {
                return@withContext CockpitResult.Unreachable("Malformed response: ${e.message}")
            }
            CockpitResult.Success(value)
        } else {
            CockpitResult.Failure(CockpitHttp.parseError(json, raw.status, raw.body), raw.status)
        }
    }
}
