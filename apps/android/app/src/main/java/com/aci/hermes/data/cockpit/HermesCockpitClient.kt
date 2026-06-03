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

    // ─── Evidence Engine (contract §10d) ─────────────────────────────────

    /** List evidence; an optional `query` runs hybrid retrieval (BM25 + memory).
     *  When a query is sent the server populates `hits` (ranked) over `items`. */
    suspend fun evidenceList(query: String? = null): CockpitResult<CockpitEvidenceList> {
        val path = if (query.isNullOrBlank()) {
            "/v1/cockpit/evidence"
        } else {
            "/v1/cockpit/evidence?q=" + enc(query)
        }
        return request("GET", path, CockpitEvidenceList.serializer())
    }

    /** One evidence artifact by id. */
    suspend fun evidenceDetail(id: String): CockpitResult<CockpitEvidenceDetail> =
        request("GET", "/v1/cockpit/evidence/" + enc(id), CockpitEvidenceDetail.serializer())

    /** Verify claims against evidence: citations, uncertain claims, contradictions. */
    suspend fun evidenceVerify(req: EvidenceVerifyRequest): CockpitResult<CockpitEvidenceVerifyResult> =
        request(
            "POST",
            "/v1/cockpit/evidence/verify",
            CockpitEvidenceVerifyResult.serializer(),
            body = json.encodeToString(EvidenceVerifyRequest.serializer(), req),
        )

    /** Promote evidence to durable memory. Low-confidence promotion needs the
     *  owner [authorization] phrase — otherwise the gateway returns 422 (the
     *  memory write policy is never bypassed). */
    suspend fun evidencePromote(
        id: String,
        authorization: String? = null,
    ): CockpitResult<PromoteEvidenceResponse> =
        request(
            "POST",
            "/v1/cockpit/evidence/" + enc(id) + "/promote",
            PromoteEvidenceResponse.serializer(),
            body = json.encodeToString(
                PromoteEvidenceRequest.serializer(),
                PromoteEvidenceRequest(authorization = authorization),
            ),
        )

    /** Demote (remove) an evidence artifact from the vault. */
    suspend fun evidenceDemote(id: String): CockpitResult<DeleteMemoryResponse> =
        request("DELETE", "/v1/cockpit/evidence/" + enc(id), DeleteMemoryResponse.serializer())
    // ─── Memory Tree (MEM-2): inbox / decisions / contradictions / freshness ──

    /** Ranked, source-cited Memory Tree search (contested excluded by default). */
    suspend fun memoryTreeSearch(
        query: String,
        includeContested: Boolean = false,
    ): CockpitResult<CockpitMemoryNodeList> {
        val sb = StringBuilder("/v1/cockpit/memory/tree?q=").append(enc(query))
        if (includeContested) sb.append("&include_contested=1")
        return request("GET", sb.toString(), CockpitMemoryNodeList.serializer())
    }

    /** The proposed-memory inbox: candidates awaiting an owner decision. */
    suspend fun memoryProposed(): CockpitResult<CockpitMemoryNodeList> =
        request("GET", "/v1/cockpit/memory/tree/proposed", CockpitMemoryNodeList.serializer())

    /** Approve (→ durable) / reject / supersede a proposed node. */
    suspend fun memoryDecision(
        id: String,
        req: MemoryDecisionRequest,
    ): CockpitResult<MemoryDecisionResponse> =
        request(
            "POST",
            "/v1/cockpit/memory/tree/" + enc(id) + "/decision",
            MemoryDecisionResponse.serializer(),
            body = json.encodeToString(MemoryDecisionRequest.serializer(), req),
        )

    /** Open (contested) contradiction reports awaiting resolution. */
    suspend fun memoryContradictions(): CockpitResult<CockpitContradictionList> =
        request("GET", "/v1/cockpit/memory/contradictions", CockpitContradictionList.serializer())

    /** Resolve a contradiction: winner stays, loser is superseded. */
    suspend fun memoryContradictionResolve(
        id: String,
        req: ResolveContradictionRequest,
    ): CockpitResult<ResolveContradictionResponse> =
        request(
            "POST",
            "/v1/cockpit/memory/contradictions/" + enc(id) + "/resolve",
            ResolveContradictionResponse.serializer(),
            body = json.encodeToString(ResolveContradictionRequest.serializer(), req),
        )

    /** Nodes overdue (or within `withinDays`) for a freshness review. */
    suspend fun memoryFreshness(withinDays: Int = 0): CockpitResult<CockpitMemoryNodeList> =
        request(
            "GET",
            "/v1/cockpit/memory/freshness?within_days=$withinDays",
            CockpitMemoryNodeList.serializer(),
        )

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

    // ─── Learning Queue (learning-dataset candidate review) ──────────────
    suspend fun learningList(): CockpitResult<CockpitLearningList> =
        request("GET", "/v1/cockpit/learning", CockpitLearningList.serializer())

    /** Decide a learning candidate. Approve requires the owner [authorization]
     *  phrase (the gateway returns 403 otherwise — owner gate never bypassed). */
    suspend fun learningDecide(
        id: String,
        decision: String,
        authorization: String? = null,
        notes: String? = null,
    ): CockpitResult<CockpitApprovalDecisionResult> =
        request(
            "POST",
            "/v1/cockpit/learning/" + enc(id),
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

    /** Pause a job (human-requested). A `409` means it was already terminal. */
    suspend fun jobPause(id: String, reason: String? = null): CockpitResult<CockpitJob> =
        request(
            "POST",
            "/v1/cockpit/jobs/" + enc(id) + "/pause",
            CockpitJob.serializer(),
            body = json.encodeToString(JobControlRequest.serializer(), JobControlRequest(reason)),
        )

    /** Resume a paused/blocked job. A `409` means it wasn't in a resumable state. */
    suspend fun jobResume(id: String, reason: String? = null): CockpitResult<CockpitJob> =
        request(
            "POST",
            "/v1/cockpit/jobs/" + enc(id) + "/resume",
            CockpitJob.serializer(),
            body = json.encodeToString(JobControlRequest.serializer(), JobControlRequest(reason)),
        )

    // ─── Capabilities / emergency stop ───────────────────────────────────

    /** Negotiate against the live backend (subsystems, lanes, execute guard). */
    suspend fun capabilities(): CockpitResult<ServerCapabilities> =
        request("GET", "/v1/cockpit/capabilities", ServerCapabilities.serializer())

    /** Halt backend work: clear owner gates, release leases, pause live jobs. */
    suspend fun emergencyStop(reason: String? = null): CockpitResult<EmergencyStopResult> =
        request(
            "POST",
            "/v1/cockpit/emergency-stop",
            EmergencyStopResult.serializer(),
            body = json.encodeToString(EmergencyStopRequest.serializer(), EmergencyStopRequest(reason)),
        )

    // ─── Coding lanes (audit / plan / execute) ───────────────────────────

    /** Classify + route a coding request (read-only — builds nothing, runs nothing). */
    suspend fun codingAudit(req: CodingRequest): CockpitResult<CodingAuditResult> =
        request(
            "POST",
            "/v1/cockpit/coding/audit",
            CodingAuditResult.serializer(),
            body = json.encodeToString(CodingRequest.serializer(), req),
        )

    /** Build + validate a bounded work packet (stage only). `422` = invalid packet. */
    suspend fun codingPlan(req: CodingRequest): CockpitResult<CodingPlanResult> =
        request(
            "POST",
            "/v1/cockpit/coding/plan",
            CodingPlanResult.serializer(),
            body = json.encodeToString(CodingRequest.serializer(), req),
        )

    /**
     * Dispatch a coding job through the existing gated orchestrator path.
     * Without the owner [CodingRequest.authorization] phrase the result is a
     * staged `approval_required` (the job is created, pending approval).
     */
    suspend fun codingExecute(req: CodingRequest): CockpitResult<CodingExecuteResult> =
        request(
            "POST",
            "/v1/cockpit/coding/execute",
            CodingExecuteResult.serializer(),
            body = json.encodeToString(CodingRequest.serializer(), req),
        )

    // ─── Evidence (Research Vault) ───────────────────────────────────────

    /** Search the Research Vault (read-only). Honest empty when the vault is empty. */
    suspend fun evidenceSearch(query: String, limit: Int = 10): CockpitResult<EvidenceList> =
        request(
            "GET",
            "/v1/cockpit/evidence/search?q=" + enc(query) + "&limit=" + limit,
            EvidenceList.serializer(),
        )
    // ─── GraphRAG knowledge graph (contract: /v1/cockpit/graph/*) ────────

    /**
     * Related files / sources / decisions for an entity. Pass exactly one of
     * [jobId] / [memoryId] / [evidenceId] / [node]. Honest empty when the
     * entity isn't in the graph yet.
     */
    suspend fun graphRelated(
        jobId: String? = null,
        memoryId: String? = null,
        evidenceId: String? = null,
        node: String? = null,
    ): CockpitResult<RelatedItemList> {
        val params = buildList {
            jobId?.takeIf { it.isNotBlank() }?.let { add("job_id=" + enc(it)) }
            memoryId?.takeIf { it.isNotBlank() }?.let { add("memory_id=" + enc(it)) }
            evidenceId?.takeIf { it.isNotBlank() }?.let { add("evidence_id=" + enc(it)) }
            node?.takeIf { it.isNotBlank() }?.let { add("node=" + enc(it)) }
        }
        val q = if (params.isEmpty()) "" else "?" + params.joinToString("&")
        return request("GET", "/v1/cockpit/graph/related$q", RelatedItemList.serializer())
    }

    /** Run a GraphRAG query (mode = local | global | coding). */
    suspend fun graphQuery(question: String, mode: String = "coding"): CockpitResult<GraphAnswer> =
        request(
            "GET",
            "/v1/cockpit/graph/query?mode=" + enc(mode) + "&q=" + enc(question),
            GraphAnswer.serializer(),
        )

    /** Rebuild + persist the knowledge-graph cache. Read-only over the repo
     *  and local stores (not an owner-gated action). */
    suspend fun graphBuild(): CockpitResult<GraphBuildResult> =
        request("POST", "/v1/cockpit/graph/build", GraphBuildResult.serializer())

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
