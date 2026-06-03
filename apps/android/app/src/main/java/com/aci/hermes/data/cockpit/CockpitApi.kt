package com.aci.hermes.data.cockpit

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Phase 18 cockpit API contract — Kotlin mirror.
 *
 * One-to-one with the JSON shapes in
 * docs/android/hermes-apk-api-contract.md. Adding fields here without
 * updating that doc (and vice versa) is the failure mode this file
 * exists to prevent.
 *
 * Nothing here makes network calls. The live `HermesCockpitClient` is
 * a separate class that lands with the cockpit-screen implementation.
 */

// ─── Health ───────────────────────────────────────────────────────────

/**
 * Response of `GET /v1/health` — the negotiation entrypoint (contract
 * §2/§11). Fields are tolerant of contract drift: the live gateway
 * (`gateway/cockpit/handlers.py`) returns `service` / `api_version` /
 * `gateway_version`, while the older spec variant used `version` /
 * `message`. Both are accepted; absent fields stay null.
 */
@Serializable
data class HealthStatus(
    val ok: Boolean = false,
    val service: String? = null,
    @SerialName("api_version") val apiVersion: String? = null,
    @SerialName("gateway_version") val gatewayVersion: String? = null,
    val time: String? = null,
    // Older spec variant (kept so a pre-cockpit gateway still negotiates).
    val version: String? = null,
    val message: String? = null,
) {
    /** Best-effort gateway version across both response variants. */
    val resolvedVersion: String?
        get() = gatewayVersion ?: version
}

// ─── Runtime ──────────────────────────────────────────────────────────

@Serializable
data class RuntimeStatus(
    val gateway: GatewayRuntime,
    val host: HostInfo,
    val queue: QueueSnapshot,
)

@Serializable
data class GatewayRuntime(
    val version: String,
    @SerialName("started_at") val startedAt: String,
    val pid: Long? = null,
    val mode: String,
)

@Serializable
data class HostInfo(
    val platform: String,
    val arch: String,
    val hostname: String,
)

@Serializable
data class QueueSnapshot(
    val running: Int,
    val queued: Int,
    @SerialName("waiting_approval") val waitingApproval: Int,
)

@Serializable
data class WorkerDetectionList(val workers: List<DetectedWorker>)

@Serializable
data class DetectedWorker(
    val id: String,
    @SerialName("display_name") val displayName: String,
    val kind: String,
    val available: Boolean,
    val version: String? = null,
    val path: String? = null,
    val notes: String? = null,
)

// ─── Jobs ─────────────────────────────────────────────────────────────

@Serializable
data class CockpitJob(
    val id: String,
    val title: String,
    @SerialName("worker_id") val workerId: String,
    val status: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("workspace_path") val workspacePath: String? = null,
    val branch: String? = null,
    @SerialName("base_branch") val baseBranch: String? = null,
    val remote: String? = null,
    @SerialName("validation_summary") val validationSummary: ValidationSummary? = null,
    @SerialName("publish_state") val publishState: String? = null,
)

@Serializable
data class ValidationSummary(
    val pass: Int,
    val fail: Int,
    val pending: Int,
)

@Serializable
data class JobList(
    val jobs: List<CockpitJob>,
    @SerialName("next_cursor") val nextCursor: String? = null,
    @SerialName("prev_cursor") val prevCursor: String? = null,
)

@Serializable
data class DispatchJobRequest(
    val title: String,
    @SerialName("worker_id") val workerId: String,
    val prompt: String,
    @SerialName("workspace_path") val workspacePath: String? = null,
    @SerialName("branch_hint") val branchHint: String? = null,
    val watch: Boolean = false,
)

@Serializable
data class CancelJobRequest(val reason: String? = null)

/**
 * POST body for `jobs/{id}/run`. An execute lane (one whose worker
 * `requires_approval`) only runs when [authorization] equals the exact owner
 * phrase; the gateway returns `403` otherwise — and refuses entirely on a
 * non-loopback cockpit. Non-gated lanes (local planner / handoff) ignore it.
 */
