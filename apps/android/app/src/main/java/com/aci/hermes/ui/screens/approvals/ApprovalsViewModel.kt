package com.aci.hermes.ui.screens.approvals

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.approvals.Approval
import com.aci.hermes.approvals.ApprovalQueue
import com.aci.hermes.approvals.ProofEngine
import com.aci.hermes.audit.AuditEntry
import com.aci.hermes.audit.AuditLog
import com.aci.hermes.events.JarvisEvent
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ApprovalsUiState(
    val approvals: List<Approval> = emptyList(),
    val openedProof: String? = null,
)

class ApprovalsViewModel(
    private val queue: ApprovalQueue,
    private val audit: AuditLog,
) : ViewModel() {

    private val _state = MutableStateFlow(ApprovalsUiState())
    val state: StateFlow<ApprovalsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            queue.approvals.collect { list ->
                _state.value = _state.value.copy(approvals = list)
            }
        }
    }

    fun openProof(approval: Approval) {
        _state.value = _state.value.copy(openedProof = ProofEngine.render(approval))
    }

    fun closeProof() {
        _state.value = _state.value.copy(openedProof = null)
    }

    fun confirm(approval: Approval) {
        queue.confirm(approval.id)
    }

    fun approve(approval: Approval) {
        // The final tap is itself a confirmation — record it then try
        // to commit the decision. The queue's approve() is a no-op if
        // the count still hasn't reached the required threshold.
        queue.confirm(approval.id)
        if (queue.approve(approval.id)) {
            audit.record(
                AuditEntry(
                    source = JarvisEvent.Source.APPROVAL,
                    severity = JarvisEvent.Severity.NOTICE,
                    message = "Owner approved: ${approval.summary}",
                    attributes = mapOf(
                        "tier" to approval.tier.name,
                        "id" to approval.id,
                    ),
                    proofSnapshot = ProofEngine.render(approval),
                )
            )
        }
    }

    fun reject(approval: Approval, reason: String? = null) {
        queue.reject(approval.id, reason)
        audit.record(
            AuditEntry(
                source = JarvisEvent.Source.APPROVAL,
                severity = JarvisEvent.Severity.NOTICE,
                message = "Owner rejected: ${approval.summary}",
                attributes = mapOf(
                    "tier" to approval.tier.name,
                    "id" to approval.id,
                    "reason" to (reason ?: ""),
                ),
                proofSnapshot = ProofEngine.render(approval),
            )
        )
    }
}
