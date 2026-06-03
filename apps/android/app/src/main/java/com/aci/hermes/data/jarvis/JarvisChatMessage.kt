package com.aci.hermes.data.jarvis

import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskType
import java.util.UUID

/**
 * One entry in the Jarvis Prime chat transcript. The transcript is a
 * sealed family rather than a single message bag because the rendering
 * rules differ sharply between user input, model output, transient
 * thinking/working indicators, and gateway errors.
 *
 * Mobile-first contract:
 *  - `body` is always the short reply suitable for a phone bubble.
 *  - `detail` is the optional deep-dive shown when the user expands.
 *  - `tone` controls visual emphasis (NORMAL vs SERIOUS vs CRITICAL).
 *  - `inline` carries structured cards that ride alongside the prose
 *    (task drafts, approval prompts, critical warnings).
 */
sealed interface JarvisChatMessage {
    val id: String
    val createdAt: Long

    data class User(
        override val id: String = UUID.randomUUID().toString(),
        override val createdAt: Long = System.currentTimeMillis(),
        val text: String,
    ) : JarvisChatMessage

    data class Jarvis(
        override val id: String = UUID.randomUUID().toString(),
        override val createdAt: Long = System.currentTimeMillis(),
        val body: String,
        val detail: String? = null,
        val tone: JarvisTone = JarvisTone.NORMAL,
        val streaming: Boolean = false,
        val aborted: Boolean = false,
        val inline: List<JarvisInlineCard> = emptyList(),
        // Mobile tool-visibility surfaces (all additive / defaulted so
        // existing call sites and tests stay source-compatible):
        //  - phases: the progress rail (receiving → … → final)
        //  - toolCalls: compact, expandable, redacted tool activity
        //  - records: tappable evidence / decision-ledger references
        val phases: List<JarvisPhase> = emptyList(),
        val toolCalls: List<JarvisToolCall> = emptyList(),
        val records: List<JarvisRecordRef> = emptyList(),
    ) : JarvisChatMessage

    /**
     * Quick "..." while Jarvis is still deciding what kind of answer
     * this needs. Cleared the instant the first real chunk arrives.
     */
    data class Thinking(
        override val id: String = UUID.randomUUID().toString(),
        override val createdAt: Long = System.currentTimeMillis(),
    ) : JarvisChatMessage

    /**
     * Longer-running indicator with a human-readable label
     * ("Pulling repo state", "Drafting approval card").
     */
    data class Working(
        override val id: String = UUID.randomUUID().toString(),
        override val createdAt: Long = System.currentTimeMillis(),
        val label: String,
    ) : JarvisChatMessage

    data class Error(
        override val id: String = UUID.randomUUID().toString(),
        override val createdAt: Long = System.currentTimeMillis(),
        val text: String,
        val retryHint: String? = null,
    ) : JarvisChatMessage
}

enum class JarvisTone { NORMAL, SERIOUS, CRITICAL }
