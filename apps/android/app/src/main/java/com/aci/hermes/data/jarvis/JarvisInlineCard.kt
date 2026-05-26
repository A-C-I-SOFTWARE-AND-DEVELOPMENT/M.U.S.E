package com.aci.hermes.data.jarvis

import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskType

/**
 * Structured payloads that ride alongside a Jarvis reply. These are
 * rendered as inline cards in the chat — not as separate screens —
 * because the conversation engine is the primary surface.
 */
sealed interface JarvisInlineCard {

    /** Draft task that the user can promote into the orchestrator. */
    data class Task(
        val title: String,
        val summary: String,
        val targetTool: TargetTool,
        val taskType: TaskType,
    ) : JarvisInlineCard

    /**
     * Action that needs explicit owner approval before it runs. Formal
     * approval language is enforced by the renderer.
     */
    data class Approval(
        val title: String,
        val summary: String,
        val impact: String,
        val approveLabel: String = "Approve",
        val denyLabel: String = "Hold",
    ) : JarvisInlineCard

    /**
     * Serious but not destructive — slows the conversation, surfaces
     * the consequence, no formal approval flow.
     */
    data class Serious(
        val title: String,
        val summary: String,
    ) : JarvisInlineCard

    /**
     * Critical/destructive — typed acknowledgement before continuing.
     * Used for prod-impacting or irreversible work.
     */
    data class Critical(
        val title: String,
        val summary: String,
        val requiredAck: String,
    ) : JarvisInlineCard
}
