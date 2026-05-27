package com.aci.hermes.data.emergency

import kotlinx.serialization.Serializable

/**
 * Single entry in the tamper-evident-ish emergency stop audit log.
 * The log is local-only; it is intentionally append-only from the
 * controller's perspective. The repository may trim old entries past
 * [MAX_AUDIT_ENTRIES] to keep the file bounded.
 */
@Serializable
data class EmergencyStopAuditEvent(
    val timestamp: Long,
    val type: EventType,
    val from: EmergencyStopState,
    val to: EmergencyStopState,
    val source: String,
    val reason: String? = null,
    val approval: ApprovalSnapshot? = null,
) {
    @Serializable
    enum class EventType {
        ENGAGE,
        ESCALATE,
        DEESCALATE,
        RESUME,
        RESUME_REQUESTED,
        RESUME_APPROVED,
        RESUME_DENIED,
        BLOCKED_ACTION,
    }

    @Serializable
    data class ApprovalSnapshot(
        val requestedAt: Long,
        val approvedAt: Long?,
        val approver: String?,
        val approved: Boolean,
    )

    companion object {
        const val MAX_AUDIT_ENTRIES = 500
    }
}

/**
 * Outstanding request to resume from an active emergency stop level.
 * Created by [EmergencyStopController.requestResume]; cleared once
 * approved or denied.
 */
@Serializable
data class ResumeApproval(
    val id: String,
    val requestedAt: Long,
    val fromState: EmergencyStopState,
    val requestedBy: String,
    val reason: String? = null,
)