@Serializable
data class RunJobRequest(
    @SerialName("worker_id") val workerId: String,
    val authorization: String? = null,
)

/**
 * Result of `jobs/{id}/run` — the (advanced) job plus the tail of its worker
 * ledger trail. `worker_trail` entries are free-form ledger dicts; only the
 * fields the cockpit renders are modelled (the tolerant decoder ignores the
 * rest).
 */
@Serializable
data class RunJobResult(
    val job: CockpitJob? = null,
    @SerialName("worker_trail") val workerTrail: List<WorkerTrailEntry> = emptyList(),
)

@Serializable
data class WorkerTrailEntry(
    val kind: String = "",
    @SerialName("worker_id") val workerId: String? = null,
    val summary: String? = null,
)

/**
 * A **runnable** worker lane (`GET /v1/cockpit/jobs/lanes`) — the ids
 * `job_run` actually accepts (e.g. `codex-execute`, `hermes-local-planner`),
 * NOT the detection lanes from `runtime/workers`. [requiresApproval] tells the
 * UI which lanes need the owner phrase before running.
 */
@Serializable
data class JobLane(
    val id: String,
    @SerialName("display_name") val displayName: String = "",
    @SerialName("requires_approval") val requiresApproval: Boolean = true,
)

@Serializable
data class JobLaneList(val lanes: List<JobLane> = emptyList())

/** POST body for `/v1/cockpit/orchestrate` — create a runnable orchestrator job. */
@Serializable
data class OrchestrateRequest(val prompt: String)

// ─── Files ────────────────────────────────────────────────────────────

@Serializable
data class TreeListing(
    val path: String,
    val entries: List<TreeEntry>,
)

@Serializable
data class TreeEntry(
    val name: String,
    val kind: String,
    val size: Long? = null,
    val mtime: String? = null,
)

@Serializable
data class FileSnapshot(
    val path: String,
    val size: Long,
    val truncated: Boolean,
    val content: String? = null,
    val encoding: String? = null,
)

// ─── Diff and approval ────────────────────────────────────────────────

@Serializable
data class DiffSnapshot(
    val files: List<DiffFile>,
    val diff: String,
    val truncated: Boolean,
)

@Serializable
data class DiffFile(
    val path: String,
    val additions: Int,
    val deletions: Int,
)

@Serializable
data class ApproveJobRequest(
    val decision: String,
    val notes: String? = null,
    @SerialName("decided_at") val decidedAt: String,
    @SerialName("decided_by") val decidedBy: String = "cockpit",
)

// ─── Validation ───────────────────────────────────────────────────────

@Serializable
data class ValidationSnapshot(
    val gates: List<ValidationGate>,
    val policy: ValidationPolicy,
)

@Serializable
data class ValidationGate(
    val id: String,
    val name: String,
    val status: String,
    val summary: String? = null,
    @SerialName("log_excerpt") val logExcerpt: String? = null,
    @SerialName("override_allowed") val overrideAllowed: Boolean = false,
)

@Serializable
data class ValidationPolicy(
    @SerialName("all_must_pass") val allMustPass: Boolean,
    @SerialName("override_requires_note") val overrideRequiresNote: Boolean,
)

@Serializable
data class OverrideValidationRequest(
    @SerialName("gate_ids") val gateIds: List<String>,
    val note: String,
)

// ─── Publishing ───────────────────────────────────────────────────────

@Serializable
data class PublishPreview(
    val remote: String,
    val branch: String,
    val base: String,
    val commits: List<PublishCommit>,
    @SerialName("default_title") val defaultTitle: String,
    @SerialName("default_body") val defaultBody: String,
    @SerialName("existing_pr_url") val existingPrUrl: String? = null,
)

@Serializable
data class PublishCommit(
    val sha: String,
    val subject: String,
)

@Serializable
data class PublishRequest(
    val title: String,
    val body: String,
    val draft: Boolean,
    val base: String? = null,
)

