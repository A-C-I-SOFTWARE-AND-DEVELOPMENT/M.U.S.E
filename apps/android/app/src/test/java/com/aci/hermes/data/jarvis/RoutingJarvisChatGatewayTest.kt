package com.aci.hermes.data.jarvis

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The chat "off mocks" cutover: selection must follow the [useLive]
 * predicate at send-time so pairing/unpairing takes effect immediately.
 */
class RoutingJarvisChatGatewayTest {

    private class TaggedGateway(override val displayName: String) : JarvisChatGateway {
        override val supportsStreaming: Boolean = true
        override fun send(history: List<JarvisChatMessage>, prompt: String): Flow<JarvisChatChunk> =
            flowOf(JarvisChatChunk.Body(displayName))
    }

    private val live = TaggedGateway("LIVE")
    private val mock = TaggedGateway("MOCK")

    @Test
    fun `routes to live when paired`() = runTest {
        val gw = RoutingJarvisChatGateway(live, mock, useLive = { true })
        assertEquals("LIVE", gw.displayName)
        val chunk = gw.send(emptyList(), "hi").first() as JarvisChatChunk.Body
        assertEquals("LIVE", chunk.text)
    }

    @Test
    fun `routes to mock when not paired`() = runTest {
        val gw = RoutingJarvisChatGateway(live, mock, useLive = { false })
        assertEquals("MOCK", gw.displayName)
        val chunk = gw.send(emptyList(), "hi").first() as JarvisChatChunk.Body
        assertEquals("MOCK", chunk.text)
    }

    @Test
    fun `re-evaluates selection per send so pairing flips live without rebuild`() = runTest {
        var paired = false
        val gw = RoutingJarvisChatGateway(live, mock, useLive = { paired })
        assertEquals("MOCK", (gw.send(emptyList(), "a").first() as JarvisChatChunk.Body).text)
        paired = true
        assertEquals("LIVE", (gw.send(emptyList(), "b").first() as JarvisChatChunk.Body).text)
    }
}
