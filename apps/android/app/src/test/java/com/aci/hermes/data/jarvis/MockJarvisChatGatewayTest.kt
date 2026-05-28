package com.aci.hermes.data.jarvis

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Behavioural contract for the mock gateway. The chat lane assumes:
 *
 *  - Every send emits `Thinking` first and exactly one terminal
 *    `Done` or `Failure`.
 *  - `/error` produces `Failure` (NOT a thrown exception) so the
 *    view-model can render a Retry affordance.
 *  - The flow is cooperatively cancellable — used by the abort button.
 *
 * Tests run with `chunkDelayMs = 0` so they complete in milliseconds.
 */
class MockJarvisChatGatewayTest {

    private val gateway = MockJarvisChatGateway(chunkDelayMs = 0L)

    @Test
    fun display_name_and_streaming_flag_match_contract() {
        assertTrue(gateway.displayName.isNotBlank())
        assertTrue(gateway.supportsStreaming)
    }

    @Test
    fun casual_prompt_emits_thinking_then_done() = runBlocking {
        val chunks = withTimeout(2_000) {
            gateway.send(emptyList(), "hi").toList()
        }
        assertTrue(chunks.first() is JarvisChatChunk.Thinking)
        assertTrue(chunks.last() is JarvisChatChunk.Done)
        // No Failure in a normal stream.
        assertNull(chunks.firstOrNull { it is JarvisChatChunk.Failure })
    }

    @Test
    fun slash_error_emits_failure_and_no_done() = runBlocking {
        val chunks = withTimeout(2_000) {
            gateway.send(emptyList(), "/error something").toList()
        }
        val failure = chunks.filterIsInstance<JarvisChatChunk.Failure>().singleOrNull()
        assertNotNull("expected exactly one Failure chunk", failure)
        assertTrue(failure!!.message.isNotBlank())
        // Failure path must NOT emit Done — the view-model treats Done
        // as a clean finish and would hide the retry button otherwise.
        assertNull(chunks.firstOrNull { it is JarvisChatChunk.Done })
    }

    @Test
    fun critical_prompt_emits_critical_tone_and_critical_inline_card() = runBlocking {
        val chunks = withTimeout(2_000) {
            gateway.send(emptyList(), "drop table users").toList()
        }
        val tones = chunks.filterIsInstance<JarvisChatChunk.Tone>()
        assertTrue(
            "critical prompt must set CRITICAL tone",
            tones.any { it.tone == JarvisTone.CRITICAL },
        )
        val cards = chunks.filterIsInstance<JarvisChatChunk.Inline>().map { it.card }
        assertTrue(
            "critical prompt must attach Critical card",
            cards.any { it is JarvisInlineCard.Critical },
        )
        // Critical card carries an explicit ack string.
        val critical = cards.filterIsInstance<JarvisInlineCard.Critical>().first()
        assertTrue(critical.requiredAck.isNotBlank())
    }

    @Test
    fun approval_prompt_attaches_approval_card() = runBlocking {
        val chunks = withTimeout(2_000) {
            gateway.send(emptyList(), "deploy to prod").toList()
        }
        val cards = chunks.filterIsInstance<JarvisChatChunk.Inline>().map { it.card }
        assertTrue(cards.any { it is JarvisInlineCard.Approval })
    }

    @Test
    fun task_prompt_attaches_task_card() = runBlocking {
        val chunks = withTimeout(2_000) {
            gateway.send(emptyList(), "build a settings screen").toList()
        }
        val taskCards = chunks
            .filterIsInstance<JarvisChatChunk.Inline>()
            .map { it.card }
            .filterIsInstance<JarvisInlineCard.Task>()
        assertEquals(1, taskCards.size)
        assertTrue(taskCards.single().title.isNotBlank())
    }

    @Test
    fun cancellation_does_not_throw_uncaught_exception() = runBlocking {
        // /stall has explicit longer delays — easier to observe cancel.
        val gw = MockJarvisChatGateway(chunkDelayMs = 50L)
        val scope = CoroutineScope(Dispatchers.Default)
        val job = scope.launch {
            gw.send(emptyList(), "/stall please wait").toList()
        }
        job.cancelAndJoin()
        assertTrue("job should be cancelled", job.isCancelled)
        // Reaching here means no uncaught exception escaped the scope.
    }

    @Test
    fun architecture_prompt_streams_body_and_detail() = runBlocking {
        val chunks = withTimeout(2_000) {
            gateway.send(emptyList(), "explain how the orchestrator works").toList()
        }
        val body = chunks.filterIsInstance<JarvisChatChunk.Body>()
        val detail = chunks.filterIsInstance<JarvisChatChunk.Detail>()
        assertTrue("architecture must stream body tokens", body.isNotEmpty())
        assertTrue("architecture must stream detail tokens", detail.isNotEmpty())
        assertTrue(chunks.last() is JarvisChatChunk.Done)
    }
}
