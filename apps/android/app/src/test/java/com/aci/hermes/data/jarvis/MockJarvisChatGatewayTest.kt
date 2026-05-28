package com.aci.hermes.data.jarvis

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class MockJarvisChatGatewayTest {

    private val gateway = MockJarvisChatGateway(chunkDelayMs = 0L)

    @Test
    fun `casual input streams short reply and done`() = runTest {
        val chunks = gateway.send(emptyList(), "hi").toList()
        assertEquals(JarvisChatChunk.Thinking, chunks.first())
        assertTrue(chunks.last() is JarvisChatChunk.Done)
        assertTrue(chunks.any { it is JarvisChatChunk.Body })
        assertTrue(chunks.none { it is JarvisChatChunk.Inline })
    }

    @Test
    fun `task prompt yields inline task card`() = runTest {
        val chunks = gateway.send(emptyList(), "build a chat screen for jarvis").toList()
        val inline = chunks.filterIsInstance<JarvisChatChunk.Inline>()
        assertEquals(1, inline.size)
        assertTrue(inline.single().card is JarvisInlineCard.Task)
    }

    @Test
    fun `approval prompt yields inline approval card and serious tone`() = runTest {
        val chunks = gateway.send(emptyList(), "deploy gateway to prod").toList()
        assertTrue(chunks.any { it is JarvisChatChunk.Tone && it.tone == JarvisTone.SERIOUS })
        val card = chunks.filterIsInstance<JarvisChatChunk.Inline>().single().card
        assertTrue(card is JarvisInlineCard.Approval)
    }

    @Test
    fun `serious prompt yields inline serious card`() = runTest {
        val chunks = gateway.send(emptyList(), "review the password handling for leaks").toList()
        val card = chunks.filterIsInstance<JarvisChatChunk.Inline>().single().card
        assertTrue(card is JarvisInlineCard.Serious)
    }

    @Test
    fun `critical prompt yields inline critical card with ack`() = runTest {
        val chunks = gateway.send(emptyList(), "drop table users in prod").toList()
        val card = chunks.filterIsInstance<JarvisChatChunk.Inline>().single().card
        assertTrue(card is JarvisInlineCard.Critical)
        val critical = card as JarvisInlineCard.Critical
        assertTrue(critical.requiredAck.isNotBlank())
    }

    @Test
    fun `architecture prompt yields detail chunks`() = runTest {
        val chunks = gateway.send(emptyList(), "walk me through the architecture").toList()
        assertTrue(chunks.any { it is JarvisChatChunk.Detail })
    }

    @Test
    fun `error trigger yields failure chunk`() = runTest {
        val chunks = gateway.send(emptyList(), "/error stop responding").toList()
        val failure = chunks.lastOrNull()
        assertNotNull(failure)
        assertTrue(failure is JarvisChatChunk.Failure)
        val f = failure as JarvisChatChunk.Failure
        assertNotNull(f.retryHint)
    }

    @Test
    fun `gateway reports streaming support and a display name`() {
        assertTrue(gateway.supportsStreaming)
        assertTrue(gateway.displayName.isNotBlank())
    }
}
