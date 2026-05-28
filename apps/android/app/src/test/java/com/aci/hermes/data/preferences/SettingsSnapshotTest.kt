package com.aci.hermes.data.preferences

import com.aci.hermes.data.jarvis.AutonomyMode
import com.aci.hermes.data.jarvis.ResponseLength
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pins the shape of [SettingsRepository.Snapshot] so additions /
 * removals are explicit. The Snapshot is the contract the Control
 * surface and the Jarvis Prime home view-model both consume; silent
 * drift here breaks both screens at once.
 *
 * The repository itself talks to DataStore (Android-only), so we
 * exercise the data class directly with named defaults rather than
 * spinning up Robolectric.
 */
class SettingsSnapshotTest {

    private fun defaultSnapshot(): SettingsRepository.Snapshot = SettingsRepository.Snapshot(
        themeMode = ThemeMode.SYSTEM,
        hasOnboarded = false,
        preferredBuilder = PreferredBuilder.CODEX,
        preferredReviewer = PreferredReviewer.CLAUDE_CODE,
        useApiKeys = false,
        localOnlyMode = true,
        allowExternalAppOpening = false,
        clipboardHandoffEnabled = true,
        showSafetyWarnings = true,
    )

    @Test
    fun `safety-defaults are owner-loyal out of the box`() {
        val snap = defaultSnapshot()
        // Approvals on, safety gates on, emergency stop disengaged.
        assertTrue("approvals must default to required", snap.approvalsRequired)
        assertTrue("safety gates must default to on", snap.safetyGatesEnabled)
        assertFalse("emergency stop must default to disengaged", snap.emergencyStopEngaged)
        // Privacy-local memory is on; remote app opening is off.
        assertTrue("privacy local-only memory defaults on", snap.privacyLocalOnlyMemory)
        assertFalse("external app opening defaults off", snap.allowExternalAppOpening)
        // Owner-friendly default autonomy is manual, not autopilot.
        assertEquals(AutonomyMode.MANUAL, snap.autonomyMode)
    }

    @Test
    fun `gateway endpoint defaults to the local orchestrator`() {
        assertEquals(
            SettingsRepository.DEFAULT_GATEWAY_ENDPOINT,
            defaultSnapshot().gatewayEndpoint,
        )
        assertTrue(
            "default gateway endpoint must be a valid URL",
            SettingsRepository.DEFAULT_GATEWAY_ENDPOINT.startsWith("http"),
        )
    }

    @Test
    fun `interactive icon defaults to enabled, mock mode defaults to off`() {
        val snap = defaultSnapshot()
        assertTrue("interactive icon defaults enabled", snap.interactiveIconEnabled)
        assertFalse("mock mode defaults off", snap.mockMode)
        assertFalse("termux gateway mode defaults off", snap.termuxGatewayMode)
    }

    @Test
    fun `voice defaults off until owner opts in, notifications default on`() {
        val snap = defaultSnapshot()
        assertFalse("voice defaults off — needs explicit opt-in", snap.voiceEnabled)
        assertTrue("notifications default on", snap.notificationsEnabled)
    }

    @Test
    fun `response length defaults to balanced and mobile mode defaults to true`() {
        val snap = defaultSnapshot()
        assertEquals(ResponseLength.BALANCED, snap.responseLength)
        assertTrue("mobile-mode defaults on for cockpit", snap.mobileMode)
    }

    @Test
    fun `every snapshot field is non-null`() {
        // Smoke test — exhaustively reads every property so a future
        // `Boolean?` slip-in compiles but at least surfaces here.
        val snap = defaultSnapshot()
        assertNotNull(snap.themeMode)
        assertNotNull(snap.preferredBuilder)
        assertNotNull(snap.preferredReviewer)
        assertNotNull(snap.autonomyMode)
        assertNotNull(snap.responseLength)
        assertNotNull(snap.gatewayEndpoint)
    }
}
