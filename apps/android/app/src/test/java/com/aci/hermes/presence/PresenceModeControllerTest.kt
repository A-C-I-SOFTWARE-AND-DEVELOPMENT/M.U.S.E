package com.aci.hermes.presence

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PresenceModeControllerTest {

    private val allCaps = PresenceCapabilities(
        attentionAvailable = true,
        wakeWordAvailable = true,
        micAvailable = true,
    )

    private fun enabled(caps: PresenceCapabilities = allCaps): PresenceModeController {
        val c = PresenceModeController()
        c.on(PresenceEvent.SetEnabled(true))
        c.on(PresenceEvent.CapabilitiesChanged(caps))
        return c
    }

    @Test
    fun `disabled by default - nothing arms and triggers do nothing`() {
        val c = PresenceModeController()
        c.on(PresenceEvent.CapabilitiesChanged(allCaps))
        assertEquals(TriggerSource.NONE, c.armedSource)
        val d = c.on(PresenceEvent.WakeWordDetected)
        assertEquals(PresenceModeController.Effect.NONE, d.effect)
        assertFalse(d.listening)
    }

    @Test
    fun `fallback chain prefers attention then wake then mic`() {
        assertEquals(TriggerSource.ATTENTION, enabled(allCaps).armedSource)
        assertEquals(
            TriggerSource.WAKE_WORD,
            enabled(PresenceCapabilities(wakeWordAvailable = true, micAvailable = true)).armedSource,
        )
        assertEquals(
            TriggerSource.MIC_BUTTON,
            enabled(PresenceCapabilities(micAvailable = true)).armedSource,
        )
        assertEquals(
            TriggerSource.NONE,
            enabled(PresenceCapabilities()).armedSource,
        )
    }

    @Test
    fun `attention detected starts a hands-free conversation`() {
        val c = enabled()
        val d = c.on(PresenceEvent.AttentionDetected)
        assertEquals(PresenceModeController.Effect.START_VOICE_LOOP, d.effect)
        assertTrue(d.listening)
    }

    @Test
    fun `wake word does not start when wake is unavailable`() {
        val c = enabled(PresenceCapabilities(micAvailable = true))
        val d = c.on(PresenceEvent.WakeWordDetected)
        assertEquals(PresenceModeController.Effect.NONE, d.effect)
        assertFalse(d.listening)
    }

    @Test
    fun `mic button works even when attention is the armed source`() {
        val c = enabled(allCaps)
        assertEquals(TriggerSource.ATTENTION, c.armedSource)
        val d = c.on(PresenceEvent.MicButtonTapped)
        assertEquals(PresenceModeController.Effect.START_VOICE_LOOP, d.effect)
        assertTrue(d.listening)
    }

    @Test
    fun `second trigger while listening is a no-op`() {
        val c = enabled()
        c.on(PresenceEvent.AttentionDetected)
        val again = c.on(PresenceEvent.WakeWordDetected)
        assertEquals(PresenceModeController.Effect.NONE, again.effect)
        assertTrue(again.listening)
    }

    @Test
    fun `conversation ended stops listening and re-arms`() {
        val c = enabled()
        c.on(PresenceEvent.AttentionDetected)
        val end = c.on(PresenceEvent.ConversationEnded)
        assertEquals(PresenceModeController.Effect.STOP_VOICE_LOOP, end.effect)
        assertFalse(end.listening)
        assertEquals(TriggerSource.ATTENTION, c.armedSource)
    }

    @Test
    fun `emergency stop overrides everything and disarms triggers`() {
        val c = enabled()
        c.on(PresenceEvent.AttentionDetected)
        val stop = c.on(PresenceEvent.EmergencyStop)
        assertEquals(PresenceModeController.Effect.STOP_VOICE_LOOP, stop.effect)
        assertTrue(stop.emergencyStopped)
        assertEquals(TriggerSource.NONE, c.armedSource)
        // Triggers are ignored while emergency-stopped.
        val blocked = c.on(PresenceEvent.AttentionDetected)
        assertEquals(PresenceModeController.Effect.NONE, blocked.effect)
        assertFalse(blocked.listening)
    }

    @Test
    fun `emergency release re-arms the chain`() {
        val c = enabled()
        c.on(PresenceEvent.EmergencyStop)
        c.on(PresenceEvent.EmergencyRelease)
        assertFalse(c.isEmergencyStopped)
        assertEquals(TriggerSource.ATTENTION, c.armedSource)
        val d = c.on(PresenceEvent.AttentionDetected)
        assertEquals(PresenceModeController.Effect.START_VOICE_LOOP, d.effect)
    }

    @Test
    fun `disabling presence mid-conversation stops listening`() {
        val c = enabled()
        c.on(PresenceEvent.AttentionDetected)
        val off = c.on(PresenceEvent.SetEnabled(false))
        assertEquals(PresenceModeController.Effect.STOP_VOICE_LOOP, off.effect)
        assertFalse(off.listening)
        assertEquals(TriggerSource.NONE, c.armedSource)
    }

    @Test
    fun `losing all capabilities mid-conversation stops listening`() {
        val c = enabled()
        c.on(PresenceEvent.AttentionDetected)
        val lost = c.on(PresenceEvent.CapabilitiesChanged(PresenceCapabilities()))
        assertEquals(PresenceModeController.Effect.STOP_VOICE_LOOP, lost.effect)
        assertFalse(lost.listening)
    }
}
