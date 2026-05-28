package com.aci.hermes.data.life

/**
 * A proactive suggestion Jarvis offers unprompted — the "true partner"
 * behavior. The agent (via the gateway state feed) produces these; the
 * overlay surfaces them in a speech bubble the avatar "leans in" to
 * present, and accepting one routes the [actionPrompt] straight through
 * the normal task pipeline.
 */
data class Recommendation(
    val id: String,
    val title: String,
    val detail: String,
    /** The prompt dispatched if the user accepts. Empty = informational. */
    val actionPrompt: String = "",
    val priority: Priority = Priority.NORMAL,
) {
    val isActionable: Boolean get() = actionPrompt.isNotBlank()

    enum class Priority { LOW, NORMAL, HIGH }
}

/**
 * Holds the queue of pending recommendations and tracks which have been
 * shown/dismissed. Pure in-memory logic, unit-testable; the overlay
 * owns one instance and the gateway poller pushes into it.
 */
class RecommendationQueue {
    private val pending = ArrayDeque<Recommendation>()
    private val seen = mutableSetOf<String>()

    val hasPending: Boolean get() = pending.isNotEmpty()
    val size: Int get() = pending.size

    /** Enqueue, de-duplicating by id and ordering HIGH priority first. */
    fun offer(rec: Recommendation): Boolean {
        if (rec.id in seen || pending.any { it.id == rec.id }) return false
        if (rec.priority == Recommendation.Priority.HIGH) {
            pending.addFirst(rec)
        } else {
            pending.addLast(rec)
        }
        return true
    }

    /** Peek the next recommendation without consuming it. */
    fun peek(): Recommendation? = pending.firstOrNull()

    /** Consume the next recommendation and mark it seen. */
    fun take(): Recommendation? {
        val rec = pending.removeFirstOrNull() ?: return null
        seen += rec.id
        return rec
    }

    /** Drop the head (user dismissed it) and remember we showed it. */
    fun dismissHead() {
        pending.removeFirstOrNull()?.let { seen += it.id }
    }

    fun clear() = pending.clear()
}
