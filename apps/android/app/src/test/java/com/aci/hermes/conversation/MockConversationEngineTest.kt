package com.aci.hermes.conversation

import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MockConversationEngineTest {

    private val engine = MockConversationEngine(streamingDelayMs = 0L)

    @Test fun submit_emits_at_least_one_chunk_and_terminates_with_complete() = runTest {
        val events = engine.submit("s1", "hi there").toList()
        assertTrue("at least one chunk", events.any { it is ConversationEngine.Event.Chunk })
        val terminal = events.last()
        assertTrue("must terminate with Complete", terminal is ConversationEngine.Event.Complete)
    }

    @Test fun final_turn_is_authored_by_jarvis_and_not_streaming() = runTest {
        val events = engine.submit("s1", "give me a status").toList()
        val complete = events.last() as ConversationEngine.Event.Complete
        assertEquals(ConversationTurn.Author.JARVIS, complete.turn.author)
        assertFalse(complete.turn.streaming)
        assertEquals(ConversationTurn.Intent.STATUS_QUERY, complete.turn.intent)
    }

    @Test fun emergency_intent_routes_to_emergency_response() = runTest {
        val events = engine.submit("s1", "STOP everything!").toList()
        val complete = events.last() as ConversationEngine.Event.Complete
        assertEquals(ConversationTurn.Intent.EMERGENCY_STOP, complete.turn.intent)
        assertTrue(complete.turn.text.contains("Standing down"))
    }

    @Test fun chunks_are_cumulative_and_match_final_text() = runTest {
        val events = engine.submit("s1", "remember I prefer espresso").toList()
        val chunks = events.filterIsInstance<ConversationEngine.Event.Chunk>()
        // Cumulative property: each chunk's text starts with the previous chunk's text.
        for (i in 1 until chunks.size) {
            assertTrue(
                "chunk $i must extend chunk ${i - 1}",
                chunks[i].text.startsWith(chunks[i - 1].text),
            )
        }
        val complete = events.last() as ConversationEngine.Event.Complete
        assertEquals(chunks.last().text, complete.turn.text)
    }

    @Test fun redaction_strips_openai_keys_from_owner_text_before_classification() {
        val input = "remember my key sk-abcdefghijklmnopqrstuv"
        val redacted = ConversationEngine.Redaction.redact(input)
        assertFalse("OpenAI-style key must be stripped", redacted.contains("sk-abcdef"))
        assertTrue(redacted.contains("[REDACTED]"))
    }

    @Test fun redaction_strips_anthropic_keys_and_bearer_tokens() {
        val input = "use sk-ant-xyz1234567890abcdef and Bearer abc123def456ghi789jkl"
        val redacted = ConversationEngine.Redaction.redact(input)
        assertFalse(redacted.contains("sk-ant-xyz"))
        assertFalse(redacted.contains("Bearer abc123def456ghi789jkl"))
    }

    @Test fun redaction_leaves_normal_text_untouched() {
        val input = "schedule a planning task for tomorrow morning"
        assertEquals(input, ConversationEngine.Redaction.redact(input))
    }
}
