package com.aci.hermes.data.jarvis

import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.TaskType

/**
 * Single source of truth for the Jarvis Prime home screen.
 *
 * The screen reads one [JarvisHomeState] and renders every component
 * (icon, header, ask bar, voice button, cards) directly from it. State
 * derivation is a pure function ([JarvisHomeStateDeriver.derive]) so the
 * rules are testable without a running Android runtime.
 */
data class JarvisHomeState(
    val presence: JarvisPresence = JarvisPresence.IDLE,
    val gateway: GatewayStatus = GatewayStatus.CONNECTED,
    val mockMode: Boolean = false,
    val emergencyStopActive: Boolean = false,
    val activeTask: ActiveTaskSnapshot? = null,
    val pendingApprovals: List<PendingApproval> = emptyList(),
    val workers: List<WorkerStatus> = emptyList(),
    val memoryPulse: List<MemoryPulseEntry> = emptyList(),
    val suggestedNextAction: SuggestedAction? = null,
) {
    val hasCriticalApproval: Boolean get() = pendingApprovals.any { it.risk == ApprovalRisk.CRITICAL }
    val hasSeriousApproval: Boolean get() = pendingApprovals.any { it.risk == ApprovalRisk.SERIOUS }
    val hasAnyApproval: Boolean get() = pendingApprovals.isNotEmpty()
}

/**
 * The 11 visible presence states declared in the brief. Transient states
 * (LISTENING, THINKING) are driven by the UI layer through
 * [JarvisHomeViewModel] direct setters; the rest are derived from the
 * service + task state.
 */
enum class JarvisPresence {
    IDLE,
    LISTENING,
    THINKING,
    WORKING,
    WAITING_FOR_APPROVAL,
    SERIOUS_ACTION_PENDING,
    CRITICAL_ACTION_PENDING,
    GATEWAY_DISCONNECTED,
    SERVICE_STOPPED,
    EMERGENCY_STOP_ACTIVE,
    OFFLINE_MOCK,
}

enum class GatewayStatus { CONNECTED, DEGRADED, DISCONNECTED }

enum class ApprovalRisk { LOW, SERIOUS, CRITICAL }

data class ActiveTaskSnapshot(
    val taskId: String,
    val title: String,
    val taskType: TaskType,
    val status: TaskStatus,
    val target: TargetTool,
    val updatedAt: Long,
)

data class PendingApproval(
    val taskId: String,
    val title: String,
    val target: TargetTool,
    val risk: ApprovalRisk,
    val reason: String,
)

data class WorkerStatus(
    val target: TargetTool,
    val displayName: String,
    val busy: Boolean,
    val lastActivityAt: Long?,
)

data class MemoryPulseEntry(
    val timestamp: Long,
    val label: String,
)

data class SuggestedAction(
    val label: String,
    val kind: SuggestedKind,
    val taskId: String? = null,
)

enum class SuggestedKind {
    OPEN_APPROVAL,
    OPEN_ACTIVE_TASK,
    START_SERVICE,
    DEACTIVATE_EMERGENCY_STOP,
    OPEN_CHAT,
    OPEN_VOICE,
}

/**
 * Inputs to the deriver. All sourced from existing repositories — no new
 * remote calls. [serviceRunning] comes from
 * [com.aci.hermes.service.HermesService] presence check; [tasks] from
 * [com.aci.hermes.data.orchestrator.HermesTaskRepository]; the rest from
 * [com.aci.hermes.data.preferences.SettingsRepository].
 */
data class JarvisHomeInputs(
    val serviceRunning: Boolean,
    val tasks: List<HermesTask>,
    val localOnlyMode: Boolean,
    val emergencyStopActive: Boolean,
    val transientPresence: JarvisPresence? = null,
    val nowMs: Long = System.currentTimeMillis(),
)

object JarvisHomeStateDeriver {

    private const val MEMORY_PULSE_SIZE = 6
    private const val WORKER_BUSY_WINDOW_MS = 5 * 60 * 1000L

