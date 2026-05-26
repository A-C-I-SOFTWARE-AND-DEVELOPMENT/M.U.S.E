package com.aci.hermes.data.emergency

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EmergencyStopStateTest {
    @Test
    fun `severity ordering matches ordinal`() {
        assertTrue(EmergencyStopState.INACTIVE.severity < EmergencyStopState.SOFT_PAUSE.severity)
        assertTrue(EmergencyStopState.SOFT_PAUSE.severity < EmergencyStopState.HARD_STOP.severity)
        assertTrue(EmergencyStopState.HARD_STOP.severity < EmergencyStopState.LOCKDOWN.severity)
    }

    @Test
    fun `isActive is true for every non-INACTIVE state`() {
        assertFalse(EmergencyStopState.INACTIVE.isActive)
        assertTrue(EmergencyStopState.SOFT_PAUSE.isActive)
        assertTrue(EmergencyStopState.HARD_STOP.isActive)
        assertTrue(EmergencyStopState.LOCKDOWN.isActive)
    }

    @Test
    fun `four states exist in expected order`() {
        val expected = listOf(
            EmergencyStopState.INACTIVE,
            EmergencyStopState.SOFT_PAUSE,
            EmergencyStopState.HARD_STOP,
            EmergencyStopState.LOCKDOWN,
        )
        assertEquals(expected, EmergencyStopState.values().toList())
    }
}
