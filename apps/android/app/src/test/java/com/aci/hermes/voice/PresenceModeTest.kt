package com.aci.hermes.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PresenceModeTest {

    // ─── PresenceModePolicy.trigger — the degradation chain ──────────────

    @Test
    fun `camera attention wins when available`() {
        assertEquals(
            PresenceTrigger.CAMERA_ATTENTION,
            PresenceModePolicy.trigger(wakeWordAvailable = true, cameraAttentionAvailable = true),
        )
    }

    @Test
    fun `wake word is used when no camera`() {
        assertEquals(
            PresenceTrigger.WAKE_WORD,
            PresenceModePolicy.trigger(wakeWordAvailable = true, cameraAttentionAvailable = false),
        )
    }

    @Test
    fun `mic fallback when neither camera nor wake word`() {
        assertEquals(
            PresenceTrigger.MIC_FALLBACK,
            PresenceModePolicy.trigger(wakeWordAvailable = false, cameraAttentionAvailable = false),
        )
    }

    // ─── PresenceModePolicy.stateFor — phase projection ──────────────────

    @Test
    fun `disabled is always OFF regardless of phase`() {
        for (phase in VoicePhase.values()) {
            assertEquals(PresenceState.OFF, PresenceModePolicy.stateFor(enabled = false, phase = phase))
        }
    }

    @Test
    fun `enabled maps each voice phase to a presence state`() {
        fun s(p: VoicePhase) = PresenceModePolicy.stateFor(enabled = true, phase = p)
        assertEquals(PresenceState.ARMED, s(VoicePhase.DORMANT))
        assertEquals(PresenceState.ARMED, s(VoicePhase.WAITING_FOR_WAKE))
        assertEquals(PresenceState.LISTENING, s(VoicePhase.LISTENING))
        assertEquals(PresenceState.THINKING, s(VoicePhase.THINKING))
        assertEquals(PresenceState.SPEAKING, s(VoicePhase.SPEAKING))
    }

    // ─── WakeWordMatcher ─────────────────────────────────────────────────

    @Test
    fun `matches the keyword as a whole word ignoring case and punctuation`() {
        assertTrue(WakeWordMatcher.matches("muse", "Hey, muse"))
        assertTrue(WakeWordMatcher.matches("muse", "okay muse what's up"))
        assertTrue(WakeWordMatcher.matches("muse", "muse"))
    }

    @Test
    fun `does not match a substring or empty inputs`() {
        assertFalse(WakeWordMatcher.matches("muse", "visiting the museum"))
        assertFalse(WakeWordMatcher.matches("muse", "nothing relevant here"))
        assertFalse(WakeWordMatcher.matches("muse", ""))
        assertFalse(WakeWordMatcher.matches("", "muse"))
    }
}
