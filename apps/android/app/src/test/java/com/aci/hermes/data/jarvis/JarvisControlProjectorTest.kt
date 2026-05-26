package com.aci.hermes.data.jarvis

import com.aci.hermes.data.preferences.PreferredBuilder
import com.aci.hermes.data.preferences.PreferredReviewer
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.data.preferences.ThemeMode
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class JarvisControlProjectorTest {

    private fun snap(
        autonomy: AutonomyMode = AutonomyMode.MANUAL,
        gateway: String = SettingsRepository.DEFAULT_GATEWAY_ENDPOINT,
        mockMode: Boolean = false,
        approvals: Boolean = true,
        safetyGates: Boolean = true,
        emergency: Boolean = false,
        notifications: Boolean = true,
        voice: Boolean = false,
        icon: Boolean = true,
    ): SettingsRepository.Snapshot = SettingsRepository.Snapshot(
        themeMode = ThemeMode.SYSTEM,
        hasOnboarded = true,
        preferredBuilder = PreferredBuilder.CODEX,
        preferredReviewer = PreferredReviewer.CLAUDE_CODE,
        useApiKeys = false,
        localOnlyMode = true,
        allowExternalAppOpening = false,
        clipboardHandoffEnabled = true,
        showSafetyWarnings = true,
        autonomyMode = autonomy,
        responseLength = ResponseLength.BALANCED,
        mobileMode = true,
        notificationsEnabled = notifications,
        voiceEnabled = voice,
        interactiveIconEnabled = icon,
        gatewayEndpoint = gateway,
        mockMode = mockMode,
        termuxGatewayMode = false,
        approvalsRequired = approvals,
        safetyGatesEnabled = safetyGates,
        privacyLocalOnlyMemory = true,
        emergencyStopEngaged = emergency,
    )

    @Test
    fun `control renders with every status field populated`() {
        val state = JarvisControlProjector.project(
            snapshot = snap(),
            serviceRunning = true,
            gatewayReachable = true,
        )
        assertTrue(state.jarvisRunning)
        assertEquals(ServiceState.RUNNING, state.service)
        assertEquals(GatewayState.CONNECTED, state.gateway)
        assertEquals(AutonomyMode.MANUAL, state.autonomy)
        assertEquals(PermissionState.GRANTED, state.permissions)
        assertEquals(NotificationsState.ENABLED, state.notifications)
        assertEquals(VoiceState.DISABLED, state.voice)
        assertEquals(IconState.ENABLED, state.icon)
        assertFalse(state.emergencyStopEngaged)
        assertTrue(state.approvalsRequired)
        assertTrue(state.safetyGatesEnabled)
    }

    @Test
    fun `gateway disconnected is visible when service unreachable`() {
        val state = JarvisControlProjector.project(
            snapshot = snap(gateway = "http://10.0.0.5:8765", mockMode = false),
            serviceRunning = true,
            gatewayReachable = false,
        )
        assertEquals(GatewayState.DISCONNECTED, state.gateway)
        assertTrue(state.gatewayDisconnected)
    }

    @Test
    fun `mock mode flips gateway to mock`() {
        val state = JarvisControlProjector.project(
            snapshot = snap(mockMode = true),
            serviceRunning = true,
            gatewayReachable = false,
        )
        assertEquals(GatewayState.MOCK, state.gateway)
        assertFalse(state.gatewayDisconnected)
    }

    @Test
    fun `blank endpoint is treated as unconfigured`() {
        val state = JarvisControlProjector.project(
            snapshot = snap(gateway = ""),
            serviceRunning = true,
            gatewayReachable = true,
        )
        assertEquals(GatewayState.UNCONFIGURED, state.gateway)
    }

    @Test
    fun `lockdown renders even when service was running`() {
        val state = JarvisControlProjector.project(
            snapshot = snap(autonomy = AutonomyMode.LOCKDOWN),
            serviceRunning = true,
            gatewayReachable = true,
        )
        assertEquals(AutonomyMode.LOCKDOWN, state.autonomy)
        assertTrue(state.isLockdown)
    }

    @Test
    fun `emergency stop forces service stopped`() {
        val state = JarvisControlProjector.project(
            snapshot = snap(emergency = true),
            serviceRunning = true,
            gatewayReachable = true,
        )
        assertEquals(ServiceState.STOPPED, state.service)
        assertFalse(state.jarvisRunning)
        assertTrue(state.emergencyStopEngaged)
    }

    @Test
    fun `autonomy mode change is reflected in the next projection`() {
        val before = JarvisControlProjector.project(
            snapshot = snap(autonomy = AutonomyMode.MANUAL),
            serviceRunning = true,
            gatewayReachable = true,
        )
        val after = JarvisControlProjector.project(
            snapshot = snap(autonomy = AutonomyMode.ASSISTED),
            serviceRunning = true,
            gatewayReachable = true,
        )
        assertEquals(AutonomyMode.MANUAL, before.autonomy)
        assertEquals(AutonomyMode.ASSISTED, after.autonomy)
    }

    @Test
    fun `voice and icon status reflect settings`() {
        val state = JarvisControlProjector.project(
            snapshot = snap(voice = true, icon = false, notifications = false),
            serviceRunning = true,
            gatewayReachable = true,
        )
        assertEquals(VoiceState.ENABLED, state.voice)
        assertEquals(IconState.DISABLED, state.icon)
        assertEquals(NotificationsState.DISABLED, state.notifications)
    }
}
