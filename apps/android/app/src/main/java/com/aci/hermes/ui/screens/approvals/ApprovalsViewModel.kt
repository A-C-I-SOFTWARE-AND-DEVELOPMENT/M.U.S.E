package com.aci.hermes.ui.screens.approvals

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.approvals.ApprovalRepository
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.emergency.EmergencyStopState
import com.aci.hermes.data.gateway.GatewayEventSpine
import com.aci.hermes.data.model.Approval
import com.aci.hermes.data.model.AuditEvent
import com.aci.hermes.data.model.AuditSeverity
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ApprovalsUiState(
    val items: List<Approval> = emptyList(),
    val emergency: EmergencyStopState = EmergencyStopState(),
    val pendingSecondConfirmId: String? = null,
    val snackbar: String? = null,
)

class ApprovalsViewModel(
    private val approvals: ApprovalRepository,
    private val emergency: EmergencyStopController,
    private val audit: AuditRepository,
    private val spine: GatewayEventSpine,
) : ViewModel() {

    private val _state = MutableStateFlow(ApprovalsUiState())
    val state: StateFlow<ApprovalsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            approvals.items.collect { list -> _state.update { it.copy(items = list) } }
        }
        viewModelScope.launch {
            emergency.state.collect { es -> _state.update { it.copy(emergency = es) } }
        }
    }

    fun decide(
        approval: Approval,
        approve: Boolean,
        impactReportShown: Boolean = false,
        notes: String? = null,
    ) {
        val pendingId = _state.value.pendingSecondConfirmId
        val confirmedTwice = pendingId == approval.id
        val result = approvals.decide(
            approval = approval,
            approve = approve,
            confirmedTwice = confirmedTwice,
            impactReportShown = impactReportShown,
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
                _state.update { it.copy(pendingSecondConfirmId = null, snackbar = null) }
            }
            ApprovalRepository.DecisionResult.NeedsSecondConfirmation -> {
                _state.update {
                    it.copy(
                        pendingSecondConfirmId = approval.id,
                        snackbar = "Tap Approve again to confirm.",
                    )
                }
            }
            ApprovalRepository.DecisionResult.NeedsImpactReport -> {
                _state.update { it.copy(snackbar = "Open the impact report first.") }
            }
            ApprovalRepository.DecisionResult.BlockedByEmergencyStop -> {
                _state.update { it.copy(snackbar = "Emergency stop is active.") }
            }
            ApprovalRepository.DecisionResult.AlreadyDecided -> {
                _state.update { it.copy(snackbar = "Already decided.") }
            }
        }
    }

    fun consumeSnackbar() { _state.update { it.copy(snackbar = null) } }
    fun consumeSecondConfirmation() { _state.update { it.copy(pendingSecondConfirmId = null) } }
}
