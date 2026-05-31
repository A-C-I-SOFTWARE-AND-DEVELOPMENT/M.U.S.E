package com.aci.hermes.approval.state

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.approval.event.ApprovalEventSink
import com.aci.hermes.approval.event.RecordingApprovalEventSink
import com.aci.hermes.approval.model.ApprovalCard
import com.aci.hermes.approval.model.ApprovalHistoryItem
import com.aci.hermes.approval.model.ApprovalStatus
import com.aci.hermes.approval.model.CriticalImpactReport
import com.aci.hermes.approval.model.RollbackPlan
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ApprovalsUiState(
    val cards: List<ApprovalCard> = emptyList(),
    val history: List<ApprovalHistoryItem> = emptyList()
)

class ApprovalViewModel(
    private val store: ApprovalStore,
    private val repository: CockpitApprovalsRepository? = null,
) : ViewModel() {

    private val _state = MutableStateFlow(
        ApprovalsUiState(cards = store.snapshot(), history = store.historySnapshot())
    )
    val state: StateFlow<ApprovalsUiState> = _state.asStateFlow()

    init {
        // Read cutover: when a gateway is paired, load the REAL pending
        // owner-approval cards into the store so the screen shows live data
        // instead of an empty queue. (Deciding through the gateway — which
        // submits the owner phrase — is a separate, safety-reviewed step.)
        repository?.let { repo ->
            viewModelScope.launch {
                repo.refresh()
                repo.cards.value.forEach { store.add(it) }
                publish()
            }
        }
    }

    private fun publish() {
        _state.value = ApprovalsUiState(cards = store.snapshot(), history = store.historySnapshot())
    }

    fun add(card: ApprovalCard) { store.add(card); publish() }

    fun approveRisky(id: String, note: String? = null) {
        store.approveRisky(id, note).publishAndSync(id)
    }
    fun editRisky(id: String, newAction: String) { store.editRisky(id, newAction); publish() }
    fun approveSeriousStep1(id: String) { store.approveSeriousStep1(id); publish() }
    fun approveSeriousStep2(id: String) { store.approveSeriousStep2(id).publishAndSync(id) }
    fun attachImpactReport(id: String, report: CriticalImpactReport) {
        store.attachImpactReport(id, report); publish()
    }
    fun attachRollbackPlan(id: String, plan: RollbackPlan) {
        store.attachRollbackPlan(id, plan); publish()
    }
    fun approveCriticalStep1(id: String) { store.approveCriticalStep1(id); publish() }
    fun approveCriticalStep2(id: String) { store.approveCriticalStep2(id).publishAndSync(id) }
    fun reject(id: String, reason: String? = null) {
        store.reject(id, reason).publishAndSync(id, rejectReason = reason)
    }
    fun emergencyStop(id: String) { store.emergencyStop(id); publish() }
    fun sweepExpired() { store.sweepExpired(); publish() }

    /**
     * Publish the new local state and, when a terminal decision just landed
     * on a paired gateway, mirror it through the cockpit. The owner phrase
     * is submitted ONLY here — after the local multi-step confirmation has
     * already completed — so the on-device ceremony precedes (and the
     * gateway still independently enforces) the owner gate.
     */
    private fun DecisionResult.publishAndSync(id: String, rejectReason: String? = null) {
        publish()
        val repo = repository ?: return
        if (this !is DecisionResult.Updated) return
        when (card.status) {
            ApprovalStatus.APPROVED -> viewModelScope.launch { repo.approve(id) }
            ApprovalStatus.REJECTED -> viewModelScope.launch { repo.reject(id, rejectReason) }
            else -> Unit // non-terminal step (e.g. serious step 1) — nothing to mirror yet
        }
    }

    companion object {
        fun fromCards(
            initial: List<ApprovalCard>,
            sink: ApprovalEventSink = RecordingApprovalEventSink()
        ): ApprovalViewModel = ApprovalViewModel(ApprovalStore(sink = sink, initial = initial))
    }
}