@Serializable
data class PublishResult(
    @SerialName("pr_url") val prUrl: String,
    @SerialName("pr_number") val prNumber: Int,
    val branch: String,
    val remote: String,
    val state: String,
    @SerialName("is_draft") val isDraft: Boolean,
)

// ─── Events ───────────────────────────────────────────────────────────

@Serializable
data class EventBatch(
    val events: List<CockpitEvent>,
    @SerialName("next_cursor") val nextCursor: String? = null,
)

@Serializable
data class CockpitEvent(
    val ts: String,
    val level: String,
    val source: String,
    @SerialName("job_id") val jobId: String? = null,
    val message: String,
    val attributes: Map<String, String>? = null,
)

// ─── Destructive approvals ────────────────────────────────────────────

@Serializable
data class ApprovalList(val approvals: List<PendingApproval>)

@Serializable
data class PendingApproval(
    val id: String,
    @SerialName("job_id") val jobId: String,
    val kind: String,
    val summary: String,
    val details: Map<String, String>? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
)

@Serializable
data class DecideApprovalRequest(
    val decision: String,
    val notes: String? = null,
)

// ─── Memory ───────────────────────────────────────────────────────────

/**
 * Wire model for a cockpit memory item (contract §10a). One-to-one with
 * the server's canonical `MemoryItem`. Enum-like fields are raw Strings
 * here so an unknown future value never crashes deserialisation; the
 * repository maps them to the typed domain
 * [com.aci.hermes.data.memory.MemoryItem]. Timestamps are ISO-8601 UTC.
 */
@Serializable
data class CockpitMemoryItem(
    val id: String,
    val category: String,
    val title: String,
    val content: String,
    val durability: String,
    val confidence: String,
    val provenance: CockpitMemoryProvenance,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
    @SerialName("last_accessed_at") val lastAccessedAt: String? = null,
    val tags: List<String> = emptyList(),
    val redacted: Boolean = false,
    val hidden: Boolean = false,
)

@Serializable
data class CockpitMemoryProvenance(
    val source: String,
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("recorded_at") val recordedAt: String? = null,
    val note: String? = null,
)

@Serializable
data class CockpitMemoryList(val items: List<CockpitMemoryItem> = emptyList())

/** POST body for creating memory (canonical fields). */
@Serializable
data class CreateMemoryRequest(
    val title: String,
    val content: String,
    val category: String? = null,
    val durability: String? = null,
    val confidence: String? = null,
    val tags: List<String> = emptyList(),
    val hidden: Boolean = false,
)

@Serializable
data class CreateMemoryResponse(
    val stored: Boolean = false,
    val item: CockpitMemoryItem? = null,
    val reason: String? = null,
)

@Serializable
data class DeleteMemoryResponse(val removed: Int = 0)

// ─── Evidence Engine (contract §10d) ──────────────────────────────────

/**
 * Wire model for a cockpit evidence artifact (contract §10d). One-to-one
 * with the server's `evidence_card` projection of a Research Vault
 * `ResearchArtifact`. Distinct from [CockpitEvidenceItem] (which is an
 * audit-proof sub-record). Enum-like fields are raw Strings so an unknown
 * future value never crashes deserialisation; timestamps are ISO-8601 UTC.
 */
@Serializable
data class CockpitEvidenceCard(
    val id: String,
    val title: String = "",
    @SerialName("source_uri") val sourceUri: String = "",
    @SerialName("source_type") val sourceType: String = "",
    @SerialName("evidence_strength") val evidenceStrength: String = "",
    val trust: String = "unverified",
    val excerpt: String = "",
    val summary: String = "",
    val tags: List<String> = emptyList(),
    @SerialName("license_notes") val licenseNotes: String = "",
    @SerialName("retrieved_at") val retrievedAt: String? = null,
    @SerialName("freshness_due") val freshnessDue: String? = null,
    val checksum: String = "",
    @SerialName("citation_anchors") val citationAnchors: List<String> = emptyList(),
    @SerialName("added_at") val addedAt: String? = null,
)

@Serializable
data class CockpitEvidenceList(
    val items: List<CockpitEvidenceCard> = emptyList(),
    val hits: List<CockpitEvidenceHit> = emptyList(),
)

