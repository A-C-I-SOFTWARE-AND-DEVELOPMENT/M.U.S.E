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
    fun `working outranks thinking`() {
        val p = JarvisLiveStateMapper.project(
            JarvisLiveUiState(thinking = true, working = true),
        )
        assertEquals(JarvisLiveState.Working, p.state)
    }

    @Test
    fun `voice listening outranks generic working`() {
        // Owner-specified priority: voice listening/speaking beats work states.
        val p = JarvisLiveStateMapper.project(
            JarvisLiveUiState(listening = true, working = true),
        )
        assertEquals(JarvisLiveState.Listening, p.state)
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
        // Emergency stop and disconnected hold the avatar still (nothing live).
        val stillStates = setOf(JarvisLiveState.EmergencyStop, JarvisLiveState.Disconnected)
        for (state in JarvisLiveState.values()) {
            val p = JarvisLiveStateMapper.project(uiFor(state).copy(reducedMotion = false))
            if (state in stillStates) {
                assertFalse("motion off for $state", p.motionEnabled)
            } else {
                assertTrue("motion on for $state without reduced motion", p.motionEnabled)
            }
        }
    }

    @Test
    fun `disconnected outranks blocked approval and work but not emergency`() {
        val p = JarvisLiveStateMapper.project(
            JarvisLiveUiState(
                coding = true,
                approvalNeeded = true,
                blocked = true,
                warning = true,
                disconnected = true,
            ),
        )
        assertEquals(JarvisLiveState.Disconnected, p.state)
        // Emergency still wins over disconnected.
        val e = JarvisLiveStateMapper.project(
            JarvisLiveUiState(disconnected = true, emergencyStop = true),
        )
        assertEquals(JarvisLiveState.EmergencyStop, e.state)
    }

    @Test
    fun `warning outranks the work phases but yields to approval and blocked`() {
        val warn = JarvisLiveStateMapper.project(
            JarvisLiveUiState(coding = true, reviewing = true, warning = true),
        )
        assertEquals(JarvisLiveState.Warning, warn.state)
        assertTrue(warn.showWarningCta)

        val approval = JarvisLiveStateMapper.project(
            JarvisLiveUiState(warning = true, approvalNeeded = true),
        )
        assertEquals(JarvisLiveState.ApprovalNeeded, approval.state)
    }

    @Test
    fun `work phases resolve in reviewing coding researching order`() {
        assertEquals(
            JarvisLiveState.Reviewing,
            JarvisLiveStateMapper.project(
                JarvisLiveUiState(researching = true, coding = true, reviewing = true),
            ).state,
        )
        assertEquals(
            JarvisLiveState.Coding,
            JarvisLiveStateMapper.project(
                JarvisLiveUiState(researching = true, coding = true),
            ).state,
        )
        assertEquals(
            JarvisLiveState.Researching,
            JarvisLiveStateMapper.project(JarvisLiveUiState(researching = true)).state,
        )
    }

    @Test
    fun `voice listening and speaking outrank the work phases`() {
        assertEquals(
            JarvisLiveState.Speaking,
            JarvisLiveStateMapper.project(
                JarvisLiveUiState(coding = true, speaking = true),
            ).state,
        )
        assertEquals(
            JarvisLiveState.Listening,
            JarvisLiveStateMapper.project(
                JarvisLiveUiState(reviewing = true, listening = true),
            ).state,
        )
    }

    @Test
    fun `warning keeps motion on but suppresses particles`() {
        val p = JarvisLiveStateMapper.project(JarvisLiveUiState(warning = true))
        assertTrue(p.motionEnabled)
        assertFalse(p.particlesEnabled)
    }

    private fun uiFor(state: JarvisLiveState): JarvisLiveUiState = when (state) {
        JarvisLiveState.Idle -> JarvisLiveUiState()
        JarvisLiveState.Listening -> JarvisLiveUiState(listening = true)
        JarvisLiveState.Thinking -> JarvisLiveUiState(thinking = true)
        JarvisLiveState.Researching -> JarvisLiveUiState(researching = true)
        JarvisLiveState.Coding -> JarvisLiveUiState(coding = true)
        JarvisLiveState.Reviewing -> JarvisLiveUiState(reviewing = true)
        JarvisLiveState.Working -> JarvisLiveUiState(working = true)
        JarvisLiveState.Speaking -> JarvisLiveUiState(speaking = true)
        JarvisLiveState.ApprovalNeeded -> JarvisLiveUiState(approvalNeeded = true)
        JarvisLiveState.Blocked -> JarvisLiveUiState(blocked = true)
        JarvisLiveState.Warning -> JarvisLiveUiState(warning = true)
        JarvisLiveState.Disconnected -> JarvisLiveUiState(disconnected = true)
        JarvisLiveState.EmergencyStop -> JarvisLiveUiState(emergencyStop = true)
    }
}
