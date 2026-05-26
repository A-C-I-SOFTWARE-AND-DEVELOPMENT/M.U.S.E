package com.aci.hermes.ui.screens.approvals

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.approvals.ApprovalRepository
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.gateway.GatewayEventSpine
import com.aci.hermes.data.model.Approval
import com.aci.hermes.data.model.AuditEvent
import com.aci.hermes.data.model.AuditSeverity
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ApprovalDetailUiState(
    val approval: Approval? = null,
    val impactReportShown: Boolean = false,
    val secondConfirmPending: Boolean = false,
    val finished: Boolean = false,
    val message: String? = null,
)

class ApprovalDetailViewModel(
    private val approvalId: String,
    private val approvals: ApprovalRepository,
    private val emergency: EmergencyStopController,
    private val audit: AuditRepository,
    private val spine: GatewayEventSpine,
) : ViewModel() {

    private val _state = MutableStateFlow(ApprovalDetailUiState())
    val state: StateFlow<ApprovalDetailUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            approvals.items.collect { list ->
                val current = list.firstOrNull { it.id == approvalId }
                _state.update { it.copy(approval = current) }
            }
        }
    }

    fun markImpactReportShown() {
        _state.update { it.copy(impactReportShown = true) }
    }

    fun decide(approve: Boolean, notes: String? = null) {
        val approval = _state.value.approval ?: return
        val secondConfirm = _state.value.secondConfirmPending
        val result = approvals.decide(
            approval = approval,
            approve = approve,
            confirmedTwice = secondConfirm,
            impactReportShown = _state.value.impactReportShown,
            notes = notes,
        )
        when (result) {
            is ApprovalRepository.DecisionResult.Decided -> {
                audit.append(
                    AuditEvent(
                        actor = "user",
                        action = if (approve) "approve" else "reject",
                        target = result.approval.title,
                        payloadSummary = (notes ?: "").take(120),
                        severity = AuditSeverity.NOTICE,
                        approvalId = result.approval.id,
                        proofHash = "",
                    )
                )
                viewModelScope.launch {
                    spine.current()?.decideApproval(result.approval, approve, notes)
                }
                _state.update { it.copy(finished = true, secondConfirmPending = false) }
            }
            ApprovalRepository.DecisionResult.NeedsSecondConfirmation -> {
                _state.update {
                    it.copy(
                        secondConfirmPending = true,
                        message = "Tap Approve again to confirm.",
                    )
                }
            }
            ApprovalRepository.DecisionResult.NeedsImpactReport -> {
                _state.update { it.copy(message = "Review the impact report first.") }
            }
            ApprovalRepository.DecisionResult.BlockedByEmergencyStop -> {
                _state.update { it.copy(message = "Emergency stop is active.") }
            }
            ApprovalRepository.DecisionResult.AlreadyDecided -> {
                _state.update { it.copy(finished = true) }
            }
        }
    }

    fun consumeMessage() { _state.update { it.copy(message = null) } }
}
