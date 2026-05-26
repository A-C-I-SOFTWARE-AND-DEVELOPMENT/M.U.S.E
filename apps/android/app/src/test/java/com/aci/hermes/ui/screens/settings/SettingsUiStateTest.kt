package com.aci.hermes.ui.screens.settings

import com.aci.hermes.data.jarvis.AutonomyMode
import com.aci.hermes.data.jarvis.ControlWarnings
import com.aci.hermes.data.jarvis.PendingWarning
import com.aci.hermes.data.jarvis.ResponseLength
import com.aci.hermes.data.jarvis.WarningLevel
import com.aci.hermes.data.preferences.SettingsRepository
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SettingsUiStateTest {

    @Test
    fun `settings renders with every Jarvis Prime field present`() {
        val state = SettingsUiState()
        assertEquals(ResponseLength.BALANCED, state.responseLength)
        assertTrue(state.mobileMode)
        assertTrue(state.notificationsEnabled)
        assertEquals(false, state.voiceEnabled)
        assertTrue(state.interactiveIconEnabled)
        assertEquals(SettingsRepository.DEFAULT_GATEWAY_ENDPOINT, state.gatewayEndpoint)
        assertEquals(false, state.mockMode)
        assertEquals(false, state.termuxGatewayMode)
        assertTrue(state.approvalsRequired)
        assertTrue(state.privacyLocalOnlyMemory)
        assertEquals(AutonomyMode.MANUAL, state.autonomyMode)
        assertNull(state.pendingWarning)
    }

    @Test
    fun `disabling approvals produces a serious warning copy that the screen can render`() {
        val action = ControlWarnings.Action.DisableApprovals
        val level = ControlWarnings.levelFor(action)
        val warning = PendingWarning(
            level = level,
            title = "Disable owner approvals?",
            message = "Jarvis will run multi-step work without asking first.",
            confirmLabel = "Disable approvals",
            action = action,
        )
        val state = SettingsUiState(pendingWarning = warning)
        assertNotNull(state.pendingWarning)
        assertEquals(WarningLevel.SERIOUS, state.pendingWarning!!.level)
        assertEquals(action, state.pendingWarning!!.action)
    }

    @Test
    fun `disabling safety gates is critical when surfaced as a warning`() {
        val action = ControlWarnings.Action.DisableSafetyGates
        val level = ControlWarnings.levelFor(action)
        assertEquals(WarningLevel.CRITICAL, level)
    }

    @Test
    fun `gateway endpoint change carries a notice level`() {
        val action = ControlWarnings.Action.GatewayEndpointChange(
            from = SettingsRepository.DEFAULT_GATEWAY_ENDPOINT,
            to = "https://gateway.example.com",
        )
        assertEquals(WarningLevel.NOTICE, ControlWarnings.levelFor(action))
    }
}
