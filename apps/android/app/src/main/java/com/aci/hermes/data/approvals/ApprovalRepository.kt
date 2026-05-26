package com.aci.hermes.data.approvals

import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.model.Approval
import com.aci.hermes.data.model.ApprovalDecision
import com.aci.hermes.data.model.ApprovalRisk
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * In-memory approvals queue. The decision gating logic is intentionally
 * here (not in the UI) so it can be unit tested.
 *
 *   - LOW / MEDIUM: one tap decides.
 *   - HIGH (serious): caller must pass `confirmedTwice = true`
 *     (the UI achieves this by showing a re-confirmation prompt).
 *   - CRITICAL: caller must pass `impactReportShown = true` AND
 *     `confirmedTwice = true`.
 *   - Emergency stop blocks every decision regardless of risk.
 */
class ApprovalRepository(
    private val emergency: EmergencyStopController,
) {

    private val _items = MutableStateFlow<List<Approval>>(emptyList())
    val items: StateFlow<List<Approval>> = _items.asStateFlow()

    fun replaceAll(items: List<Approval>) {
        _items.value = items.sortedWith(approvalOrder)
    }

    fun upsert(approval: Approval) {
        val list = _items.value.toMutableList()
        val idx = list.indexOfFirst { it.id == approval.id }
        if (idx >= 0) list[idx] = approval else list.add(approval)
        _items.value = list.sortedWith(approvalOrder)
    }

    fun byId(id: String): Approval? = _items.value.firstOrNull { it.id == id }

    fun pending(): List<Approval> = _items.value.filter { it.isPending }

    fun decide(
        approval: Approval,
        approve: Boolean,
        confirmedTwice: Boolean = false,
        impactReportShown: Boolean = false,
        notes: String? = null,
    ): DecisionResult {
        if (emergency.isArmed()) return DecisionResult.BlockedByEmergencyStop
        when (approval.risk) {
            ApprovalRisk.HIGH -> if (!confirmedTwice) return DecisionResult.NeedsSecondConfirmation
            ApprovalRisk.CRITICAL -> {
                if (!impactReportShown) return DecisionResult.NeedsImpactReport
                if (!confirmedTwice) return DecisionResult.NeedsSecondConfirmation
            }
            ApprovalRisk.MEDIUM, ApprovalRisk.LOW -> Unit
        }
        if (!approval.isPending) return DecisionResult.AlreadyDecided
        val now = System.currentTimeMillis()
        val updated = approval.copy(
            decision = if (approve) ApprovalDecision.APPROVED else ApprovalDecision.REJECTED,
            decidedAt = now,
            decisionNotes = notes,
            updatedAt = now,
        )
        upsert(updated)
        return DecisionResult.Decided(updated)
    }

    sealed interface DecisionResult {
        data class Decided(val approval: Approval) : DecisionResult
        data object NeedsSecondConfirmation : DecisionResult
        data object NeedsImpactReport : DecisionResult
        data object BlockedByEmergencyStop : DecisionResult
        data object AlreadyDecided : DecisionResult
    }

    private companion object {
        val approvalOrder = compareByDescending<Approval> { it.isPending }
            .thenByDescending { it.risk.ordinal }
            .thenByDescending { it.createdAt }
    }
}
