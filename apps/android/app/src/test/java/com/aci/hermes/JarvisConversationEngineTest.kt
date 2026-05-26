package com.aci.hermes

import com.aci.hermes.data.conversation.JarvisConversationEngine
import com.aci.hermes.data.model.ChatRole
import com.aci.hermes.data.model.SuggestionKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class JarvisConversationEngineTest {

    private val engine = JarvisConversationEngine()

    @Test
    fun `reply role is always Jarvis`() {
        val reply = engine.reply("anything")
        assertEquals(ChatRole.JARVIS, reply.role)
    }

    @Test
    fun `voice prompt suggests starting voice`() {
        val reply = engine.reply("can you take a voice note")
        assertNotNull(reply.suggestion)
        assertEquals(SuggestionKind.START_VOICE, reply.suggestion?.kind)
    }

    @Test
    fun `memory prompt suggests opening memory`() {
        val reply = engine.reply("what do you remember about me")
        assertNotNull(reply.suggestion)
        assertEquals(SuggestionKind.OPEN_MEMORY, reply.suggestion?.kind)
    }

    @Test
    fun `risky prompt mentions authorization phrase`() {
        val reply = engine.reply("can you deploy to production")
        assertTrue("expected critical guidance, got: ${reply.body}",
            reply.body.contains("Yes, with authorization."))
    }

    @Test
    fun `blank input asks user to elaborate`() {
        val reply = engine.reply("   ")
        assertTrue(reply.body.isNotBlank())
    }
}
