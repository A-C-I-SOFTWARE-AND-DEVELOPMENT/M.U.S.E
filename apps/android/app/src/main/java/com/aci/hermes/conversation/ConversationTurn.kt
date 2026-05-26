package com.aci.hermes.conversation

import kotlinx.serialization.Serializable
import java.util.UUID

/**
 * One turn in the Jarvis Prime conversation.
 *
 * Turns are owned by a session (a single back-and-forth thread). The
 * [Author] distinguishes who produced the text. [intent] captures the
 * coarse intent classification — surfaced in the audit log so the
 * owner can see why Jarvis Prime took a turn the way it did.
 */
@Serializable
data class ConversationTurn(
    val id: String = UUID.randomUUID().toString(),
    val sessionId: String,
    val author: Author,
    val text: String,
    val intent: Intent = Intent.UNKNOWN,
    val timestamp: Long = System.currentTimeMillis(),
    /** If true, this turn is still being streamed in. */
    val streaming: Boolean = false,
) {
    @Serializable
    enum class Author { OWNER, JARVIS, SYSTEM }

    @Serializable
    enum class Intent {
        UNKNOWN,
        SMALL_TALK,
        BRIEFING,
        APPROVAL_REQUEST,
        APPROVAL_RESPONSE,
        STATUS_QUERY,
        MEMORY_WRITE,
        EMERGENCY_STOP,
    }
}
