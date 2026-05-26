package com.aci.hermes.approval.state

import androidx.lifecycle.ViewModel
import com.aci.hermes.approval.event.ApprovalEventSink
import com.aci.hermes.approval.event.RecordingApprovalEventSink
import com.aci.hermes.approval.model.ApprovalCard
import com.aci.hermes.approval.model.ApprovalHistoryItem
import com.aci.hermes.approval.model.CriticalImpactReport
import com.aci.hermes.approval.model.RollbackPlan
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class ApprovalsUiState(
    val cards: List<ApprovalCard> = emptyList(),
    val history: List<ApprovalHistoryItem> = emptyList()
)

class ApprovalViewModel(
    private val store: ApprovalStore
) : ViewModel() {

    private val _state = MutableStateFlow(
        ApprovalsUiState(cards = store.snapshot(), history = store.historySnapshot())
    )
    val state: StateFlow<ApprovalsUiState> = _state.asStateFlow()

    private fun publish() {
        _state.value = ApprovalsUiState(cards = store.snapshot(), history = store.historySnapshot())
    }

    fun add(card: ApprovalCard) { store.add(card); publish() }

    fun approveRisky(id: String, note: String? = null) { store.approveRisky(id, note); publish() }
    fun editRisky(id: String, newAction: String) { store.editRisky(id, newAction); publish() }
    fun approveSeriousStep1(id: String) { store.approveSeriousStep1(id); publish() }
    fun approveSeriousStep2(id: String) { store.approveSeriousStep2(id); publish() }
    fun attachImpactReport(id: String, report: CriticalImpactReport) {
        store.attachImpactReport(id, report); publish()
    }
    fun attachRollbackPlan(id: String, plan: RollbackPlan) {
        store.attachRollbackPlan(id, plan); publish()
    }
    fun approveCriticalStep1(id: String) { store.approveCriticalStep1(id); publish() }
    fun approveCriticalStep2(id: String) { store.approveCriticalStep2(id); publish() }
    fun reject(id: String, reason: String? = null) { store.reject(id, reason); publish() }
    fun emergencyStop(id: String) { store.emergencyStop(id); publish() }
    fun sweepExpired() { store.sweepExpired(); publish() }

    companion object {
        fun fromCards(
            initial: List<ApprovalCard>,
            sink: ApprovalEventSink = RecordingApprovalEventSink()
        ): ApprovalViewModel = ApprovalViewModel(ApprovalStore(sink = sink, initial = initial))
    }
}
