package com.aci.hermes.ui.components.icon

import com.aci.hermes.ui.jarvis.IconState
import com.aci.hermes.ui.jarvis.JarvisIconColors
import com.aci.hermes.ui.jarvis.JarvisPalette
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Test

/**
 * Pins the visual treatment of the emergency-stop state
 * ([IconState.CRITICAL_ACTION_PENDING]). Anything destructive must be
 * unmistakably crimson, at full pulse, and visually distinct from
 * "approval" and "blocked" — those carry different consequences.
 */
class EmergencyStopAppearanceTest {

    private val emergency = JarvisIconColors.appearanceFor(IconState.CRITICAL_ACTION_PENDING)

    @Test
    fun `emergency stop uses crimson for ring and core`() {
        assertEquals(JarvisPalette.Red, emergency.ringColor)
        assertEquals(JarvisPalette.Red, emergency.coreColor)
    }

    @Test
    fun `emergency stop pulses at full amplitude and is not dimmed`() {
        assertEquals(1.0f, emergency.pulseAmplitude)
        assertFalse("emergency must not be dimmed", emergency.dim)
    }

    @Test
    fun `emergency stop differs from blocked`() {
        val blocked = JarvisIconColors.appearanceFor(IconState.BLOCKED)
        assertNotEquals(emergency.coreColor, blocked.coreColor)
        assertNotEquals(emergency.pulseAmplitude, blocked.pulseAmplitude)
    }

    @Test
    fun `emergency stop differs from waiting for approval`() {
        val approval = JarvisIconColors.appearanceFor(IconState.WAITING_FOR_APPROVAL)
        assertNotEquals(emergency.ringColor, approval.ringColor)
        assertNotEquals(emergency.coreColor, approval.coreColor)
    }

    @Test
    fun `emergency stop differs from serious action pending`() {
        // Both are "act now" states, but critical is crimson and
        // serious is gold — TalkBack and the eye both need to tell
        // them apart.
        val serious = JarvisIconColors.appearanceFor(IconState.SERIOUS_ACTION_PENDING)
        assertNotEquals(emergency.ringColor, serious.ringColor)
        assertNotEquals(emergency.coreColor, serious.coreColor)
    }
}
