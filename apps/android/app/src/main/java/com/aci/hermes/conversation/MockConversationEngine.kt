package com.aci.hermes.conversation

import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import java.util.UUID

/**
 * Local, deterministic [ConversationEngine] for offline and test runs.
 *
 * Generates a short, canned reply in the Jarvis Prime voice. Every
 * owner submission is run through [ConversationEngine.Redaction.redact]
 * first so secrets never end up in the in-memory transcript.
 *
 * Intent classification is intentionally simple — production wiring
 * will replace this with the gateway's classifier.
 */
class MockConversationEngine(
    private val streamingDelayMs: Long = 30L,
) : ConversationEngine {

    override fun submit(sessionId: String, ownerText: String): Flow<ConversationEngine.Event> = flow {
        val turnId = UUID.randomUUID().toString()
        val redacted = ConversationEngine.Redaction.redact(ownerText.trim())
        val intent = classify(redacted)
        val reply = canned(intent, redacted)
        val builder = StringBuilder()
        for (chunk in reply.tokens()) {
            builder.append(chunk)
            emit(ConversationEngine.Event.Chunk(turnId = turnId, text = builder.toString()))
            if (streamingDelayMs > 0) delay(streamingDelayMs)
        }
        emit(
            ConversationEngine.Event.Complete(
                ConversationTurn(
                    id = turnId,
                    sessionId = sessionId,
                    author = ConversationTurn.Author.JARVIS,
                    text = builder.toString(),
                    intent = intent,
                    streaming = false,
                )
            )
        )
    }

    private fun classify(text: String): ConversationTurn.Intent {
        val lower = text.lowercase()
        return when {
            lower.startsWith("stop") || "emergency" in lower -> ConversationTurn.Intent.EMERGENCY_STOP
            "status" in lower || "what's running" in lower -> ConversationTurn.Intent.STATUS_QUERY
            "remember" in lower || "note" in lower -> ConversationTurn.Intent.MEMORY_WRITE
            "approve" in lower || "yes, go ahead" in lower -> ConversationTurn.Intent.APPROVAL_RESPONSE
            "?" in lower -> ConversationTurn.Intent.STATUS_QUERY
            lower.isBlank() -> ConversationTurn.Intent.UNKNOWN
            else -> ConversationTurn.Intent.SMALL_TALK
        }
    }

    private fun canned(intent: ConversationTurn.Intent, text: String): String = when (intent) {
        ConversationTurn.Intent.EMERGENCY_STOP ->
            "Standing down. I have signalled every worker to stop and held all pending approvals."
        ConversationTurn.Intent.STATUS_QUERY ->
            "The gateway is offline in this mock. Once you bring it online, I will pull the live worker and queue state for you."
        ConversationTurn.Intent.MEMORY_WRITE ->
            "Captured. I have added that to the Memory Tree — you can review or forget it any time from the Memory screen."
        ConversationTurn.Intent.APPROVAL_RESPONSE ->
            "Noted. I will only act on approvals you confirm twice, and never without an impact report for the critical ones."
        ConversationTurn.Intent.SMALL_TALK ->
            "Standing by. Tell me what you'd like me to do and I will lay out the plan before I move."
        else ->
            "I'm here. Brief me when you're ready."
    }

    private fun String.tokens(): List<String> =
        split(Regex("(?<=\\s)")).filter { it.isNotEmpty() }
}
