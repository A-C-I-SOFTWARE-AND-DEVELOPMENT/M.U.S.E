package com.aci.hermes.ui.screens.control

import com.aci.hermes.data.jarvis.AutonomyMode
import com.aci.hermes.data.jarvis.ControlWarnings
import com.aci.hermes.data.jarvis.GatewayState
import com.aci.hermes.data.jarvis.JarvisControlState
import com.aci.hermes.data.jarvis.PendingWarning
import com.aci.hermes.data.jarvis.WarningLevel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class JarvisControlStateTest {

    @Test
    fun `control renders default state with every section visible`() {
        val state = JarvisControlState()
        assertFalse(state.jarvisRunning)
        assertEquals(AutonomyMode.MANUAL, state.autonomy)
        assertFalse(state.emergencyStopEngaged)
        assertTrue(state.approvalsRequired)
        assertTrue(state.safetyGatesEnabled)
        assertTrue(state.connectedServices.isEmpty())
        // shortcuts always present so the UI can render them as zero-state entries
        assertEquals(0, state.audit.recentEvents)
        assertEquals(0, state.memory.savedFacts)
    }

    @Test
    fun `lockdown renders with the lockdown summary visible`() {
        val state = JarvisControlState(autonomy = AutonomyMode.LOCKDOWN)
        assertTrue(state.isLockdown)
        assertTrue(state.autonomy.summary.contains("paused", ignoreCase = true))
    }

    @Test
    fun `gateway disconnected is visible to the screen`() {
        val state = JarvisControlState(
            gateway = GatewayState.DISCONNECTED,
            gatewayEndpoint = "http://10.0.0.5:8765",
        )
        assertTrue(state.gatewayDisconnected)
    }

    @Test
    fun `autonomy mode change updates the rendered state`() {
        val initial = JarvisControlState(autonomy = AutonomyMode.MANUAL)
        val after = initial.copy(autonomy = AutonomyMode.ASSISTED)
        assertEquals(AutonomyMode.ASSISTED, after.autonomy)
        // ensure the original snapshot did not mutate — state is immutable
        assertEquals(AutonomyMode.MANUAL, initial.autonomy)
    }

    @Test
    fun `disabling approvals surfaces a serious warning on the state`() {
        val action = ControlWarnings.Action.DisableApprovals
        val state = JarvisControlState(
            pendingWarning = PendingWarning(
                level = ControlWarnings.levelFor(action),
                title = "Disable owner approvals?",
                message = "Jarvis will run multi-step work without asking first.",
                confirmLabel = "Disable approvals",
                action = action,
            ),
        )
        assertNotNull(state.pendingWarning)
        assertEquals(WarningLevel.SERIOUS, state.pendingWarning!!.level)
    }

    @Test
    fun `disabling safety gates surfaces a critical warning on the state`() {
        val action = ControlWarnings.Action.DisableSafetyGates
        val state = JarvisControlState(
            pendingWarning = PendingWarning(
                level = ControlWarnings.levelFor(action),
                title = "Disable safety gates?",
                message = "Verification gates are the rails that keep Jarvis owner-loyal.",
                confirmLabel = "Disable safety gates",
                action = action,
            ),
        )
        assertNotNull(state.pendingWarning)
        assertEquals(WarningLevel.CRITICAL, state.pendingWarning!!.level)
    }
}
