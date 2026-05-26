package com.aci.hermes.data.jarvis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AutonomyModeTest {

    @Test
    fun `default fallback is manual`() {
        assertEquals(AutonomyMode.MANUAL, AutonomyMode.fromName(null))
        assertEquals(AutonomyMode.MANUAL, AutonomyMode.fromName("not-a-mode"))
    }

    @Test
    fun `all four modes are covered`() {
        val all = AutonomyMode.entries.toSet()
        assertEquals(
            setOf(
                AutonomyMode.MANUAL,
                AutonomyMode.ASSISTED,
                AutonomyMode.TRUSTED_LOW_RISK,
                AutonomyMode.LOCKDOWN,
            ),
            all,
        )
    }

    @Test
    fun `only lockdown reports itself as lockdown`() {
        assertTrue(AutonomyMode.LOCKDOWN.isLockdown)
        assertFalse(AutonomyMode.MANUAL.isLockdown)
        assertFalse(AutonomyMode.ASSISTED.isLockdown)
        assertFalse(AutonomyMode.TRUSTED_LOW_RISK.isLockdown)
    }

    @Test
    fun `display names are owner-facing`() {
        assertEquals("Manual", AutonomyMode.MANUAL.displayName)
        assertEquals("Assisted", AutonomyMode.ASSISTED.displayName)
        assertEquals("Trusted (low risk)", AutonomyMode.TRUSTED_LOW_RISK.displayName)
        assertEquals("Lockdown", AutonomyMode.LOCKDOWN.displayName)
    }
}