    fun derive(inputs: JarvisHomeInputs): JarvisHomeState {
        val pendingApprovals = inputs.tasks
            .filter { it.status == TaskStatus.NEEDS_REVISION || it.status == TaskStatus.READY_FOR_HANDOFF }
            .map { task ->
                val risk = riskFor(task)
                PendingApproval(
                    taskId = task.id,
                    title = task.title.ifBlank { "(untitled task)" },
                    target = task.targetTool,
                    risk = risk,
                    reason = task.reviewNotes?.takeIf { it.isNotBlank() }
                        ?: defaultApprovalReason(task.status),
                )
            }

        val activeTask = inputs.tasks
            .filter { it.status == TaskStatus.HANDED_TO_CODEX ||
                it.status == TaskStatus.HANDED_TO_CLAUDE ||
                it.status == TaskStatus.IN_REVIEW }
            .maxByOrNull { it.updatedAt }
            ?.let {
                ActiveTaskSnapshot(
                    taskId = it.id,
                    title = it.title.ifBlank { "(untitled task)" },
                    taskType = it.taskType,
                    status = it.status,
                    target = it.targetTool,
                    updatedAt = it.updatedAt,
                )
            }

        val workers = TargetTool.values().filter { it != TargetTool.MANUAL }.map { target ->
            val mostRecent = inputs.tasks.filter { it.targetTool == target }.maxByOrNull { it.updatedAt }
            val isActiveTarget = activeTask?.target == target
            WorkerStatus(
                target = target,
                displayName = displayNameFor(target),
                busy = isActiveTarget || (mostRecent != null &&
                    inputs.nowMs - mostRecent.updatedAt < WORKER_BUSY_WINDOW_MS &&
                    mostRecent.status != TaskStatus.COMPLETE),
                lastActivityAt = mostRecent?.updatedAt,
            )
        }

        val memoryPulse = inputs.tasks
            .sortedByDescending { it.updatedAt }
            .take(MEMORY_PULSE_SIZE)
            .map { MemoryPulseEntry(it.updatedAt, memoryLabel(it)) }

        val gateway = when {
            !inputs.serviceRunning -> GatewayStatus.DISCONNECTED
            inputs.localOnlyMode -> GatewayStatus.DEGRADED
            else -> GatewayStatus.CONNECTED
        }

        val presence = derivePresence(
            transient = inputs.transientPresence,
            serviceRunning = inputs.serviceRunning,
            emergencyStopActive = inputs.emergencyStopActive,
            localOnlyMode = inputs.localOnlyMode,
            hasCritical = pendingApprovals.any { it.risk == ApprovalRisk.CRITICAL },
            hasSerious = pendingApprovals.any { it.risk == ApprovalRisk.SERIOUS },
            hasAnyApproval = pendingApprovals.isNotEmpty(),
            hasActiveTask = activeTask != null,
        )

        val suggested = suggestedNextAction(
            presence = presence,
            pendingApprovals = pendingApprovals,
            activeTask = activeTask,
            emergencyStopActive = inputs.emergencyStopActive,
            serviceRunning = inputs.serviceRunning,
        )

        return JarvisHomeState(
            presence = presence,
            gateway = gateway,
            mockMode = inputs.localOnlyMode,
            emergencyStopActive = inputs.emergencyStopActive,
            activeTask = activeTask,
            pendingApprovals = pendingApprovals,
            workers = workers,
            memoryPulse = memoryPulse,
            suggestedNextAction = suggested,
        )
    }

    private fun derivePresence(
        transient: JarvisPresence?,
        serviceRunning: Boolean,
        emergencyStopActive: Boolean,
        localOnlyMode: Boolean,
        hasCritical: Boolean,
        hasSerious: Boolean,
        hasAnyApproval: Boolean,
        hasActiveTask: Boolean,
    ): JarvisPresence {
        // Hard blocks come first — they always win regardless of transient UI state.
        if (emergencyStopActive) return JarvisPresence.EMERGENCY_STOP_ACTIVE
        if (!serviceRunning) return JarvisPresence.SERVICE_STOPPED
        if (hasCritical) return JarvisPresence.CRITICAL_ACTION_PENDING
        if (hasSerious) return JarvisPresence.SERIOUS_ACTION_PENDING
        // Transient UI states (LISTENING / THINKING) only apply while no
        // higher-priority block is active.
        if (transient == JarvisPresence.LISTENING || transient == JarvisPresence.THINKING) {
            return transient
        }
        if (hasAnyApproval) return JarvisPresence.WAITING_FOR_APPROVAL
        if (hasActiveTask) return JarvisPresence.WORKING
        if (localOnlyMode) return JarvisPresence.OFFLINE_MOCK
        return JarvisPresence.IDLE
    }

