// Lives under `ui/screens/chat/` rather than `data/jarvis/` because the
// allowed test-path constraint for this lane is `**/chat/**`. The gateway
// it covers is in `com.aci.hermes.data.jarvis`.
package com.aci.hermes.ui.screens.chat

import com.aci.hermes.data.jarvis.JarvisChatChunk
import com.aci.hermes.data.jarvis.JarvisInlineCard
import com.aci.hermes.data.jarvis.MockJarvisChatGateway
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MockJarvisChatGatewayTest {

    private val gateway = MockJarvisChatGateway(chunkDelayMs = 0)

    private fun collect(prompt: String): List<JarvisChatChunk> = runBlocking {
        gateway.send(emptyList(), prompt).toList()
    }

    @Test
    fun `casual prompt streams thinking then body then done`() {
        val chunks = collect("hi")
        assertTrue("expected leading Thinking", chunks.first() is JarvisChatChunk.Thinking)
        assertTrue("expected trailing Done", chunks.last() is JarvisChatChunk.Done)
        assertTrue("expected at least one Body chunk", chunks.any { it is JarvisChatChunk.Body })
    }

    @Test
    fun `error trigger emits a single Failure and stops`() {
        val chunks = collect("/error something broke")
        val failures = chunks.filterIsInstance<JarvisChatChunk.Failure>()
        assertEquals(1, failures.size)
        assertNotNull(failures.first().retryHint)
        // No Done after a Failure — the gateway short-circuits.
        assertTrue(chunks.none { it is JarvisChatChunk.Done })
    }

    @Test
    fun `task prompt emits an Inline Task card`() {
        val chunks = collect("build a chat screen for jarvis")
        val inline = chunks.filterIsInstance<JarvisChatChunk.Inline>()
        assertEquals(1, inline.size)
        assertTrue(inline.first().card is JarvisInlineCard.Task)
    }

    @Test
    fun `approval prompt emits an Inline Approval card`() {
        val chunks = collect("deploy gateway to prod")
        val inline = chunks.filterIsInstance<JarvisChatChunk.Inline>()
        assertEquals(1, inline.size)
        assertTrue(inline.first().card is JarvisInlineCard.Approval)
    }

    @Test
    fun `serious prompt emits an Inline Serious card`() {
        val chunks = collect("audit the api key handling for leaks")
        val inline = chunks.filterIsInstance<JarvisChatChunk.Inline>()
        assertEquals(1, inline.size)
        assertTrue(inline.first().card is JarvisInlineCard.Serious)
    }

    @Test
    fun `critical prompt emits an Inline Critical card with the ack string set`() {
        val chunks = collect("drop table users in prod")
        val inline = chunks.filterIsInstance<JarvisChatChunk.Inline>()
        assertEquals(1, inline.size)
        val card = inline.first().card
        assertTrue(card is JarvisInlineCard.Critical)
        assertEquals("I understand this is irreversible", (card as JarvisInlineCard.Critical).requiredAck)
    }
}
