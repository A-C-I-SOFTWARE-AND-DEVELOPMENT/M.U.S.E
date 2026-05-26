package com.aci.hermes.conversation

import kotlinx.coroutines.flow.Flow

/**
 * Jarvis Prime Conversation Engine — the boundary between the UI and
 * whichever runtime is currently driving the back-and-forth.
 *
 * Production wiring will route this to the Jarvis Prime Gateway over
 * SSE; the [MockConversationEngine] satisfies the same contract so the
 * UI works offline and so unit tests can drive deterministic flows.
 *
 * The contract is intentionally narrow: the UI submits an owner turn,
 * receives a Flow of streaming response chunks, and never holds any
 * provider-specific state. The engine itself is responsible for
 * redaction (no API keys ever leave the device through this interface)
 * and intent tagging.
 */
interface ConversationEngine {

    /**
     * Submit an owner turn. The returned Flow emits zero-or-more
     * [Event.Chunk] events followed by exactly one terminal event —
     * either [Event.Complete] or [Event.Error]. The Flow MUST be cold
     * — collection starts the engine.
     */
    fun submit(sessionId: String, ownerText: String): Flow<Event>

    sealed interface Event {
        /** Incremental text update. `text` is the cumulative reply. */
        data class Chunk(val turnId: String, val text: String) : Event

        /** The reply completed normally; `turn` is the final immutable turn. */
        data class Complete(val turn: ConversationTurn) : Event

        /** The engine failed. The UI surfaces this without retrying. */
        data class Error(val message: String) : Event
    }

    /**
     * Redaction policy. Applied before any text leaves the device.
     * Public so tests can assert which tokens are stripped.
     */
    companion object Redaction {
        private val patterns: List<Regex> = listOf(
            // OpenAI-style keys
            Regex("""\bsk-[A-Za-z0-9]{20,}\b"""),
            // Anthropic-style keys
            Regex("""\bsk-ant-[A-Za-z0-9-]{20,}\b"""),
            // Bearer tokens
            Regex("""\bBearer\s+[A-Za-z0-9._-]{20,}\b"""),
            // AWS access keys
            Regex("""\bAKIA[0-9A-Z]{16}\b"""),
        )

        fun redact(text: String): String {
            var out = text
            for (re in patterns) out = re.replace(out, "[REDACTED]")
            return out
        }
    }
}
