package com.aci.hermes.data.jarvis

import org.junit.Assert.assertEquals
import org.junit.Test

class ControlWarningsTest {

    @Test
    fun `disabling approvals is a serious warning`() {
        val level = ControlWarnings.levelFor(ControlWarnings.Action.DisableApprovals)
        assertEquals(WarningLevel.SERIOUS, level)
    }

    @Test
    fun `re-enabling approvals does not raise a warning`() {
        val level = ControlWarnings.levelFor(ControlWarnings.Action.EnableApprovals)
        assertEquals(WarningLevel.NONE, level)
    }

    @Test
    fun `disabling safety gates is a critical warning`() {
        val level = ControlWarnings.levelFor(ControlWarnings.Action.DisableSafetyGates)
        assertEquals(WarningLevel.CRITICAL, level)
    }

    @Test
    fun `changing gateway endpoint warns the owner`() {
        val level = ControlWarnings.levelFor(
            ControlWarnings.Action.GatewayEndpointChange(
                from = "http://127.0.0.1:8765",
                to = "http://10.0.0.5:8765",
            )
        )
        assertEquals(WarningLevel.NOTICE, level)
    }

    @Test
    fun `same gateway endpoint produces no warning`() {
        val same = "http://127.0.0.1:8765"
        val level = ControlWarnings.levelFor(
            ControlWarnings.Action.GatewayEndpointChange(from = same, to = same)
        )
        assertEquals(WarningLevel.NONE, level)
    }

    @Test
    fun `switching to lockdown is a serious warning`() {
        val level = ControlWarnings.levelFor(
            ControlWarnings.Action.AutonomyChange(
                from = AutonomyMode.ASSISTED,
                to = AutonomyMode.LOCKDOWN,
            )
        )
        assertEquals(WarningLevel.SERIOUS, level)
    }

    @Test
    fun `dropping to manual is unguarded`() {
        val level = ControlWarnings.levelFor(
            ControlWarnings.Action.AutonomyChange(
                from = AutonomyMode.TRUSTED_LOW_RISK,
                to = AutonomyMode.MANUAL,
            )
        )
        assertEquals(WarningLevel.NONE, level)
    }

    @Test
    fun `escalating to trusted low risk is a serious warning`() {
        val level = ControlWarnings.levelFor(
            ControlWarnings.Action.AutonomyChange(
                from = AutonomyMode.MANUAL,
                to = AutonomyMode.TRUSTED_LOW_RISK,
            )
        )
        assertEquals(WarningLevel.SERIOUS, level)
    }

    @Test
    fun `escalating to high-autonomy coding is a serious warning`() {
        val level = ControlWarnings.levelFor(
            ControlWarnings.Action.AutonomyChange(
                from = AutonomyMode.ASSISTED,
                to = AutonomyMode.OWNER_HIGH_AUTONOMY_CODING,
            )
        )
        assertEquals(WarningLevel.SERIOUS, level)
    }

    @Test
    fun `emergency stop is a serious warning`() {
        val level = ControlWarnings.levelFor(ControlWarnings.Action.EmergencyStop)
        assertEquals(WarningLevel.SERIOUS, level)
    }
}
