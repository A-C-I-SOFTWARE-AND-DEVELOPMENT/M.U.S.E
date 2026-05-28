package com.aci.hermes.ui.screens.control

import com.aci.hermes.data.jarvis.AutonomyMode
import com.aci.hermes.data.jarvis.ConnectedService
import com.aci.hermes.data.jarvis.GatewayState
import com.aci.hermes.data.jarvis.JarvisControlState
import com.aci.hermes.data.jarvis.ServiceState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Asserts the cockpit-level invariants for lockdown and emergency-stop
 * state on the Control screen. The screen reads from a
 * [JarvisControlState] (via [orchestratorAsControlState] until the
 * full projector lands), so these tests pin the state→copy
 * relationship that the UI depends on.
 */
class ControlLockdownStateTest {

    @Test
    fun `orchestratorAsControlState reflects service liveness`() {
        val running = orchestratorAsControlState(serviceRunning = true)
        val stopped = orchestratorAsControlState(serviceRunning = false)

        assertEquals(ServiceState.RUNNING, running.service)
        assertTrue(running.jarvisRunning)

        assertEquals(ServiceState.STOPPED, stopped.service)
        assertFalse(stopped.jarvisRunning)
    }

    @Test
    fun `orchestratorAsControlState always reports gateway as unconfigured until projector lands`() {
        val state = orchestratorAsControlState(serviceRunning = true)
        assertEquals(GatewayState.UNCONFIGURED, state.gateway)
    }

    @Test
    fun `orchestratorAsControlState always exposes Termux as a known service slot`() {
        val state = orchestratorAsControlState(serviceRunning = true)
        val termux = state.connectedServices.firstOrNull { it.id == "termux" }
        assertTrue("Termux slot must exist so the screen can render the pill", termux != null)
        assertFalse("Termux defaults to disconnected", termux!!.connected)
    }

    @Test
    fun `lockdown autonomy projects with summary that names lockdown`() {
        val state = JarvisControlState(
            service = ServiceState.RUNNING,
            autonomy = AutonomyMode.LOCKDOWN,
        )
        val out = ControlEmptyStateCopy.serviceSummary(state)
        assertTrue("must name lockdown", out.contains("Lockdown", ignoreCase = true))
        assertTrue("must explain paused state", out.contains("paused", ignoreCase = true))
    }

    @Test
    fun `emergency stop projects with summary that calls out owner release`() {
        val state = JarvisControlState(
            service = ServiceState.RUNNING,
            emergencyStopEngaged = true,
        )
        val out = ControlEmptyStateCopy.serviceSummary(state)
        assertTrue("must mention release", out.contains("Release", ignoreCase = true))
        assertTrue("must mention owner", out.contains("owner", ignoreCase = true))
    }

    @Test
    fun `mock gateway is always identified as fake to the owner`() {
        val state = JarvisControlState(
            mockMode = true,
            gateway = GatewayState.MOCK,
            connectedServices = listOf(
                ConnectedService(id = "termux", displayName = "Termux", connected = false),
            ),
        )
        val out = ControlEmptyStateCopy.gatewaySummary(state.gateway)
        assertTrue("must call out mock", out.contains("Mock", ignoreCase = true))
        assertTrue("must mark as fake/owner-only", out.contains("fake", ignoreCase = true))
    }
}
