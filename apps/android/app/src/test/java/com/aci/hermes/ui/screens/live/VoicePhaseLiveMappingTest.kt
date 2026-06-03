package com.aci.hermes.ui.screens.live

import com.aci.hermes.voice.VoicePhase
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VoicePhaseLiveMappingTest {

    @Test
    fun `listening surfaces transcript and sets only listening`() {
        val s = JarvisLiveUiState().withVoicePhase(VoicePhase.LISTENING, "open the pr")
        assertTrue(s.listening)
        assertFalse(s.thinking)
        assertFalse(s.speaking)
        assertEquals("open the pr", s.voiceLine)
    }

    @Test
    fun `thinking sets only thinking`() {
        val s = JarvisLiveUiState().withVoicePhase(VoicePhase.THINKING)
        assertTrue(s.thinking)
        assertFalse(s.listening)
        assertFalse(s.speaking)
    }

    @Test
    fun `speaking sets only speaking`() {
        val s = JarvisLiveUiState().withVoicePhase(VoicePhase.SPEAKING)
        assertTrue(s.speaking)
        assertFalse(s.listening)
        assertFalse(s.thinking)
    }

    @Test
    fun `dormant and waiting clear all voice flags`() {
        val busy = JarvisLiveUiState(listening = true, thinking = true, speaking = true)
        assertFalse(busy.withVoicePhase(VoicePhase.DORMANT).listening)
        val waiting = busy.withVoicePhase(VoicePhase.WAITING_FOR_WAKE)
        assertFalse(waiting.listening)
        assertFalse(waiting.thinking)
        assertFalse(waiting.speaking)
    }

    @Test
    fun `mapping never touches non-voice action flags`() {
        val base = JarvisLiveUiState(working = true, approvalNeeded = true, emergencyStop = true)
        val s = base.withVoicePhase(VoicePhase.LISTENING, "hi")
        assertTrue(s.working)
        assertTrue(s.approvalNeeded)
        assertTrue(s.emergencyStop)
    }
}