@Serializable
data class CockpitEvidenceDetail(val item: CockpitEvidenceCard? = null)

/** One ranked retrieval hit from `GET /evidence?q=` or the verify endpoint. */
@Serializable
data class CockpitEvidenceHit(
    val kind: String = "",
    val title: String = "",
    val uri: String = "",
    val excerpt: String = "",
    val trust: String = "unverified",
    val score: Float = 0f,
    @SerialName("artifact_id") val artifactId: String? = null,
    @SerialName("citation_anchors") val citationAnchors: List<String> = emptyList(),
)

@Serializable
data class EvidenceVerifyRequest(
    val claims: List<String>,
    val query: String? = null,
)

@Serializable
data class CockpitEvidenceVerifyResult(
    val citations: List<CockpitClaimCitation> = emptyList(),
    val uncertain: List<String> = emptyList(),
    val contradictions: List<CockpitContradiction> = emptyList(),
    val rejected: List<String> = emptyList(),
)

@Serializable
data class CockpitClaimCitation(
    val claim: String = "",
    val supported: Boolean = false,
    val hits: List<CockpitEvidenceHit> = emptyList(),
)

@Serializable
data class CockpitContradiction(
    val subject: String = "",
    val a: String = "",
    val b: String = "",
    val reason: String = "",
)

/** POST body for `evidence/{id}/promote` — owner phrase gates durable writes. */
@Serializable
data class PromoteEvidenceRequest(val authorization: String? = null)

@Serializable
data class PromoteEvidenceResponse(
    val promoted: Boolean = false,
    @SerialName("node_id") val nodeId: String? = null,
    val reasons: List<String> = emptyList(),
    val hint: String? = null,
)

// ─── Audit ────────────────────────────────────────────────────────────

/**
 * Wire models for the cockpit audit surface (contract §10b). One-to-one
 * with the server's canonical `AuditRecord` / `ProofRecord`. Enum-like
 * fields are raw Strings; the repository maps them to the typed domain
 * models in `com.aci.hermes.data.model.audit`. Timestamps are ISO-8601.
 */
@Serializable
data class CockpitAuditList(val records: List<CockpitAuditRecord> = emptyList())

@Serializable
data class CockpitAuditRecord(
    val id: String,
    val timestamp: String? = null,
    @SerialName("user_request") val userRequest: String = "",
    val action: String = "",
    @SerialName("risk_tier") val riskTier: String = "LOW",
    val route: CockpitRouteSummary = CockpitRouteSummary(),
    @SerialName("approval_state") val approvalState: String = "UNNECESSARY",
    val result: String = "SUCCESS",
    val confidence: Float = 0f,
    @SerialName("proof_id") val proofId: String = "",
)

@Serializable
data class CockpitRouteSummary(
    val destination: String = "HUMAN_ONLY",
    val model: String? = null,
    val reason: String = "",
    @SerialName("duration_ms") val durationMs: Long = 0,
)

@Serializable
data class CockpitProofRecord(
    val id: String = "",
    @SerialName("audit_id") val auditId: String,
    val rationale: String = "",
    val evidence: List<CockpitEvidenceItem> = emptyList(),
    @SerialName("tests_run") val testsRun: List<String> = emptyList(),
    @SerialName("files_changed") val filesChanged: List<String> = emptyList(),
    val verification: CockpitVerificationResult = CockpitVerificationResult(),
    val approvals: List<CockpitApprovalHistoryItem> = emptyList(),
    val rollback: CockpitRollbackPlan? = null,
    @SerialName("impact_report") val impactReport: String? = null,
    @SerialName("worker_runs") val workerRuns: List<CockpitWorkerRun> = emptyList(),
)

@Serializable
data class CockpitEvidenceItem(
    val id: String = "",
    val kind: String = "LOG",
    val title: String = "",
    val body: String = "",
    @SerialName("source_path") val sourcePath: String? = null,
)

