package com.aci.hermes.approval.event

import com.aci.hermes.approval.model.ApprovalRiskTier

/**
 * Events emitted by the app toward the Hermes gateway/runtime.
 *
 * The app NEVER performs the destructive action itself. It produces these
 * events and the runtime is responsible for everything that touches the
 * outside world. This separation is what makes the approval system safe.
 */
sealed interface ApprovalEvent {
    val cardId: String
    val tier: ApprovalRiskTier
    val emittedAtMillis: Long

    data class Approved(
        override val cardId: String,
        override val tier: ApprovalRiskTier,
        override val emittedAtMillis: Long,
        val confirmations: Int,
        val note: String? = null
    ) : ApprovalEvent

    data class Rejected(
        override val cardId: String,
        override val tier: ApprovalRiskTier,
        override val emittedAtMillis: Long,
        val reason: String? = null
    ) : ApprovalEvent

    data class Edited(
        override val cardId: String,
        override val tier: ApprovalRiskTier,
        override val emittedAtMillis: Long,
        val editedAction: String
    ) : ApprovalEvent

    data class Expired(
        override val cardId: String,
        override val tier: ApprovalRiskTier,
        override val emittedAtMillis: Long
    ) : ApprovalEvent

    data class EmergencyStopped(
        override val cardId: String,
        override val tier: ApprovalRiskTier,
        override val emittedAtMillis: Long
    ) : ApprovalEvent
}

/**
 * Sink the UI calls to publish approval decisions to the runtime.
 *
 * Production code wires this to the gateway transport (mTLS, websocket, etc).
 * Tests and previews use the in-memory implementation.
 */
fun interface ApprovalEventSink {
    fun emit(event: ApprovalEvent)
}

/** In-memory sink used by tests and previews. */
class RecordingApprovalEventSink : ApprovalEventSink {
    private val _events = mutableListOf<ApprovalEvent>()
    val events: List<ApprovalEvent> get() = _events.toList()

    override fun emit(event: ApprovalEvent) {
        _events += event
    }

    fun clear() = _events.clear()
}
