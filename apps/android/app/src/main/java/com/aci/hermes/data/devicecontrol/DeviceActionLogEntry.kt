package com.aci.hermes.data.devicecontrol

import kotlinx.serialization.Serializable

/**
 * One entry in the local, append-only device-action ledger. Every device
 * action — approved, refused, or executed — produces an entry, so the
 * owner can always answer "what did Jarvis do on my phone?".
 *
 * Deliberately minimal: the action's human-readable label, its
 * sensitivity, the outcome, and a reason. No screen contents, no
 * transcripts, no chain-of-thought, no secrets ever land here.
 */
@Serializable
data class DeviceActionLogEntry(
    val timestamp: Long,
    val intentLabel: String,
    val sensitivity: DeviceActionSensitivity,
    val outcome: Outcome,
    /** Block reason or short note; null for a plain approval. */
    val reason: String? = null,
) {
    @Serializable
    enum class Outcome {
        /** Broker approved the action (it will be executed next). */
        APPROVED,

        /** Sensitive action held back pending explicit confirmation. */
        NEEDS_CONFIRMATION,

        /** Broker refused the action (see [reason]). */
        BLOCKED,

        /** The approved gesture was dispatched to the device. */
        EXECUTED,

        /** Execution was attempted but the device reported failure. */
        EXECUTION_FAILED,
    }

    companion object {
        /** Keep the on-disk ledger bounded; oldest entries roll off. */
        const val MAX_ENTRIES = 500
    }
}
