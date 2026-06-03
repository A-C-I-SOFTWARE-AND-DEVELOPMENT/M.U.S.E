package com.aci.hermes.data.devicecontrol

import com.aci.hermes.data.automation.AutomationIntent
import com.aci.hermes.data.automation.ScrollDirection
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The four safety scenarios the device-control broker must enforce:
 * permission missing, action blocked (emergency stop), action approved,
 * and the sensitive-action confirmation gate. Pure JVM — no device.
 */
class DeviceActionBrokerTest {

    private val standardIntent = AutomationIntent.Scroll(ScrollDirection.DOWN)
    private val sensitiveIntent = AutomationIntent.OpenApp("facebook")

    private val allCaps = DeviceControlCapability.entries.toSet()

    private fun consent(
        enabled: Boolean = true,
        capabilities: Set<DeviceControlCapability> = allCaps,
        confirmSensitive: Boolean = true,
    ) = DeviceConsentState(
        enabled = enabled,
        consentedCapabilities = capabilities,
        confirmSensitiveActions = confirmSensitive,
    )

    // ── 1. permission missing ───────────────────────────────────────────

    @Test
    fun `blocks when a required capability is not granted by the OS`() {
        val packet = DeviceActionPacket.from(standardIntent)
        val decision = DeviceActionBroker.evaluate(
            packet = packet,
            consent = consent(),
            emergencyEngaged = false,
            grantedCapabilities = emptySet(), // ACCESSIBILITY not granted
        )
        assertEquals(BrokerDecision.Blocked(BlockReason.MISSING_PERMISSION), decision)
    }

    @Test
    fun `blocks when a required capability is granted but not consented`() {
        val packet = DeviceActionPacket.from(standardIntent)
        val decision = DeviceActionBroker.evaluate(
            packet = packet,
            consent = consent(capabilities = emptySet()), // owner hasn't consented
            emergencyEngaged = false,
            grantedCapabilities = allCaps,
        )
        assertEquals(BrokerDecision.Blocked(BlockReason.MISSING_PERMISSION), decision)
    }

    @Test
    fun `blocks when the master switch is off`() {
        val decision = DeviceActionBroker.evaluate(
            packet = DeviceActionPacket.from(standardIntent),
            consent = consent(enabled = false),
            emergencyEngaged = false,
            grantedCapabilities = allCaps,
        )
        assertEquals(BrokerDecision.Blocked(BlockReason.CONSENT_DISABLED), decision)
    }

    // ── 2. action blocked (emergency stop) ──────────────────────────────

    @Test
    fun `emergency stop blocks even a fully-consented granted action`() {
        val decision = DeviceActionBroker.evaluate(
            packet = DeviceActionPacket.from(standardIntent),
            consent = consent(),
            emergencyEngaged = true,
            grantedCapabilities = allCaps,
        )
        assertEquals(BrokerDecision.Blocked(BlockReason.EMERGENCY_STOP), decision)
    }

    // ── 3. action approved ──────────────────────────────────────────────

    @Test
    fun `approves a standard action when enabled granted and consented`() {
        val packet = DeviceActionPacket.from(standardIntent)
        val decision = DeviceActionBroker.evaluate(
            packet = packet,
            consent = consent(),
            emergencyEngaged = false,
            grantedCapabilities = allCaps,
        )
        assertEquals(BrokerDecision.Approved, decision)

        val entry = DeviceActionBroker.logEntryFor(packet, decision, now = 1_000L)
        assertEquals(DeviceActionLogEntry.Outcome.APPROVED, entry.outcome)
        assertEquals(1_000L, entry.timestamp)
        assertEquals("Scroll down", entry.intentLabel)
    }

    @Test
    fun `approves a sensitive action when confirmation is turned off`() {
        val decision = DeviceActionBroker.evaluate(
            packet = DeviceActionPacket.from(sensitiveIntent),
            consent = consent(confirmSensitive = false),
            emergencyEngaged = false,
            grantedCapabilities = allCaps,
        )
        assertEquals(BrokerDecision.Approved, decision)
    }

    // ── 4. sensitive-action confirmation gate ───────────────────────────

    @Test
    fun `holds a sensitive action for confirmation by default`() {
        val packet = DeviceActionPacket.from(sensitiveIntent)
        val decision = DeviceActionBroker.evaluate(
            packet = packet,
            consent = consent(confirmSensitive = true),
            emergencyEngaged = false,
            grantedCapabilities = allCaps,
        )
        assertEquals(BrokerDecision.NeedsConfirmation, decision)

        val entry = DeviceActionBroker.logEntryFor(packet, decision, now = 5L)
        assertEquals(DeviceActionLogEntry.Outcome.NEEDS_CONFIRMATION, entry.outcome)
        assertEquals(DeviceActionSensitivity.SENSITIVE, entry.sensitivity)
    }

    @Test
    fun `block log entry records the reason`() {
        val packet = DeviceActionPacket.from(standardIntent)
        val decision = BrokerDecision.Blocked(BlockReason.EMERGENCY_STOP)
        val entry = DeviceActionBroker.logEntryFor(packet, decision, now = 0L)
        assertEquals(DeviceActionLogEntry.Outcome.BLOCKED, entry.outcome)
        assertTrue(entry.reason?.contains("emergency") == true)
    }
}
