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
 * Job status lifecycle. Mirrors the FSM in
 * docs/android/hermes-apk-api-contract.md §4. Kept as a string-valued
 * enum so that an unknown future value doesn't crash deserialisation —
 * the JSON layer treats `status` as a raw String, and screens map it
 * through this enum where they need typed behaviour.
 */
enum class JobStatus(val wire: String) {
    DRAFT("draft"),
    QUEUED("queued"),
    RUNNING("running"),
    WAITING_FOR_APPROVAL("waiting_for_approval"),
    APPROVED("approved"),
    PUBLISHING("publishing"),
    PUBLISHED("published"),
    FAILED("failed"),
    CANCELLED("cancelled");

    companion object {
        fun fromWire(value: String?): JobStatus? = entries.firstOrNull { it.wire == value }
    }
}

enum class PublishState(val wire: String) {
    NOT_STARTED("not_started"),
    IN_PROGRESS("in_progress"),
    SUCCEEDED("succeeded"),
    FAILED("failed");

    companion object {
        fun fromWire(value: String?): PublishState? = entries.firstOrNull { it.wire == value }
    }
}
