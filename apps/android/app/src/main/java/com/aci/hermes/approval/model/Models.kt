package com.aci.hermes.approval.model

/**
 * Risk tiers that determine the approval flow.
 *
 * The app NEVER executes destructive work directly. It emits gateway/runtime
 * approval events; the runtime decides what to actually do.
 */
enum class ApprovalRiskTier {
    SAFE,       // no approval, runtime auto-runs
    LOW,        // execute + report
    RISKY,      // single approval
    SERIOUS,    // two confirmations
    CRITICAL,   // impact report + rollback plan + two confirmations
    FORBIDDEN   // refuse, never approvable
}

enum class ApprovalStatus {
    PENDING,
    APPROVED,
    REJECTED,
    EXPIRED,
    EMERGENCY_STOPPED
}

/**
 * Per-step state for SERIOUS actions: an initial approval followed by a
 * consequence-confirmation step that is gated on the first.
 */
data class SeriousActionState(
    val step1Approved: Boolean = false,
    val step2Approved: Boolean = false
) {
    val canConfirmStep2: Boolean get() = step1Approved
    val complete: Boolean get() = step1Approved && step2Approved
}

/**
 * An item describing one impacted surface in a CRITICAL action — e.g.
 * a service, table, account, or external system.
 */
data class CriticalImpactReport(
    val summary: String,
    val impactedSurfaces: List<String>,
    val blastRadius: String,
    val reversible: Boolean
) {
    val isComplete: Boolean
        get() = summary.isNotBlank() &&
            impactedSurfaces.isNotEmpty() &&
            blastRadius.isNotBlank()
}

/**
 * The rollback plan attached to every CRITICAL action.
 */
data class RollbackPlan(
    val steps: List<String>,
    val estimatedDurationSeconds: Long,
    val verified: Boolean
) {
    val isComplete: Boolean get() = steps.isNotEmpty() && estimatedDurationSeconds > 0
}

/**
 * Per-step state for CRITICAL actions: requires an impact report, a
 * rollback plan, and TWO confirmations before it can fire.
 */
data class CriticalActionState(
    val impactReport: CriticalImpactReport? = null,
    val rollbackPlan: RollbackPlan? = null,
    val step1Approved: Boolean = false,
    val step2Approved: Boolean = false
) {
    val hasImpactReport: Boolean get() = impactReport?.isComplete == true
    val hasRollbackPlan: Boolean get() = rollbackPlan?.isComplete == true
    val canApproveStep1: Boolean get() = hasImpactReport && hasRollbackPlan
    val canApproveStep2: Boolean get() = canApproveStep1 && step1Approved
    val complete: Boolean get() = canApproveStep1 && step1Approved && step2Approved
}

/**
 * A single approval request the user sees on the Approvals screen.
 *
 * Cards are immutable; the [com.aci.hermes.approval.state.ApprovalStore]
 * swaps new ones in on transitions.
 */
data class ApprovalCard(
    val id: String,
    val title: String,
    val summary: String,
    val requester: String,
    val tier: ApprovalRiskTier,
    val status: ApprovalStatus = ApprovalStatus.PENDING,
    val createdAtMillis: Long,
    val expiresAtMillis: Long,
    val proposedAction: String,
    val seriousState: SeriousActionState = SeriousActionState(),
    val criticalState: CriticalActionState = CriticalActionState(),
    val editedNote: String? = null
) {
    /** True when this card has timed out and can no longer be executed. */
    fun isExpired(nowMillis: Long): Boolean =
        nowMillis >= expiresAtMillis && status == ApprovalStatus.PENDING

    /** True when an emergency stop should be displayed for this tier. */
    val showsEmergencyStop: Boolean
        get() = tier == ApprovalRiskTier.SERIOUS || tier == ApprovalRiskTier.CRITICAL
}

/**
 * A historical record of an approval decision.
 */
data class ApprovalHistoryItem(
    val cardId: String,
    val title: String,
    val tier: ApprovalRiskTier,
    val outcome: ApprovalStatus,
    val decidedAtMillis: Long,
    val decidedBy: String,
    val note: String? = null
)
