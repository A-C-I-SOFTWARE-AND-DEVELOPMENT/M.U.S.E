package com.aci.hermes.data.model

import kotlinx.serialization.Serializable
import java.util.UUID

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