    private fun riskFor(task: HermesTask): ApprovalRisk = when {
        task.taskType == TaskType.AUDIT && task.status == TaskStatus.NEEDS_REVISION -> ApprovalRisk.CRITICAL
        task.taskType == TaskType.BUILD && task.status == TaskStatus.NEEDS_REVISION -> ApprovalRisk.SERIOUS
        task.status == TaskStatus.NEEDS_REVISION -> ApprovalRisk.SERIOUS
        else -> ApprovalRisk.LOW
    }

    private fun defaultApprovalReason(status: TaskStatus): String = when (status) {
        TaskStatus.NEEDS_REVISION -> "Worker reported issues. Review and decide next step."
        TaskStatus.READY_FOR_HANDOFF -> "Prompt ready to dispatch to the official tool."
        else -> "Awaiting your approval."
    }

    private fun displayNameFor(target: TargetTool): String = when (target) {
        TargetTool.CODEX -> "Codex"
        TargetTool.CHATGPT -> "ChatGPT"
        TargetTool.CLAUDE_CODE -> "Claude Code"
        TargetTool.CLAUDE -> "Claude"
        TargetTool.MANUAL -> "Manual"
    }

    private fun memoryLabel(task: HermesTask): String {
        val verb = when (task.status) {
            TaskStatus.DRAFT -> "drafted"
            TaskStatus.READY_FOR_HANDOFF -> "queued"
            TaskStatus.HANDED_TO_CODEX -> "dispatched to Codex"
            TaskStatus.HANDED_TO_CLAUDE -> "dispatched to Claude"
            TaskStatus.IN_REVIEW -> "reviewing"
            TaskStatus.NEEDS_REVISION -> "flagged for revision"
            TaskStatus.COMPLETE -> "completed"
        }
        val title = task.title.ifBlank { "(untitled task)" }
        return "$verb · $title"
    }

    private fun suggestedNextAction(
        presence: JarvisPresence,
        pendingApprovals: List<PendingApproval>,
        activeTask: ActiveTaskSnapshot?,
        emergencyStopActive: Boolean,
        serviceRunning: Boolean,
    ): SuggestedAction? {
        if (emergencyStopActive) {
            return SuggestedAction(
                label = "Deactivate emergency stop",
                kind = SuggestedKind.DEACTIVATE_EMERGENCY_STOP,
            )
        }
        if (!serviceRunning) {
            return SuggestedAction(label = "Start HermesService", kind = SuggestedKind.START_SERVICE)
        }
        val critical = pendingApprovals.firstOrNull { it.risk == ApprovalRisk.CRITICAL }
        if (critical != null) {
            return SuggestedAction(
                label = "Review critical approval: ${critical.title}",
                kind = SuggestedKind.OPEN_APPROVAL,
                taskId = critical.taskId,
            )
        }
        val serious = pendingApprovals.firstOrNull { it.risk == ApprovalRisk.SERIOUS }
        if (serious != null) {
            return SuggestedAction(
                label = "Approve: ${serious.title}",
                kind = SuggestedKind.OPEN_APPROVAL,
                taskId = serious.taskId,
            )
        }
        val firstApproval = pendingApprovals.firstOrNull()
        if (firstApproval != null) {
            return SuggestedAction(
                label = "Approve: ${firstApproval.title}",
                kind = SuggestedKind.OPEN_APPROVAL,
                taskId = firstApproval.taskId,
            )
        }
        if (activeTask != null) {
            return SuggestedAction(
                label = "Check active task: ${activeTask.title}",
                kind = SuggestedKind.OPEN_ACTIVE_TASK,
                taskId = activeTask.taskId,
            )
        }
        return when (presence) {
            JarvisPresence.IDLE, JarvisPresence.OFFLINE_MOCK ->
                SuggestedAction(label = "Ask Jarvis anything", kind = SuggestedKind.OPEN_CHAT)
            JarvisPresence.LISTENING ->
                SuggestedAction(label = "Open voice capture", kind = SuggestedKind.OPEN_VOICE)
            else -> null
        }
    }
}