@Serializable
data class CockpitVerificationResult(
    val status: String = "SKIPPED",
    val summary: String = "",
    @SerialName("failing_checks") val failingChecks: List<String> = emptyList(),
    @SerialName("passed_checks") val passedChecks: List<String> = emptyList(),
)

@Serializable
data class CockpitApprovalHistoryItem(
    val id: String = "",
    val timestamp: String? = null,
    val approver: String = "",
    val state: String = "PENDING",
    val comment: String? = null,
)

@Serializable
data class CockpitRollbackPlan(
    val id: String = "",
    val summary: String = "",
    val steps: List<String> = emptyList(),
    val automatic: Boolean = false,
    val executed: Boolean = false,
)

@Serializable
data class CockpitWorkerRun(
    val id: String = "",
    val worker: String = "",
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("finished_at") val finishedAt: String? = null,
    val status: String = "SUCCESS",
    val notes: String = "",
)

// ─── Approval cards (canonical) ───────────────────────────────────────

/**
 * Wire model for the canonical owner-approval queue (contract §10c) —
 * one-to-one with the server's `ApprovalCard`. Enum-like fields are raw
 * Strings (mapped to `approval.model` enums by the repository); timestamps
 * are ISO-8601 (null `expires_at` = never expires). Multi-step
 * serious/critical state is UI-runtime and defaulted client-side.
 */
@Serializable
data class CockpitApprovalCardList(val approvals: List<CockpitApprovalCard> = emptyList())

@Serializable
data class CockpitApprovalCard(
    val id: String,
    val title: String = "",
    val summary: String = "",
    val requester: String = "",
    val tier: String = "RISKY",
    val status: String = "PENDING",
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
    @SerialName("proposed_action") val proposedAction: String = "",
    @SerialName("edited_note") val editedNote: String? = null,
)

/** POST body for `approvals/{id}` — approve requires the owner phrase. */
@Serializable
data class CockpitApprovalDecision(
    val decision: String,
    val authorization: String? = null,
    val notes: String? = null,
)

@Serializable
data class CockpitApprovalDecisionResult(
    val id: String = "",
    val status: String? = null,
    val error: String? = null,
    val hint: String? = null,
)

// ─── Error envelope ───────────────────────────────────────────────────

@Serializable
data class CockpitErrorEnvelope(val error: CockpitError)

@Serializable
data class CockpitError(
    val code: String,
    val message: String,
    val details: Map<String, String>? = null,
)

/**
 * Job status lifecycle. Mirrors the canonical contract (§4) — a superset
 * of the JARVIS-Prime queue's execution states and the cockpit's
 * publish-workflow states. Wire values are the enum constant names
 * (UPPER_SNAKE, per §1); [fromWire] is case-insensitive so a legacy
 * lowercase gateway still maps. Kept string-valued so an unknown future
 * value never crashes deserialisation.
 */
enum class JobStatus(val wire: String) {
    DRAFT("DRAFT"),
    QUEUED("QUEUED"),
    RUNNING("RUNNING"),
    PAUSED("PAUSED"),
    BLOCKED("BLOCKED"),
    DISCONNECTED("DISCONNECTED"),
    COMPLETED("COMPLETED"),
    WAITING_FOR_APPROVAL("WAITING_FOR_APPROVAL"),
    APPROVED("APPROVED"),
    PUBLISHING("PUBLISHING"),
    PUBLISHED("PUBLISHED"),
    FAILED("FAILED"),
    CANCELLED("CANCELLED");

    /** Terminal states never auto-advance. */
    val isTerminal: Boolean
        get() = this == PUBLISHED || this == FAILED || this == CANCELLED || this == COMPLETED

    companion object {
        fun fromWire(value: String?): JobStatus? =
            entries.firstOrNull { it.wire.equals(value, ignoreCase = true) }
    }
}

enum class PublishState(val wire: String) {
    NOT_STARTED("NOT_STARTED"),
    IN_PROGRESS("IN_PROGRESS"),
    SUCCEEDED("SUCCEEDED"),
    FAILED("FAILED");

