package com.aci.hermes.ui.screens.live

import com.aci.hermes.R
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class JarvisLiveStateMapperTest {

    @Test
    fun `idle state with no flags projects Idle`() {
        val p = JarvisLiveStateMapper.project(JarvisLiveUiState())
        assertEquals(JarvisLiveState.Idle, p.state)
        assertEquals(R.string.jarvis_state_idle, p.pillText)
        assertFalse(p.showApprovalCta)
        assertFalse(p.showFixCta)
        assertFalse(p.showEmergencyReleaseCta)
    }

    @Test
    fun `every state has non-empty pill text and voice line resources`() {
        for (state in JarvisLiveState.values()) {
            val ui = uiFor(state)
            val p = JarvisLiveStateMapper.project(ui)
            assertEquals("state $state must round-trip", state, p.state)
            assertNotEquals("pill res id must be set for $state", 0, p.pillText)
            assertNotEquals("voice res id must be set for $state", 0, p.voiceLineFallback)
            assertNotEquals("content desc must be set for $state", 0, p.contentDescription)
        }
    }

    @Test
    fun `emergency stop outranks every other state`() {
        val p = JarvisLiveStateMapper.project(
            JarvisLiveUiState(
                listening = true,
                thinking = true,
                working = true,
                speaking = true,
                approvalNeeded = true,
                blocked = true,
                emergencyStop = true,
            ),
        )
        assertEquals(JarvisLiveState.EmergencyStop, p.state)
        assertTrue(p.showEmergencyReleaseCta)
        assertFalse(p.showApprovalCta)
        assertFalse(p.showFixCta)
    }

    @Test
    fun `blocked outranks approval working thinking listening`() {
        val p = JarvisLiveStateMapper.project(
            JarvisLiveUiState(
                listening = true,
                thinking = true,
                working = true,
                approvalNeeded = true,
                blocked = true,
            ),
        )
        assertEquals(JarvisLiveState.Blocked, p.state)
        assertTrue(p.showFixCta)
        assertFalse(p.showApprovalCta)
        assertFalse(p.showEmergencyReleaseCta)
    }

    @Test
    fun `approval needed outranks thinking working listening idle`() {
        val p = JarvisLiveStateMapper.project(
            JarvisLiveUiState(
                listening = true,
                thinking = true,
                working = true,
                approvalNeeded = true,
            ),
        )
        assertEquals(JarvisLiveState.ApprovalNeeded, p.state)
        assertTrue(p.showApprovalCta)
    }

    @Test
    fun `speaking outranks working and thinking`() {
        val p = JarvisLiveStateMapper.project(
            JarvisLiveUiState(thinking = true, working = true, speaking = true),
        )
        assertEquals(JarvisLiveState.Speaking, p.state)
    }

    @Test
    fun `working outranks thinking and listening`() {
        val p = JarvisLiveStateMapper.project(
            JarvisLiveUiState(listening = true, thinking = true, working = true),
        )
        assertEquals(JarvisLiveState.Working, p.state)
    }

    @Test
    fun `reduced motion clamps motion and particles to false`() {
        for (state in JarvisLiveState.values()) {
            val p = JarvisLiveStateMapper.project(uiFor(state).copy(reducedMotion = true))
            assertFalse("motion off for $state under reduced motion", p.motionEnabled)
            assertFalse("particles off for $state under reduced motion", p.particlesEnabled)
        }
    }

    @Test
    fun `long running working task never projects idle`() {
        val p = JarvisLiveStateMapper.project(JarvisLiveUiState(working = true))
        assertEquals(JarvisLiveState.Working, p.state)
        assertNotEquals(JarvisLiveState.Idle, p.state)
    }

    @Test
    fun `approval state sets approval cta flag true`() {
        val p = JarvisLiveStateMapper.project(JarvisLiveUiState(approvalNeeded = true))
        assertTrue(p.showApprovalCta)
        assertFalse(p.showFixCta)
        assertFalse(p.showEmergencyReleaseCta)
    }

    @Test
    fun `blocked state sets fix cta flag true`() {
        val p = JarvisLiveStateMapper.project(JarvisLiveUiState(blocked = true))
        assertTrue(p.showFixCta)
        assertFalse(p.showApprovalCta)
        assertFalse(p.showEmergencyReleaseCta)
    }

    @Test
    fun `emergency state sets emergency release cta flag true`() {
        val p = JarvisLiveStateMapper.project(JarvisLiveUiState(emergencyStop = true))
        assertTrue(p.showEmergencyReleaseCta)
        assertFalse(p.showApprovalCta)
        assertFalse(p.showFixCta)
        assertFalse("motion off in emergency stop", p.motionEnabled)
        assertFalse("particles off in emergency stop", p.particlesEnabled)
    }

    @Test
    fun `idle state has no cta flags`() {
        val p = JarvisLiveStateMapper.project(JarvisLiveUiState())
        assertFalse(p.showApprovalCta)
        assertFalse(p.showFixCta)
        assertFalse(p.showEmergencyReleaseCta)
    }

    @Test
    fun `content description is present for every state`() {
        for (state in JarvisLiveState.values()) {
            val p = JarvisLiveStateMapper.project(uiFor(state))
            assertNotEquals("content desc must exist for $state", 0, p.contentDescription)
        }
    }

    @Test
    fun `motion is enabled by default for non-emergency states`() {
        for (state in JarvisLiveState.values()) {
            val p = JarvisLiveStateMapper.project(uiFor(state).copy(reducedMotion = false))
            if (state == JarvisLiveState.EmergencyStop) {
                assertFalse(p.motionEnabled)
            } else {
                assertTrue("motion on for $state without reduced motion", p.motionEnabled)
            }
        }
    }

    private fun uiFor(state: JarvisLiveState): JarvisLiveUiState = when (state) {
        JarvisLiveState.Idle -> JarvisLiveUiState()
        JarvisLiveState.Listening -> JarvisLiveUiState(listening = true)
        JarvisLiveState.Thinking -> JarvisLiveUiState(thinking = true)
        JarvisLiveState.Working -> JarvisLiveUiState(working = true)
        JarvisLiveState.Speaking -> JarvisLiveUiState(speaking = true)
        JarvisLiveState.ApprovalNeeded -> JarvisLiveUiState(approvalNeeded = true)
        JarvisLiveState.Blocked -> JarvisLiveUiState(blocked = true)
        JarvisLiveState.EmergencyStop -> JarvisLiveUiState(emergencyStop = true)
    }
}
