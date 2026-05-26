package com.aci.hermes.voice

import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.TaskType
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Side-effecting destination for a captured voice transcript. Kept as
 * a narrow interface so [VoiceCaptureViewModel] is unit-testable
 * without a real [HermesTaskRepository].
 *
 * Phase-1 invariant: vague or serious commands never auto-execute. A
 * captured transcript becomes either a chat draft or an
 * approval-needed task — the dangerous-action path is intentionally
 * absent.
 */
interface VoiceCaptureRouter {
    /** Stash the transcript for the chat / orchestrator new-task surface to pick up. */
    suspend fun sendToChat(transcript: String, classification: VoiceCommandClassification): RoutingResult

    /** Persist the transcript as a [HermesTask]. */
    suspend fun createTask(transcript: String, classification: VoiceCommandClassification): RoutingResult

    sealed class RoutingResult {
        data class Ok(val message: String) : RoutingResult()
        data class Failed(val message: String) : RoutingResult()
    }
}

/**
 * Default routing implementation used in the running app. Writes draft
 * tasks to [tasksRepo] and updates [pendingChatDraft] with the latest
 * transcript so the orchestrator new-task screen can pick it up.
 */
class DefaultVoiceCaptureRouter(
    private val tasksRepo: HermesTaskRepository,
    private val pendingChatDraft: VoicePendingDraft,
) : VoiceCaptureRouter {

    override suspend fun sendToChat(
        transcript: String,
        classification: VoiceCommandClassification,
    ): VoiceCaptureRouter.RoutingResult {
        if (transcript.isBlank()) {
            return VoiceCaptureRouter.RoutingResult.Failed("Nothing to send.")
        }
        pendingChatDraft.publish(
            VoicePendingDraft.Draft(
                transcript = transcript,
                requiresApproval = classification.category == VoiceCommandCategory.APPROVAL_REQUIRED,
                reason = classification.reason,
            ),
        )
        return VoiceCaptureRouter.RoutingResult.Ok("Sent to chat draft.")
    }

    override suspend fun createTask(
        transcript: String,
        classification: VoiceCommandClassification,
    ): VoiceCaptureRouter.RoutingResult {
        if (transcript.isBlank()) {
            return VoiceCaptureRouter.RoutingResult.Failed("Nothing to save.")
        }
        val needsApproval = classification.category == VoiceCommandCategory.APPROVAL_REQUIRED
        val titlePrefix = if (needsApproval) APPROVAL_PREFIX else "Voice capture"
        val description = buildString {
            append(transcript.trim())
            if (needsApproval) {
                appendLine()
                appendLine()
                append("⚠ Marked as approval-required by voice capture")
                classification.matchedTrigger?.let { append(" (matched: \"$it\")") }
                classification.reason?.let { append(" — $it") }
                appendLine(".")
                append("Voice capture never auto-executes this action. Review before handing off.")
            }
        }
        val title = transcript.trim().split(Regex("[.!?\\n]"))
            .firstOrNull { it.isNotBlank() }
            ?.take(80)
            ?.let { "$titlePrefix: $it" }
            ?: titlePrefix

        val task = HermesTask(
            title = title,
            description = description,
            targetTool = TargetTool.MANUAL,
            taskType = TaskType.PLANNING,
            status = TaskStatus.DRAFT,
        )
        tasksRepo.upsert(task)
        val message = if (needsApproval) {
            "Saved as approval-required draft (not executed)."
        } else {
            "Saved as draft task."
        }
        return VoiceCaptureRouter.RoutingResult.Ok(message)
    }

    companion object {
        const val APPROVAL_PREFIX = "[Approval needed]"
    }
}

/**
 * Tiny in-memory hand-off used by the chat / new-task surface to read
 * the last voice transcript without coupling to the voice module. The
 * orchestrator dashboard observes [pending] so it can navigate to the
 * new-task screen when the voice sheet routes a transcript to chat;
 * the task screen then consumes the draft to prefill its fields.
 */
class VoicePendingDraft {
    private val _pending = MutableStateFlow<Draft?>(null)
    val pending: StateFlow<Draft?> = _pending

    fun publish(draft: Draft) {
        _pending.value = draft
    }

    /** Consume the pending draft, clearing it. */
    fun consume(): Draft? {
        val snapshot = _pending.value
        _pending.value = null
        return snapshot
    }

    fun peek(): Draft? = _pending.value

    data class Draft(
        val transcript: String,
        val requiresApproval: Boolean,
        val reason: String? = null,
    )
}
