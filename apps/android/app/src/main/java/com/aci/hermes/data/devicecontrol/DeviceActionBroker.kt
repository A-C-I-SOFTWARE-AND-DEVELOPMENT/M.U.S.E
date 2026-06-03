package com.aci.hermes.data.devicecontrol

/** Why the broker refused an action. */
enum class BlockReason {
    /** The emergency stop is engaged — every action is dropped. */
    EMERGENCY_STOP,

    /** The master device-control switch is off. */
    CONSENT_DISABLED,

    /** A required capability is not consented by the owner or not granted by the OS. */
    MISSING_PERMISSION,
}

/** The broker's verdict for a single [DeviceActionPacket]. */
sealed interface BrokerDecision {
    /** Cleared to run now. */
    data object Approved : BrokerDecision

    /** A sensitive action that must be explicitly confirmed before it runs. */
    data object NeedsConfirmation : BrokerDecision

    /** Refused; [reason] explains why. */
    data class Blocked(val reason: BlockReason) : BrokerDecision
}

/**
 * The single chokepoint every device action passes through. It is a pure
 * function of the action plus the current consent / emergency / granted
 * state, so the safety rules are exhaustively unit-testable with no
 * Android device in the loop.
 *
 * Precedence (safety first):
 *  1. emergency stop engaged → always [BrokerDecision.Blocked].
 *  2. master switch off       → blocked.
 *  3. a required capability not consented *and* OS-granted → blocked.
 *  4. sensitive + confirmation required → [BrokerDecision.NeedsConfirmation].
 *  5. otherwise → [BrokerDecision.Approved].
 *
 * The broker never executes anything; it only decides and produces the
 * ledger entry that records the decision. The Android-facing
 * [DeviceControlController] does the resolving, executing, and logging.
 */
object DeviceActionBroker {

    fun evaluate(
        packet: DeviceActionPacket,
        consent: DeviceConsentState,
        emergencyEngaged: Boolean,
        grantedCapabilities: Set<DeviceControlCapability>,
    ): BrokerDecision {
        if (emergencyEngaged) return BrokerDecision.Blocked(BlockReason.EMERGENCY_STOP)
        if (!consent.enabled) return BrokerDecision.Blocked(BlockReason.CONSENT_DISABLED)

        val missing = packet.requiredCapabilities.any { cap ->
            cap !in grantedCapabilities || !consent.hasConsented(cap)
        }
        if (missing) return BrokerDecision.Blocked(BlockReason.MISSING_PERMISSION)

        if (packet.sensitivity == DeviceActionSensitivity.SENSITIVE && consent.confirmSensitiveActions) {
            return BrokerDecision.NeedsConfirmation
        }
        return BrokerDecision.Approved
    }

    /** Build the ledger entry that records a [decision] for [packet]. */
    fun logEntryFor(
        packet: DeviceActionPacket,
        decision: BrokerDecision,
        now: Long,
    ): DeviceActionLogEntry {
        val (outcome, reason) = when (decision) {
            BrokerDecision.Approved ->
                DeviceActionLogEntry.Outcome.APPROVED to null
            BrokerDecision.NeedsConfirmation ->
                DeviceActionLogEntry.Outcome.NEEDS_CONFIRMATION to "awaiting confirmation"
            is BrokerDecision.Blocked ->
                DeviceActionLogEntry.Outcome.BLOCKED to decision.reason.name.lowercase()
        }
        return DeviceActionLogEntry(
            timestamp = now,
            intentLabel = packet.previewLabel,
            sensitivity = packet.sensitivity,
            outcome = outcome,
            reason = reason,
        )
    }
}
