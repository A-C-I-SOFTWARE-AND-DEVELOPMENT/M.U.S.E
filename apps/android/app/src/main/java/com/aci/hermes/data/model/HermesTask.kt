package com.aci.hermes.data.model

import kotlinx.serialization.Serializable
import java.util.UUID

/**
 * Single task tracked by the Jarvis Prime / Hermes orchestrator.
 *
 * Originally an extension of the Hermes "draft → ready → handed off → review" flow,
 * the model now also carries the Jarvis Prime worker-card surface:
 * worker phase, risk tier, approval state, evidence / blocked / rollback /
 * verification summaries, a proof / audit link, the next concrete action,
 * and an emergency-stop flag.
 *
 * Older persisted tasks (Hermes-era status names, no Jarvis fields) are
 * migrated on load by [com.aci.hermes.data.orchestrator.HermesTaskRepository].
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

    // Jarvis Prime task / worker card extensions.
    val riskTier: RiskTier = RiskTier.LOW,
    val approvalState: ApprovalState = ApprovalState.NOT_REQUIRED,
    val workerPhase: WorkerPhase = WorkerPhase.PLANNER,
    val evidenceSummary: String? = null,
    val blockedReason: String? = null,
    val rollbackSummary: String? = null,
    val verificationResult: String? = null,
    val proofLink: String? = null,
    val emergencyStopActive: Boolean = false,
)

@Serializable
enum class TaskType { BUILD, REVIEW, AUDIT, DEBUG, REFACTOR, RESEARCH, PLANNING }

/**
 * Jarvis Prime task lifecycle. The first six values are the active worker
 * phases the orchestrator advances through. The last six are terminal-ish
 * states the UI groups into the "Waiting / Blocked / Failed / Complete /
 * Stopped" sections.
 */
@Serializable
enum class TaskStatus {
    DRAFT,
    QUEUED,
    PLANNING,
    NAVIGATING,
    EDITING,
    EXECUTING,
    REVIEWING,
    WAITING_FOR_APPROVAL,
    BLOCKED,
    FAILED,
    COMPLETE,
    STOPPED,
}

@Serializable
enum class TargetTool { CODEX, CHATGPT, CLAUDE_CODE, CLAUDE, MANUAL }

/** Coarse blast-radius label surfaced as a chip on every task card. */
@Serializable
enum class RiskTier { LOW, MEDIUM, HIGH, CRITICAL }

/**
 * Approval state for the human-in-the-loop gate. [PENDING] is what surfaces
 * a card to the "Waiting for Approval" section and unlocks the Approvals
 * deep link.
 */
@Serializable
enum class ApprovalState { NOT_REQUIRED, PENDING, APPROVED, REJECTED }

/**
 * Worker lane Jarvis Prime is currently routing the task through. These
 * are independent of [TaskStatus] — a task in [TaskStatus.BLOCKED] still
 * remembers which lane it was in when it stalled. The Worker Lanes UI on
 * the dashboard groups active tasks by this value.
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
 * Grouping the Tasks screen uses to bucket cards. Pure function of
 * [TaskStatus] so the same view can be tested without Compose.
 */
enum class TaskSection { ACTIVE, WAITING_FOR_APPROVAL, BLOCKED, FAILED, COMPLETE }

/** Section the card belongs to on the Tasks screen. */
fun TaskStatus.section(): TaskSection = when (this) {
    TaskStatus.DRAFT,
    TaskStatus.QUEUED,
    TaskStatus.PLANNING,
    TaskStatus.NAVIGATING,
    TaskStatus.EDITING,
    TaskStatus.EXECUTING,
    TaskStatus.REVIEWING,
    TaskStatus.STOPPED -> TaskSection.ACTIVE
    TaskStatus.WAITING_FOR_APPROVAL -> TaskSection.WAITING_FOR_APPROVAL
    TaskStatus.BLOCKED -> TaskSection.BLOCKED
    TaskStatus.FAILED -> TaskSection.FAILED
    TaskStatus.COMPLETE -> TaskSection.COMPLETE
}

/** Worker lane the status implies, used to highlight the active lane card. */
fun TaskStatus.lane(): WorkerPhase? = when (this) {
    TaskStatus.PLANNING -> WorkerPhase.PLANNER
    TaskStatus.NAVIGATING -> WorkerPhase.NAVIGATOR
    TaskStatus.EDITING -> WorkerPhase.EDITOR
    TaskStatus.EXECUTING -> WorkerPhase.EXECUTOR
    TaskStatus.REVIEWING -> WorkerPhase.REVIEWER
    TaskStatus.COMPLETE -> WorkerPhase.JARVIS_FINAL_SYNTHESIS
    else -> null
}

/** Deep-link route into the Approvals queue for [task]. Null unless gated. */
fun HermesTask.approvalsRoute(): String? =
    if (status == TaskStatus.WAITING_FOR_APPROVAL || approvalState == ApprovalState.PENDING) {
        "approvals/$id"
    } else null

/** Deep-link route into the audit trail. Prefers an explicit [proofLink]. */
fun HermesTask.auditRoute(): String? = when {
    status == TaskStatus.COMPLETE -> proofLink ?: "audit/$id"
    proofLink != null -> proofLink
    else -> null
}
