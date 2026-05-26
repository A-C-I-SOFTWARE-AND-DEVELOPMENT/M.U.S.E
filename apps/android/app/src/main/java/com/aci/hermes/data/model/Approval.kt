package com.aci.hermes.data.model

import kotlinx.serialization.Serializable
import java.util.UUID

/**
 * Gradient of risk for a queued action. Used by the Approvals UI to
 * decide:
 *  - LOW: silent auto-approve allowed in mock mode only; UI still
 *    surfaces it for review.
 *  - MEDIUM ("risky"): one tap Approve / Reject.
 *  - HIGH ("serious"): requires two taps — Approve, then Approve again
 *    on the confirmation prompt.
 *  - CRITICAL: shows an impact report screen first; user must scroll
 *    through it before the Approve button enables.
 */
@Serializable
enum class ApprovalRisk { LOW, MEDIUM, HIGH, CRITICAL }

@Serializable
enum class ApprovalDecision { PENDING, APPROVED, REJECTED, CANCELLED, EXPIRED }

@Serializable
data class ImpactItem(
    val label: String,
    val value: String,
    val severity: ApprovalRisk = ApprovalRisk.LOW,
)

@Serializable
data class ImpactReport(
    val summary: String,
    val items: List<ImpactItem> = emptyList(),
    val reversible: Boolean = true,
    val blastRadius: String = "single user",
)

@Serializable
data class Approval(
    val id: String = UUID.randomUUID().toString(),
    val title: String = "",
    val description: String = "",
    val proposedAction: String = "",
    val risk: ApprovalRisk = ApprovalRisk.MEDIUM,
    val impact: ImpactReport? = null,
    val decision: ApprovalDecision = ApprovalDecision.PENDING,
    val decidedAt: Long? = null,
    val decisionNotes: String? = null,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
    val source: String = "gateway",
) {
    val isPending: Boolean get() = decision == ApprovalDecision.PENDING
    val isDecided: Boolean get() = decision != ApprovalDecision.PENDING
}
