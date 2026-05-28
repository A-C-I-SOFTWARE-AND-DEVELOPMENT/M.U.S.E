package com.aci.hermes.ui.screens.control

import com.aci.hermes.data.jarvis.AutonomyMode
import com.aci.hermes.data.jarvis.GatewayState
import com.aci.hermes.data.jarvis.JarvisControlState
import com.aci.hermes.data.jarvis.ServiceState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pins owner-facing copy on the Control surface. The Compose screen
 * reads from [ControlEmptyStateCopy] so a future copy edit can't
 * drift the surface from the contract these tests assert.
 */
class ControlEmptyStateCopyTest {

    @Test
    fun `emergency stop wins over every other state`() {
        val state = JarvisControlState(
            service = ServiceState.RUNNING,
            autonomy = AutonomyMode.LOCKDOWN,
            emergencyStopEngaged = true,
        )
        val out = ControlEmptyStateCopy.serviceSummary(state)
        assertEquals(ControlEmptyStateCopy.SERVICE_EMERGENCY_STOPPED, out)
        assertTrue("must name the owner", out.contains("owner", ignoreCase = true))
    }

    @Test
    fun `lockdown wins over running but loses to emergency stop`() {
        val lockdown = JarvisControlState(
            service = ServiceState.RUNNING,
            autonomy = AutonomyMode.LOCKDOWN,
            emergencyStopEngaged = false,
        )
        assertEquals(
            ControlEmptyStateCopy.SERVICE_LOCKDOWN,
            ControlEmptyStateCopy.serviceSummary(lockdown),
        )
    }

    @Test
    fun `running shows owner control language`() {
        val running = JarvisControlState(service = ServiceState.RUNNING)
        val out = ControlEmptyStateCopy.serviceSummary(running)
        assertTrue("must reference Owner control", out.contains("Owner-controlled"))
        assertTrue("must mention approvals", out.contains("Approvals"))
    }

    @Test
    fun `stopped state guides the owner toward Start`() {
        val stopped = JarvisControlState(service = ServiceState.STOPPED)
        val out = ControlEmptyStateCopy.serviceSummary(stopped)
        assertTrue(out.contains("Start", ignoreCase = false))
        assertTrue(out.contains("ready"))
    }

    @Test
    fun `gateway summary covers every state`() {
        assertEquals(
            ControlEmptyStateCopy.GATEWAY_CONNECTED,
            ControlEmptyStateCopy.gatewaySummary(GatewayState.CONNECTED),
        )
        assertEquals(
            ControlEmptyStateCopy.GATEWAY_DISCONNECTED,
            ControlEmptyStateCopy.gatewaySummary(GatewayState.DISCONNECTED),
        )
        assertEquals(
            ControlEmptyStateCopy.GATEWAY_MOCK,
            ControlEmptyStateCopy.gatewaySummary(GatewayState.MOCK),
        )
        assertEquals(
            ControlEmptyStateCopy.GATEWAY_UNCONFIGURED,
            ControlEmptyStateCopy.gatewaySummary(GatewayState.UNCONFIGURED),
        )
    }

    @Test
    fun `gateway disconnected calls out owner action required`() {
        val out = ControlEmptyStateCopy.gatewaySummary(GatewayState.DISCONNECTED)
        assertTrue("must name owner action", out.contains("owner action", ignoreCase = true))
    }

    @Test
    fun `termux summary distinguishes installed-disconnected vs absent`() {
        assertEquals(
            ControlEmptyStateCopy.TERMUX_CONNECTED,
            ControlEmptyStateCopy.termuxSummary(connected = true, installed = true),
        )
        assertEquals(
            ControlEmptyStateCopy.TERMUX_DISCONNECTED,
            ControlEmptyStateCopy.termuxSummary(connected = false, installed = true),
        )
        assertEquals(
            ControlEmptyStateCopy.TERMUX_ABSENT,
            ControlEmptyStateCopy.termuxSummary(connected = false, installed = false),
        )
    }
}