    companion object {
        fun fromWire(value: String?): PublishState? =
            entries.firstOrNull { it.wire.equals(value, ignoreCase = true) }
    }
}

// ─── Avatar persona ("make my avatar Goku") ──────────────────────────────

@Serializable
data class CockpitPersona(
    val name: String = "",
    val description: String = "",
    @SerialName("persona_prompt") val personaPrompt: String = "",
    val generated: Boolean = false,
)

@Serializable
data class SetPersonaRequest(
    val description: String,
    val name: String = "",
)

// ─── Room editor (AI-generated furniture) ─────────────────────────────────

@Serializable
data class CockpitRoomItem(
    val id: String = "",
    val prompt: String = "",
    @SerialName("image_b64") val imageB64: String? = null,
    val x: Float = 0.5f,
    val y: Float = 0.62f,
)

@Serializable
data class PlaceItemRequest(val x: Float, val y: Float)

@Serializable
data class CockpitRoomList(
    val items: List<CockpitRoomItem> = emptyList(),
    @SerialName("image_generation") val imageGeneration: Boolean = false,
)

@Serializable
data class GenerateRoomRequest(val prompt: String)

// ─── Server capabilities (feature negotiation) ────────────────────────────

/**
 * Wire model for `GET /v1/cockpit/capabilities` — what *this backend* can do
 * (distinct from the curated in-app [com.aci.hermes.data.model.Capability]
 * picker). Lets the app negotiate against the live server: which subsystems
 * import, which worker lanes are present, and whether execute lanes are
 * permitted (loopback guard). Never carries the owner phrase or any secret.
 */
@Serializable
data class ServerCapabilities(
    @SerialName("api_version") val apiVersion: String = "",
    @SerialName("gateway_version") val gatewayVersion: String = "",
    val subsystems: Map<String, Boolean> = emptyMap(),
    /** Orchestrator lane ids the coding/execute + jobs/run routes accept. */
    @SerialName("available_workers") val availableWorkers: List<ServerWorkerLane> = emptyList(),
    /** Informational: external CLIs detected on the host (not execute-validated). */
    @SerialName("detected_clis") val detectedClis: List<String> = emptyList(),
    @SerialName("execute_allowed") val executeAllowed: Boolean = false,
    @SerialName("owner_gate_required") val ownerGateRequired: Boolean = true,
    @SerialName("generated_at") val generatedAt: String? = null,
)

@Serializable
data class ServerWorkerLane(
    val id: String = "",
    @SerialName("requires_approval") val requiresApproval: Boolean = true,
)

// ─── Emergency stop (real backend halt) ───────────────────────────────────

@Serializable
data class EmergencyStopRequest(val reason: String? = null)

/**
 * Result of `POST /v1/cockpit/emergency-stop`. A genuine backend halt: owner
 * gates cleared, proactive tick disabled, worker branch leases released, and
 * every non-terminal queued/running job paused (reversible via resume).
 */
@Serializable
data class EmergencyStopResult(
    val reason: String = "",
    @SerialName("cleared_actions") val clearedActions: List<String> = emptyList(),
    @SerialName("branch_leases_cleared") val branchLeasesCleared: Int = 0,
    @SerialName("tick_disabled") val tickDisabled: Boolean = false,
    @SerialName("jobs_paused") val jobsPaused: Int = 0,
    @SerialName("jobs_paused_ids") val jobsPausedIds: List<String> = emptyList(),
    @SerialName("halted_at") val haltedAt: String? = null,
)

// ─── Job pause / resume ───────────────────────────────────────────────────

@Serializable
data class JobControlRequest(val reason: String? = null)

// ─── Coding lanes (audit / plan / execute) ────────────────────────────────

@Serializable
data class CodingRequest(
    val prompt: String,
    @SerialName("repo_root") val repoRoot: String? = null,
    @SerialName("worker_id") val workerId: String? = null,
    /** Owner phrase — required only to actually dispatch an execute lane. */
    val authorization: String? = null,
)

