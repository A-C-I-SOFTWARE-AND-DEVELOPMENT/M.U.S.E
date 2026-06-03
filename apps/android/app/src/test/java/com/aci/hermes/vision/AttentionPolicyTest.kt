package com.aci.hermes.vision

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AttentionPolicyTest {

    // ─── active(): the camera only runs when all three gates pass ────────

    @Test
    fun `camera runs only when opted in, presence on, and permission granted`() {
        assertTrue(AttentionPolicy.active(true, true, true))
    }

    @Test
    fun `opting in alone never starts the camera`() {
        assertFalse(AttentionPolicy.active(cameraAttentionEnabled = true, presenceModeEnabled = true, cameraPermissionGranted = false))
        assertFalse(AttentionPolicy.active(cameraAttentionEnabled = true, presenceModeEnabled = false, cameraPermissionGranted = true))
        assertFalse(AttentionPolicy.active(cameraAttentionEnabled = false, presenceModeEnabled = true, cameraPermissionGranted = true))
    }

    // ─── shouldArmOnTransition(): rising edge only ───────────────────────

    @Test
    fun `arms on the rising edge into PRESENT`() {
        assertTrue(AttentionPolicy.shouldArmOnTransition(null, AttentionState.PRESENT))
        assertTrue(AttentionPolicy.shouldArmOnTransition(AttentionState.ABSENT, AttentionState.PRESENT))
    }

    @Test
    fun `does not re-arm while still present or when absent`() {
        assertFalse(AttentionPolicy.shouldArmOnTransition(AttentionState.PRESENT, AttentionState.PRESENT))
        assertFalse(AttentionPolicy.shouldArmOnTransition(AttentionState.PRESENT, AttentionState.ABSENT))
        assertFalse(AttentionPolicy.shouldArmOnTransition(null, AttentionState.ABSENT))
    }
}
