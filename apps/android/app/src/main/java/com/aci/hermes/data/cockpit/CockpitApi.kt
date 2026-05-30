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