/** Result of `POST /v1/cockpit/coding/audit` — classify + route (read-only). */
@Serializable
data class CodingAuditResult(
    val intent: String = "",
    @SerialName("risk_class") val riskClass: String = "",
    @SerialName("primary_worker") val primaryWorker: String = "",
    @SerialName("reviewer_worker") val reviewerWorker: String = "",
    @SerialName("model_lane_hint") val modelLaneHint: String = "",
    @SerialName("owner_gates") val ownerGates: List<String> = emptyList(),
    val blocked: Boolean = false,
    val rationale: String = "",
    val mission: String = "",
    @SerialName("owner_gate_required") val ownerGateRequired: Boolean = false,
)

/** A bounded coding work packet (mirrors the natural-language coder packet). */
@Serializable
data class CodingPacket(
    val mission: String = "",
    val intent: String = "",
    val branch: String = "",
    @SerialName("risk_class") val riskClass: String = "",
    @SerialName("repo_root") val repoRoot: String = ".",
    @SerialName("allowed_files") val allowedFiles: List<String> = emptyList(),
    @SerialName("forbidden_files") val forbiddenFiles: List<String> = emptyList(),
    @SerialName("acceptance_criteria") val acceptanceCriteria: List<String> = emptyList(),
    @SerialName("verification_plan") val verificationPlan: List<String> = emptyList(),
    @SerialName("rollback_plan") val rollbackPlan: List<String> = emptyList(),
    @SerialName("owner_gates") val ownerGates: List<String> = emptyList(),
    @SerialName("primary_worker") val primaryWorker: String = "",
    @SerialName("model_lane_hint") val modelLaneHint: String = "",
    val blocked: Boolean = false,
)

@Serializable
data class CodingValidationFinding(
    val field: String = "",
    val severity: String = "",
    val message: String = "",
)

@Serializable
data class CodingValidation(
    val ok: Boolean = false,
    val findings: List<CodingValidationFinding> = emptyList(),
)

/** Result of `POST /v1/cockpit/coding/plan` — stage/validate only. */
@Serializable
data class CodingPlanResult(
    val packet: CodingPacket = CodingPacket(),
    val validation: CodingValidation = CodingValidation(),
    val markdown: String = "",
    @SerialName("owner_gate_required") val ownerGateRequired: Boolean = false,
)

/**
 * Result of `POST /v1/cockpit/coding/execute`. When `status` is
 * `approval_required` the job is staged (created, pending the owner phrase);
 * when `dispatched` it ran through the existing gated orchestrator path.
 */
@Serializable
data class CodingExecuteResult(
    val status: String = "",
    val job: CockpitOrchestratorJob? = null,
    val packet: CodingPacket = CodingPacket(),
    @SerialName("worker_id") val workerId: String = "",
    @SerialName("risk_class") val riskClass: String? = null,
    @SerialName("workspace_path") val workspacePath: String? = null,
    @SerialName("model_lane_hint") val modelLaneHint: String? = null,
    @SerialName("verification_plan") val verificationPlan: List<String> = emptyList(),
    @SerialName("authorization_required") val authorizationRequired: Boolean = false,
    @SerialName("authorization_hint") val authorizationHint: String? = null,
    val error: String? = null,
)

/** Minimal orchestrator-job view returned inside coding/execute. */
@Serializable
data class CockpitOrchestratorJob(
    val id: String = "",
    val status: String = "",
    val prompt: String = "",
)

// ─── Evidence (Research Vault) ────────────────────────────────────────────

@Serializable
data class EvidenceArtifact(
    val id: String = "",
    val title: String = "",
    @SerialName("source_uri") val sourceUri: String = "",
    @SerialName("source_type") val sourceType: String = "",
    @SerialName("evidence_strength") val evidenceStrength: String = "",
    val excerpt: String = "",
    val summary: String = "",
    val tags: List<String> = emptyList(),
    @SerialName("freshness_due") val freshnessDue: String? = null,
    @SerialName("added_at") val addedAt: String? = null,
)

@Serializable
data class EvidenceList(val items: List<EvidenceArtifact> = emptyList())
