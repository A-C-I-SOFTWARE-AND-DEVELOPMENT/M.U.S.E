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

    // ─── Memory (contract §10a) ──────────────────────────────────────────

    /** List memory items; optional `query` runs server-side recollection. */
    suspend fun memoryList(query: String? = null): CockpitResult<CockpitMemoryList> {
        val path = if (query.isNullOrBlank()) {
            "/v1/cockpit/memory"
        } else {
            "/v1/cockpit/memory?q=" + enc(query)
        }
        return request("GET", path, CockpitMemoryList.serializer())
    }

    /** Create a memory item. A `422 unprocessable` Failure means the store
     *  rejected it (secret-like / low confidence) — honest, not an error. */
    suspend fun memoryCreate(req: CreateMemoryRequest): CockpitResult<CreateMemoryResponse> =
        request(
            "POST",
            "/v1/cockpit/memory",
            CreateMemoryResponse.serializer(),
            body = json.encodeToString(CreateMemoryRequest.serializer(), req),
        )

    /** Delete a memory item by id (== store key). */
    suspend fun memoryDelete(id: String): CockpitResult<DeleteMemoryResponse> =
        request("DELETE", "/v1/cockpit/memory/" + enc(id), DeleteMemoryResponse.serializer())

    // ─── Avatar persona ("make my avatar Goku") ──────────────────────────

    /** The companion's adopted persona, or an empty one if default. */
    suspend fun personaGet(): CockpitResult<CockpitPersona> =
        request("GET", "/v1/cockpit/avatar/persona", CockpitPersona.serializer())

    /** Adopt a persona from a description — the model researches the character
     *  and the companion speaks in-character. Empty description clears it. */
    suspend fun personaSet(req: SetPersonaRequest): CockpitResult<CockpitPersona> =
        request(
            "POST",
            "/v1/cockpit/avatar/persona",
            CockpitPersona.serializer(),
            body = json.encodeToString(SetPersonaRequest.serializer(), req),
        )

    // ─── Room editor (AI-generated furniture) ────────────────────────────

    /** The companion's room items (with base64 images) + whether image-gen is on. */
    suspend fun roomList(): CockpitResult<CockpitRoomList> =
        request("GET", "/v1/cockpit/avatar/room", CockpitRoomList.serializer())

    /** Generate a room item from a prompt ('a Victorian desk'). 503 if no image
     *  model is configured. */
    suspend fun roomGenerate(req: GenerateRoomRequest): CockpitResult<CockpitRoomItem> =
        request(
            "POST",
            "/v1/cockpit/avatar/room",
            CockpitRoomItem.serializer(),
            body = json.encodeToString(GenerateRoomRequest.serializer(), req),
        )

    /** Persist a furniture item's normalized (x, y) placement in the room. */
    suspend fun roomPlace(id: String, x: Float, y: Float): CockpitResult<JsonObject> =
        request(
            "POST",
            "/v1/cockpit/avatar/room/" + enc(id) + "/place",
            JsonObject.serializer(),
            body = json.encodeToString(PlaceItemRequest.serializer(), PlaceItemRequest(x, y)),
        )

    // ─── Approvals (contract §10c) ───────────────────────────────────────

    suspend fun approvalsList(): CockpitResult<CockpitApprovalCardList> =
        request("GET", "/v1/cockpit/approvals", CockpitApprovalCardList.serializer())

    /** Decide an approval. Approve requires the owner [authorization] phrase
     *  (the gateway returns 403 otherwise — the owner gate is never bypassed). */
    suspend fun approvalsDecide(
        id: String,
        decision: String,
        authorization: String? = null,
        notes: String? = null,
    ): CockpitResult<CockpitApprovalDecisionResult> =
        request(
            "POST",
            "/v1/cockpit/approvals/" + enc(id),
            CockpitApprovalDecisionResult.serializer(),
            body = json.encodeToString(
                CockpitApprovalDecision.serializer(),
                CockpitApprovalDecision(decision = decision, authorization = authorization, notes = notes),
            ),
        )

    // ─── Audit (contract §10b) ───────────────────────────────────────────
    suspend fun auditList(): CockpitResult<CockpitAuditList> =
        request("GET", "/v1/cockpit/audit", CockpitAuditList.serializer())

    suspend fun auditProof(id: String): CockpitResult<CockpitProofRecord> =
        request("GET", "/v1/cockpit/audit/" + enc(id) + "/proof", CockpitProofRecord.serializer())

    // ─── Jobs (contract §4) ──────────────────────────────────────────────
    suspend fun jobsList(): CockpitResult<JobList> =
        request("GET", "/v1/cockpit/jobs", JobList.serializer())

    suspend fun jobGet(id: String): CockpitResult<CockpitJob> =
        request("GET", "/v1/cockpit/jobs/" + enc(id), CockpitJob.serializer())

    /** Dispatch (enqueue) a new job. Returns the created job (201). */
    suspend fun jobDispatch(req: DispatchJobRequest): CockpitResult<CockpitJob> =
        request(
            "POST",
            "/v1/cockpit/jobs",
            CockpitJob.serializer(),
            body = json.encodeToString(DispatchJobRequest.serializer(), req),
        )

    /** Cancel a job. A `409 conflict` Failure means it was already terminal. */
    suspend fun jobCancel(id: String, reason: String? = null): CockpitResult<CockpitJob> =
        request(
            "POST",
            "/v1/cockpit/jobs/" + enc(id) + "/cancel",
            CockpitJob.serializer(),
            body = json.encodeToString(CancelJobRequest.serializer(), CancelJobRequest(reason)),
        )

    /**
     * Run a job on a worker via the orchestrator's gated contract. Execute
     * lanes (whose worker `requires_approval`) need the exact owner
     * [authorization] phrase — the gateway returns `403` otherwise, and refuses
     * entirely on a non-loopback cockpit. Returns the advanced job plus its
     * worker ledger trail. The owner gate is never bypassed client-side.
     */
    suspend fun jobRun(
        id: String,
        workerId: String,
        authorization: String? = null,
    ): CockpitResult<RunJobResult> =
        request(
            "POST",
            "/v1/cockpit/jobs/" + enc(id) + "/run",
            RunJobResult.serializer(),
            body = json.encodeToString(
                RunJobRequest.serializer(),
                RunJobRequest(workerId = workerId, authorization = authorization),
            ),
        )

    /** The runnable worker lanes `job_run` accepts (the dispatch/run picker source). */
    suspend fun jobLanes(): CockpitResult<JobLaneList> =
        request("GET", "/v1/cockpit/jobs/lanes", JobLaneList.serializer())

    /**
     * Create a real **orchestrator** job from a prompt (`POST /v1/cockpit/orchestrate`).
     * Unlike [jobDispatch] (a JobQueue entry that [jobRun] can't run), this job is
     * immediately runnable. Spawns nothing — running is a separate gated [jobRun].
     */
    suspend fun orchestrate(prompt: String): CockpitResult<CockpitJob> =
        request(
            "POST",
            "/v1/cockpit/orchestrate",
            CockpitJob.serializer(),
            body = json.encodeToString(OrchestrateRequest.serializer(), OrchestrateRequest(prompt)),
        )

    private fun enc(value: String): String =
        java.net.URLEncoder.encode(value, "UTF-8")

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
