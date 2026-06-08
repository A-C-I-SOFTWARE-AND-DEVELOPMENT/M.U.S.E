package com.aci.hermes.data.memory

import kotlinx.serialization.Serializable
import java.util.UUID

/**
 * MUSE memory model.
 *
 * Every fact, preference, lesson, or decision Jarvis remembers is a
 * [MemoryItem]. The Memory screen renders these items and lets the
 * owner inspect, correct, and delete them. The same shape is also
 * what the gateway/runtime will sync over when the network bridge is
 * wired — until then [MemoryRepository] supplies mock data so the
 * screen can be developed and tested.
 */
@Serializable
data class MemoryItem(
    val id: String = UUID.randomUUID().toString(),
    val category: MemoryCategory,
    val title: String,
    val content: String,
    val durability: MemoryDurability,
    val confidence: MemoryConfidence,
    val provenance: MemoryProvenance,
    val createdAt: Long,
    val updatedAt: Long = createdAt,
    val lastAccessedAt: Long? = null,
    val tags: List<String> = emptyList(),
    val redacted: Boolean = false,
    val hidden: Boolean = false,
)

@Serializable
enum class MemoryCategory(val display: String) {
    OWNER_PREFERENCE("Owner Preference"),
    PROJECT_MEMORY("Project Memory"),
    WORKFLOW_LESSON("Workflow Lesson"),
    TASK_CONTEXT("Task Context"),
    DECISION_RECORD("Decision Record"),
    SOCIAL_SPEECH_PATTERN("Social Speech Pattern"),
    SESSION_MEMORY("Session Memory"),

    /**
     * Honest "no classification" bucket. The canonical server contract
     * emits this for memories with no category signal (rather than
     * guessing one); the cockpit renders it as a plain uncategorized item.
     */
    UNCATEGORIZED("Uncategorized"),
}

@Serializable
enum class MemoryDurability(val display: String) {
    EPHEMERAL("Ephemeral"),
    SESSION("Session"),
    SHORT_TERM("Short term"),
    LONG_TERM("Long term"),
    PERMANENT("Permanent"),
}

@Serializable
enum class MemoryConfidence(val display: String) {
    LOW("Low"),
    MEDIUM("Medium"),
    HIGH("High"),
    CONFIRMED("Confirmed"),
}

@Serializable
data class MemoryProvenance(
    val source: String,
    val sessionId: String? = null,
    val recordedAt: Long,
    val note: String? = null,
)

/**
 * Owner-visible actions emitted whenever the owner changes Jarvis's
 * memory. The Memory screen produces these locally and forwards them
 * to the runtime/gateway event sink when wired; today they're
 * captured in [LogBuffer] for diagnostics.
 */
@Serializable
sealed class MemoryAction {
    abstract val itemId: String
    abstract val emittedAt: Long

    @Serializable
    data class Correct(
        override val itemId: String,
        val previousContent: String,
        val newContent: String,
        val reason: String?,
        override val emittedAt: Long = System.currentTimeMillis(),
    ) : MemoryAction()

    @Serializable
    data class Delete(
        override val itemId: String,
        val reason: String?,
        override val emittedAt: Long = System.currentTimeMillis(),
    ) : MemoryAction()

    @Serializable
    data class Hide(
        override val itemId: String,
        override val emittedAt: Long = System.currentTimeMillis(),
    ) : MemoryAction()

    @Serializable
    data class Reveal(
        override val itemId: String,
        override val emittedAt: Long = System.currentTimeMillis(),
    ) : MemoryAction()
}
