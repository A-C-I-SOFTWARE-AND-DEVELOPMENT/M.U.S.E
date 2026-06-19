package com.aci.hermes.data.model

import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.model.ApprovalStatus
import kotlinx.serialization.Serializable
import java.util.UUID

/**
 * One unit of work tracked by the muse cockpit.
 *
 * The original Hermes handoff fields (title / status / target / notes) are
 * unchanged. The muse worker-card surface is layered on top as new,
 * fully-defaulted fields so older persisted tasks deserialize without
 * migration — every addition is optional and round-trips through the same
 * `Json { ignoreUnknownKeys = true; encodeDefaults = true }` config the
 * repository uses.
 *
 * Risk tier and approval state deliberately reuse the canonical
 * [ApprovalRiskTier] / [ApprovalStatus] the Approvals flow already gates on,
 * rather than introducing a parallel scale.
 */
@Serializable
data class HermesTask(
    val id: String = UUID.randomUUID().toString(),
    val title: String = "",
    val description: String = "",
    val workspacePath: String? = null,
    val targetTool: TargetTool = TargetTool.CODEX,
    val taskType: TaskType = TaskType.BUILD,
    val status: TaskStatus = TaskStatus.DRAFT,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
    val promptBody: String? = null,
    val resultNotes: String? = null,
    val reviewNotes: String? = null,
    val nextAction: String? = null,

    // --- muse worker-card extensions (all optional / defaulted) ---
    /** Blast-radius tier, on the same scale the Approvals flow gates on. */
    val riskTier: ApprovalRiskTier = ApprovalRiskTier.LOW,
    /** Which worker lane the task is currently routed through. */
    val workerPhase: WorkerPhase = WorkerPhase.PLANNER,
    /** Approval decision when this task is gated; null when no approval is required. */
    val approvalState: ApprovalStatus? = null,
    /** One-line summary of the evidence Jarvis gathered before acting. */
    val evidenceSummary: String? = null,
    /** Why the task is blocked, surfaced on every BLOCKED card. */
    val blockedReason: String? = null,
    /** The rollback / undo plan prepared for this task. */
    val rollbackSummary: String? = null,
    /** Result of the post-execution verification gate. */
    val verificationResult: String? = null,
    /** Proof / audit link (URL or internal audit id). */
    val proofLink: String? = null,
)

@Serializable
enum class TaskType { BUILD, REVIEW, AUDIT, DEBUG, REFACTOR, RESEARCH, PLANNING }

@Serializable
enum class TaskStatus {
    DRAFT,
    READY_FOR_HANDOFF,
    HANDED_TO_CODEX,
    HANDED_TO_CLAUDE,
    IN_REVIEW,
    NEEDS_REVISION,
    COMPLETE,
}

@Serializable
enum class TargetTool { CODEX, CHATGPT, CLAUDE_CODE, CLAUDE, MANUAL }

/**
 * muse worker lanes. The orchestrator routes a task through these in
 * order; the card shows the current lane. Independent of [TaskStatus] so a
 * blocked task still remembers which lane it stalled in.
 */
@Serializable
enum class WorkerPhase {
    PLANNER,
    NAVIGATOR,
    EDITOR,
    EXECUTOR,
    REVIEWER,
    JARVIS_FINAL_SYNTHESIS,
}

/**
 * Buckets the Tasks screen groups cards into. Derived purely from a task's
 * data ([TaskStatus] + the new approval / blocked fields) so the grouping is
 * unit-testable without Compose and without changing the [TaskStatus] enum.
 */
enum class TaskSection { ACTIVE, WAITING_FOR_APPROVAL, BLOCKED, FAILED, COMPLETE }

/**
 * Section a task belongs to. Precedence, highest first:
 *  1. COMPLETE status → Complete
 *  2. REJECTED / EMERGENCY_STOPPED approval → Failed
 *  3. PENDING approval → Waiting for approval
 *  4. an explicit blocked reason, or NEEDS_REVISION status → Blocked
 *  5. everything else → Active
 */
fun HermesTask.section(): TaskSection = when {
    status == TaskStatus.COMPLETE -> TaskSection.COMPLETE
    approvalState == ApprovalStatus.REJECTED ||
        approvalState == ApprovalStatus.EMERGENCY_STOPPED -> TaskSection.FAILED
    approvalState == ApprovalStatus.PENDING -> TaskSection.WAITING_FOR_APPROVAL
    blockedReason != null || status == TaskStatus.NEEDS_REVISION -> TaskSection.BLOCKED
    else -> TaskSection.ACTIVE
}

/** True when this task should surface an Approvals deep link. */
fun HermesTask.linksApprovals(): Boolean = section() == TaskSection.WAITING_FOR_APPROVAL

/** True when this task should surface an Audit deep link. */
fun HermesTask.linksAudit(): Boolean = section() == TaskSection.COMPLETE || proofLink != null
